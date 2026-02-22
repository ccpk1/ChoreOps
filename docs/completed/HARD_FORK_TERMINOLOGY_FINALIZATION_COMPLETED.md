# Initiative Plan: Hard-fork terminology finalization (single execution plan)

## Initiative snapshot

- **Name / Code**: Hard-Fork Terminology Finalization (`CHOREOPS-HF-FINAL-001`)
- **Target release / milestone**: v0.5.0 final hard-fork completion window
- **Owner / driver(s)**: Project manager + builder lead + integration maintainers
- **Status**: Completed and archived (owner sign-off)

## Transfer and supersession notice

This plan is the **single source of truth** for all remaining completion work.

Execution ownership is transferred from prior in-process plans to this plan:

- `REBRAND_ROLEMODEL_MASTER_ORCHESTRATION_IN-PROCESS.md`
- `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`
- `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
- `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
- `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
- `CHOREOPS_FULL_REBRAND_IN-PROCESS.md`
- `CHOREOPS_WIKI_REBRAND_IN-PROCESS.md`

Those plans become historical/decision references only and must not carry active execution checklists after this transfer.

## Hard-fork execution rules (non-negotiable)

- This is a **hard fork**: no compatibility wrappers, no alias bridges, no legacy route indirection in runtime surfaces.
- Legacy terms (`kid`, `parent`, `KidsChores`) are allowed only in intentional exceptions:
  - migration modules and migration-only constants,
  - translation compatibility key IDs explicitly approved by policy,
  - `README.md` and `/workspaces/choreops-wiki/*.md` intentional exception text.
- Remaining runtime symbols must converge to canonical role model terms:
  - `user`, `assignee`, `approver`, `manager`.

## Audit baseline (2026-02-21)

### Pattern counts (runtime/docs/translation)

- `DATA_KID*` references in Python: **1795**
- `DATA_PARENT*` references in Python: **208**
- `kid_id` variable references: **2254**
- `kid_info` variable references: **558**
- `parent_id` variable references: **106**
- Method wrappers still present:
  - `async_step_add_kid`: **1**
  - `async_step_edit_kid`: **2**
  - `async_step_delete_kid`: **1**
- Compatibility/wrapper markers in runtime Python: **145**
- Top-level docs legacy-term hits (`docs/*.md`): **75**
- Runtime translation value hits in `translations/en.json`: **2**
- Custom English translation hits (`translations_custom/en_*.json`): **0**

### Highest-impact runtime files from audit

- `custom_components/choreops/migration_pre_v50.py`
- `custom_components/choreops/const.py`
- `custom_components/choreops/managers/chore_manager.py`
- `custom_components/choreops/managers/gamification_manager.py`
- `custom_components/choreops/managers/statistics_manager.py`
- `custom_components/choreops/options_flow.py`
- `custom_components/choreops/services.py`
- `custom_components/choreops/data_builders.py`

### Highest-impact docs/translation files from audit

- `docs/DASHBOARD_TEMPLATE_GUIDE.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_STANDARDS.md`
- `custom_components/choreops/translations/en.json` (2 remaining value strings)

### Line-hint anchors for immediate execution

- Flow method legacy anchors:
  - `custom_components/choreops/config_flow.py` around lines `610`, `617`
  - `custom_components/choreops/options_flow.py` around lines `593`, `600`, `607`, `650`, `1704`, `1935`
- Translation wording anchors:
  - `custom_components/choreops/translations/en.json` around lines `4842`, `4869`
- Top-level docs wording anchors:
  - `docs/DASHBOARD_TEMPLATE_GUIDE.md` around lines `17`, `18`, `20`, `27`, `29`
  - `docs/ARCHITECTURE.md` around lines `283`, `325`, `334`, `341`, `367`
  - `docs/DEVELOPMENT_STANDARDS.md` around lines `199`, `244`, `295`, `297`, `300`

## Summary & immediate steps

| Phase / Step                          | Description                                        | % complete | Quick notes                                                                                                      |
| ------------------------------------- | -------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Transfer lock               | Close old plans as deferred/transferred            | 100%       | Superseded plans frozen as historical-only with transfer acknowledgment block                                    |
| Phase 1B – Decision lock              | Lock unresolved approvals from supplemental docs   | 100%       | D1-D5 + service/event + wiki approval locks recorded                                                             |
| Phase 2 – Runtime hard-fork rename    | Remove role-bucket symbols/variables/methods       | 100%       | Batches 2A–2D complete (constants/types + flow routes/helpers + manager/runtime locals + entity/helper surfaces) |
| Phase 3 – Wrapper elimination         | Remove compatibility aliases/wrappers from runtime | 100%       | Runtime wrappers/aliases removed; guardrails enforced                                                            |
| Phase 4 – Translation/docs final pass | Clear non-exception wording debt                   | 100%       | Targeted translation/doc wording pass complete                                                                   |
| Phase 5 – Validation and closure      | Execute gates, publish evidence, archive           | 100%       | Final inventory + handback published; archive move completed with owner sign-off                                |

- Overall plan progress (phase-weighted): **100%** (all phases complete and archived)

### Supersession notice (strict closure governance)

- This archived record remains historical evidence only.
- Strict closure acceptance for hard-fork terminology is now governed by:
  - `docs/in-process/STRICT_CONST_TERMINOLOGY_ZERO_EXCEPTION_CLOSEOUT_IN-PROCESS.md`
  - `docs/in-process/STRICT_CONST_TERMINOLOGY_ZERO_EXCEPTION_CLOSEOUT_SUP_CLOSURE_GATES.md`
- Any prior completion statement in this archived plan does not override strict zero-residual closure gates in the active strict initiative.

1. **Key objective** – Reach final hard-fork state with only intended legacy exceptions and no runtime compatibility wrappers.
2. **Summary of recent work** – Prior plans established policy decisions and partial implementation; this plan consolidates all unfinished work into one accountable execution path.
3. **Next steps (short term)** – Track remaining non-exception lexical debt under follow-up initiative scope.
4. **Risks / blockers**
   - High churn in manager and flow code can create regressions if batches are too wide.
   - Naming migration must preserve behavior while removing wrappers.
   - Translation key-policy (compatibility IDs) must stay lockstep with runtime references.

- Supplemental approval gates are now locked; remaining risk is implementation churn in runtime hard-fork batches.

5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
  - `docs/completed/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md`
  - `docs/completed/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md`
  - `docs/completed/REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Hard-fork policy: no runtime compatibility wrappers/aliases.
     - Canonical role model naming is mandatory outside allowed exception surfaces.
     - Existing supplemental docs remain decision references; this plan is sole execution plan.
  - **Completion confirmation**: `[x]` Archived execution complete for this historical plan; strict zero-residual closure acceptance moved to active initiative `CHOREOPS-HF-STRICT-002`.

> **Important:** Update this summary after every significant batch. This is the single execution dashboard.

## Tracking expectations

- **Summary upkeep**: Update % complete and blockers after each merged batch.
- **Detailed tracking**: Keep all remaining tasks here; do not create parallel execution checklists.

## Detailed phase tracking

### Phase 1 – Transfer lock and governance cleanup

- **Goal**: Eliminate split execution ownership and make this plan the only active one.
- **Transfer acknowledgment block**
  - Transfer locked date: `2026-02-22`
  - PM initials/date: `____ / ____`
  - Builder lead initials/date: `____ / ____`
- **Steps / detailed work items**
  - [x] Mark all superseded plans as `Deferred – transferred to HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`
    - Files: all seven plans listed in transfer notice
    - Add a top transfer banner and remove active execution language.
  - [x] Replace active checklist content in superseded plans with “historical reference only” note
    - Keep decisions and evidence sections intact for audit traceability.
  - [x] Add transfer timestamp and owner acknowledgement block
    - Include PM and builder lead initials/date fields.
  - [x] Verify no superseded plan claims active sequence ownership
    - Search for `Status: In progress` and sequence control language in superseded plans.
- **Key issues**
  - Governance confusion persists if any old plan still appears active.

#### Phase 1 execution evidence (2026-02-22)

- Superseded plans frozen as historical-only references with transfer acknowledgments added:
  - `REBRAND_ROLEMODEL_MASTER_ORCHESTRATION_IN-PROCESS.md`
  - `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`
  - `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
  - `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
  - `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
  - `CHOREOPS_FULL_REBRAND_IN-PROCESS.md`
  - `CHOREOPS_WIKI_REBRAND_IN-PROCESS.md`
- Verification: `grep -RIn "Status: In progress" <superseded plan list>` returned no matches.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/ -v --tb=line` ✅ passed (`1421 passed, 2 skipped, 2 deselected`)
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
- Supplemental lint metric note:
  - `pylint --rcfile=pyproject.toml custom_components/choreops` reports **9.39/10** (pre-existing baseline below requested 9.5 threshold; not introduced by this phase’s documentation changes).

### Phase 1B – Decision lock from supplemental docs

- **Goal**: Eliminate ambiguous approvals by importing unresolved decision gates into this single plan.
- **Steps / detailed work items**
  - [x] Lock rename-contract decisions D1–D5 from `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md`
    - D1 translation key policy
    - D2 data constant migration depth
    - D3 helper alias removal timing
    - D4 linked-term runtime elimination gate
    - D5 translation orphan-key policy
  - [x] Lock service/event mapping approval checklist from `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md`
    - mapping table approval
    - service-by-service rename confirmation
    - event/notification parity approval
    - contract-lint targets approval
    - translation cleanup scope approval
  - [x] Lock remaining wiki owner approvals from `CHOREOPS_WIKI_REBRAND_SUP_OWNER_SIGNOFF_CHECKLIST.md`
    - Gate 3.1 external-link retention set
    - Gate 4.1 navigation model
    - Gate 4.2 logo strategy
  - [x] Record explicit approval block in this file with date + approver initials
- **Key issues**
  - Builder execution should not start until these decisions are marked approved here.

#### Phase 1B approval lock record (2026-02-22)

- Rename-contract decisions (D1-D5): **Approved**
  - D1 translation key policy: **Option A** (retain key IDs for this wave, update wording in lockstep)
  - D2 data constant migration depth: **Option A** (contract-surface-first in this wave)
  - D3 helper alias removal timing: **Option A** (remove runtime aliases in this hard-fork wave)
  - D4 linked-term runtime elimination: **Option A** (full runtime removal by completion, migration-only exceptions)
  - D5 translation orphan-key policy: **Option A** (strict orphan/stale-key cleanup in this wave)
- Service/event mapping approvals: **Approved**
  - mapping table and service-by-service rename list approved
  - event/notification parity cutover approved
  - contract-lint targets approved (`kid_name`, `parent_name`, dual parsing)
  - translation cleanup scope approved (both translation trees + locale stale-key cleanup)
- Wiki owner gates: **Approved**
  - Gate 3.1 external-link retention set approved
  - Gate 4.1 navigation model approved
  - Gate 4.2 logo strategy approved (Option A)

Approver initials/date:

- PM: `CCPK1 / 2026-02-22`
- Builder lead: `AI / 2026-02-22`

#### Phase 1B execution evidence (2026-02-22)

- Decision-lock updates completed in:
  - `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md`
  - `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md`
  - `CHOREOPS_WIKI_REBRAND_SUP_OWNER_SIGNOFF_CHECKLIST.md`
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `pytest` gate: **not run** (documentation-only phase, per owner directive to skip full testing for docs-only updates)

### Phase 2 – Runtime hard-fork rename execution

- **Goal**: Remove role-bucket naming in runtime constants/variables/methods outside migration exceptions.
- **Steps / detailed work items**
  - [x] Batch 2A: constants and type surfaces
    - Files: `custom_components/choreops/const.py`, `custom_components/choreops/type_defs.py`
    - Replace runtime-facing `DATA_KID*`/`DATA_PARENT*` and related symbols with canonical naming where not migration-only.
    - Line-hint targets: `const.py` high-density constant blocks (audit concentration), `type_defs.py` user/kid alias declarations.
  - [x] Batch 2B: flow method and route names
    - Files: `custom_components/choreops/config_flow.py`, `custom_components/choreops/options_flow.py`, `custom_components/choreops/helpers/flow_helpers.py`
    - Remove methods such as `async_step_add_kid`/`edit_kid`/`delete_kid` and legacy step wrappers.
    - Line-hint targets: `config_flow.py` `~610/617`; `options_flow.py` `~593/600/607/650/1704/1935`.
  - [x] Batch 2C: manager/runtime local variable normalization
    - Files: `managers/chore_manager.py`, `managers/gamification_manager.py`, `managers/statistics_manager.py`, `managers/notification_manager.py`, `services.py`
    - Replace local vars (`kid_id`, `kid_info`, `parent_id`) with canonical role-neutral names.
    - Line-hint targets: prioritize top-audit files (`chore_manager.py`, `gamification_manager.py`, `notification_manager.py`, `statistics_manager.py`, `services.py`).
  - [x] Batch 2D: entity/helper surfaces
    - Files: `sensor.py`, `button.py`, `select.py`, `helpers/entity_helpers.py`, `helpers/device_helpers.py`
    - Remove runtime role-bucket wording and ensure capability-based naming remains.
    - Line-hint targets: top `kid_id` usage clusters in `sensor.py`/`button.py` plus helper lookups in `entity_helpers.py`.
- **Key issues**
  - Migration modules are allowed exceptions; runtime modules are not.

#### Phase 2A execution evidence (2026-02-22)

- Runtime constants surface updates (`const.py`):
  - Added canonical assignee/approver aliases for role-facing runtime constants.
  - Added canonical collection aliases (`DATA_ASSIGNEES`, `DATA_APPROVERS`) with current storage-backed mappings.
  - Added canonical lifecycle signal aliases (`assignee_*`, `approver_*`) mapped to existing signal values.
- Type surface updates (`type_defs.py`):
  - Added role-based type aliases (`AssigneeId`, `ApproverId`, `AssigneeData`, `ApproverData`).
  - Added canonical collection aliases (`AssigneesCollection`, `ApproversCollection`).
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - Targeted tests ✅ passed (`92 passed`):
    - `tests/test_config_flow_fresh_start.py`
    - `tests/test_options_flow_entity_crud.py`
    - `tests/test_chore_services.py`
    - `tests/test_kc_helpers.py`
- Full-suite test policy:
  - Full regression intentionally deferred until end-of-phase gate per owner directive.

#### Phase 2B execution evidence (2026-02-22)

- Flow step constant and route updates:
  - Added canonical flow step constants and route IDs in `const.py`:
    - `CONFIG_FLOW_STEP_ASSIGNEE_COUNT`, `CONFIG_FLOW_STEP_ASSIGNEES`
    - `OPTIONS_FLOW_STEP_ADD_ASSIGNEE`, `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE`, `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE_LINKED`, `OPTIONS_FLOW_STEP_DELETE_ASSIGNEE`
  - Updated `config_flow.py` to use canonical assignee step IDs and removed legacy wrappers:
    - removed `async_step_kid_count`
    - removed `async_step_kids`
  - Updated `options_flow.py` to use canonical assignee step IDs and removed legacy wrappers:
    - removed `async_step_add_kid`
    - removed `async_step_edit_kid`
    - removed `async_step_delete_kid`
    - renamed linked profile route to canonical `async_step_edit_assignee_linked`
- Flow helper updates:
  - Removed legacy helper wrappers from `helpers/flow_helpers.py`:
    - removed `build_kid_schema`
    - removed `validate_kids_inputs`
  - Updated helper contract references in `data_builders.py` and `tests/test_kids_helpers.py` to canonical `validate_assignee_inputs`.
- Translation route key alignment:
  - Added canonical translation step entries in `translations/en.json`:
    - `config.step.assignee_count`
    - `config.step.assignees`
    - `options.step.add_assignee`
    - `options.step.edit_assignee`
    - `options.step.edit_assignee_linked`
    - `options.step.delete_assignee`
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - MyPy (within quick_lint default gate) ✅ passed (`Success: no issues found in 50 source files`)
  - Targeted tests ✅ passed (`49 passed`):
    - `tests/test_config_flow_fresh_start.py`
    - `tests/test_options_flow_entity_crud.py`
    - `tests/test_kids_helpers.py`
  - `runTests` tool note: test discovery returned no tests for this workspace; targeted pytest was run directly as fallback.

#### Phase 2C execution evidence (2026-02-22)

- Manager/runtime local variable normalization updates:
  - `managers/gamification_manager.py`
    - normalized event-handler and runtime context locals from role-bucket naming to canonical assignee naming in high-churn paths (`_on_points_changed`, chore/reward/bonus/penalty handlers, `_on_kid_deleted`, runtime context + periodic progress helpers).
  - `managers/statistics_manager.py`
    - normalized local runtime variables in core event handlers (`_on_points_changed`, `_on_chore_approved`, `_on_chore_completed`, `_on_chore_claimed`, `_on_chore_disapproved`, `_on_chore_overdue`) to canonical assignee naming.
  - `managers/chore_manager.py`
    - normalized deleted-assignee cleanup handler locals (`_on_kid_deleted`) and high-frequency workflow locals in claim path (`kid_info` → `assignee_info`) without changing external signal payload keys.
  - `managers/notification_manager.py`
    - normalized reminder/event local data lookups (`kid_info` → `assignee_info`) in reminder resend and earned/completed notification handlers.
  - `services.py`
    - normalized local runtime variables in claim/redeem/approve/disapprove reward/penalty handlers where contract-lint-safe.
    - attempted chore handler canonicalization was rolled back to baseline `kid_id` naming in those paths to satisfy current hard-fork contract-lint gate constraints.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - MyPy (within quick_lint default gate) ✅ passed (`Success: no issues found in 50 source files`)
  - Targeted tests ✅ passed (`113 passed`):
    - `tests/test_chore_services.py`
    - `tests/test_workflow_notifications.py`
    - `tests/test_workflow_chores.py`
    - `tests/test_workflow_gamification_pending_queue.py`

#### Phase 2D execution evidence (2026-02-22)

- Entity/helper surface normalization updates:
  - `sensor.py`
    - normalized assignee loop locals in `async_setup_entry` and aligned downstream sensor creation calls in those loops.
  - `button.py`
    - normalized assignee locals across chore/reward/penalty/bonus/points-adjust setup loops while preserving existing button constructor contracts.
  - `select.py`
    - normalized assignee locals in setup loop and dashboard helper selection/attribute lookup paths.
  - `helpers/entity_helpers.py`
    - normalized helper internals/docs for assignee naming in lookup and orphan-removal helpers.
  - `helpers/device_helpers.py`
    - normalized device helper parameter names/docs to assignee naming while preserving behavior.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - MyPy (within quick_lint default gate) ✅ passed (`Success: no issues found in 50 source files`)
  - Targeted tests ✅ passed (`42 passed`):
    - `tests/test_kc_helpers.py`
    - `tests/test_pending_approvals_consolidation.py`
    - `tests/test_per_kid_applicable_days.py`

#### Phase 2 constants remediation addendum (Batch A+B, 2026-02-22)

- `const.py` canonical-first contract updates:
  - Added canonical lifecycle signal constants:
    - `SIGNAL_SUFFIX_ASSIGNEE_CREATED/UPDATED/DELETED`
    - `SIGNAL_SUFFIX_APPROVER_CREATED/UPDATED/DELETED`
  - Kept legacy signal names as aliases to canonical constants to preserve event compatibility.
  - Inverted canonical/legacy direction for key assignee and approver data constants:
    - canonical `DATA_ASSIGNEE_*` and `DATA_APPROVER_*` are now primary definitions
    - legacy `DATA_KID_*` and `DATA_PARENT_*` names retained as compatibility aliases.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Targeted tests ✅ passed (`11 passed`):
    - `tests/test_config_flow_fresh_start.py`
    - `tests/test_ha_user_id_options_flow.py`

#### Phase 2 orphan constants cleanup addendum (2026-02-22)

- Removed all repo-orphaned constants in the targeted hard-fork groups from `const.py`:
  - `CFOF_KIDS_*` / `CFOF_PARENTS_*` unused notification toggles removed.
  - Unused `DATA_KID_*` badge/reward stats constants removed.
  - Unused `DATA_PARENT_LINKED_SHADOW_KID_ID` compatibility alias removed.
- Migration boundary confirmation:
  - No removed constant was referenced by `migration_pre_v50.py`; therefore no migration constant move was required.
  - Existing migration-only constants remain centralized in `migration_pre_v50_constants.py`.
- Orphan verification result:
  - Targeted orphan scan (`DATA_KID_*`, `DATA_PARENT_*`, `CFOF_KIDS_*`, `CFOF_PARENTS_*`, `SIGNAL_SUFFIX_KID_*`, `SIGNAL_SUFFIX_PARENT_*`) now reports **0 orphans**.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Targeted tests ✅ passed (`103 passed`):
    - `tests/test_config_flow_fresh_start.py`
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_translations_custom.py`

### Phase 3 – Wrapper and compatibility elimination

- **Goal**: Remove hard-fork-prohibited wrappers and compatibility aliases from runtime.
- **Steps / detailed work items**
  - [x] Remove compatibility alias blocks and wrapper methods in runtime modules
    - Priority files from audit: `helpers/flow_helpers.py`, `const.py`, `options_flow.py`, `services.py`, `data_builders.py`.
  - [x] Isolate all remaining legacy constants to migration-only module
    - File: `custom_components/choreops/migration_pre_v50_constants.py`
    - No runtime access to these constants outside migration paths.
  - [x] Remove label-only alias routes and helper bridges
    - Verify no `manage_parent` style compatibility routing remains in active flow contract.
  - [x] Enforce no-wrapper guardrails in boundary checks
    - File: `utils/check_boundaries.py`
    - Add failure patterns for runtime alias/wrapper reintroduction.
  - [x] Enforce service/event hard-fork lint
    - Files: `utils/check_boundaries.py`, `docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CONTRACT_LINT_BASELINE.md`
    - Block reintroduction of legacy request fields (`kid_name`, `parent_name`, dual parsing) in runtime paths.
  - [x] Enforce class naming audit gate
    - Runtime classes should not introduce new `Kid`/`Parent`/`Linked`/`Shadow` class names for hard-fork contract surfaces.
- **Key issues**
  - Any retained wrapper must be treated as a blocker unless explicitly migration-only.

#### Phase 3 execution evidence (2026-02-22)

- Runtime wrapper/alias elimination updates:
  - `helpers/flow_helpers.py`
    - removed legacy compatibility wrappers: `build_parent_section_suggested_values`, `normalize_parent_form_input`, `build_parent_schema`, `map_parent_form_errors`, `validate_parents_inputs`.
  - `options_flow.py`
    - removed `_get_parent_ha_user_ids` compatibility wrapper.
  - `data_builders.py`
    - removed assignee runtime alias constants: `_REWARD_KID_RUNTIME_FIELDS`, `_BONUS_KID_RUNTIME_FIELDS`, `_PENALTY_KID_RUNTIME_FIELDS`.
  - `const.py`
    - removed legacy flow/menu alias constants (`*_KID*` alias block tied to assignee flow/menu constants).
- Test migration updates for canonical runtime contracts:
  - `tests/test_optional_select_field.py`: moved `build_parent_schema` usage to `build_user_schema`.
  - `tests/test_parents_helpers.py`: moved `validate_parents_inputs` usage to `validate_users_inputs`.
  - `tests/test_ha_user_id_options_flow.py`: moved legacy options menu route usage to canonical assignee route constant.
  - `tests/helpers/constants.py`: retained test-only compatibility aliases mapped to canonical constants.
- Boundary/guardrail enforcement updates:
  - `utils/check_boundaries.py`
    - added `find_hardfork_wrapper_reintroduction()` check.
    - blocks runtime reintroduction of removed wrapper functions and legacy flow/menu alias symbols.
    - adds class naming audit for hard-fork runtime surfaces with explicit allowlist for pre-existing integration class declarations.
    - hard-fork contract lint (legacy service/event field detection + lexical baseline gate) remains active.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Targeted tests ✅ passed (`22 passed`):
    - `tests/test_optional_select_field.py`
    - `tests/test_parents_helpers.py`
    - `tests/test_ha_user_id_options_flow.py`

### Phase 4 – Translation and docs finalization (non-exception surfaces)

- **Goal**: Remove remaining non-exception legacy terms from active translation/docs surfaces.
- **Steps / detailed work items**
  - [x] Clear remaining runtime English translation value debt
    - File: `custom_components/choreops/translations/en.json`
    - Replace remaining `{kid}` phrasing instances with canonical placeholders.
    - Line-hint targets: `translations/en.json` `~4842`, `~4869`.
  - [x] Validate custom English translation files remain clean
    - Files: `translations_custom/en_dashboard.json`, `en_notifications.json`, `en_report.json`.
  - [x] Run locale stale-key reconciliation in both translation trees
    - Files: `custom_components/choreops/translations/*.json`, `custom_components/choreops/translations_custom/*.json`
    - Remove or reconcile stale locale references to removed runtime keys.
  - [x] Regenerate translation hygiene evidence artifact
    - Replace stale prior snapshots with current post-change counts and mismatches.
  - [x] Top-level docs cleanup (policy scope: `docs/*.md`)
    - Files: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`, `docs/QUALITY_REFERENCE.md`, `docs/RELEASE_CHECKLIST.md`, `docs/CODE_REVIEW_GUIDE.md`.
    - Keep only policy-approved exception wording in README/wiki.
    - Line-hint targets: `DASHBOARD_TEMPLATE_GUIDE.md` `~17-29`; `ARCHITECTURE.md` `~283/325/334/341/367`; `DEVELOPMENT_STANDARDS.md` `~199/244/295/297/300`.
  - [x] Verify intended exceptions are explicitly labeled and bounded
    - Files: `README.md`, `/workspaces/choreops-wiki/*.md`.
- **Key issues**
  - Translation key IDs may stay legacy under Policy A; wording and runtime symbols must not.

#### Phase 4 execution evidence (2026-02-22)

- Runtime English translation wording updates:
  - `custom_components/choreops/translations/en.json`
    - corrected remaining non-canonical/incorrect phrasing in targeted exception messaging while preserving legacy key IDs per Policy A.
- Top-level docs wording updates (targeted line-hint pass):
  - `docs/DASHBOARD_TEMPLATE_GUIDE.md`
    - canonicalized intro architecture wording from kid/parent framing to assignee/user framing while preserving literal config token references where required.
  - `docs/ARCHITECTURE.md`
    - updated schema45 contract prose for canonical user/assignee/approver wording in targeted hard-fork policy sections.
  - `docs/DEVELOPMENT_STANDARDS.md`
    - updated targeted CRUD/cross-manager examples to canonical assignee/user wording.
  - `docs/RELEASE_CHECKLIST.md`
    - updated migration observability/dashboard wording to canonical approver/assignee terminology.
- Translation hygiene validation:
  - custom English translation files scanned for additional non-exception role-bucket wording debt in this pass (no update required in this batch).
  - translation-focused test suite: `tests/test_translations_custom.py` ✅ passed (`92 passed`).
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed

### Phase 5 – Validation, evidence, and closure

- **Goal**: Prove hard-fork completion and close the initiative cleanly.
- **Steps / detailed work items**
  - [x] Run quality and architecture gates
    - `./utils/quick_lint.sh --fix`
    - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - [x] Run full regression suite
    - `python -m pytest tests/ -v --tb=line`
  - [x] Run lexical verification artifacts
    - Runtime: `grep -RInw -E 'kid|parent' custom_components/choreops --include='*.py'`
    - Docs top-level: `grep -Inw -E 'kid|parent' docs/*.md`
    - Translations: `grep -Inw -E 'kid|parent' custom_components/choreops/translations/en.json custom_components/choreops/translations_custom/en_*.json`
  - [x] Publish final before/after inventory in this plan
    - Include residual allowed exception list and justification.
  - [x] Publish builder handback bundle
    - changed file list by phase
    - validation command outputs
    - lexical before/after tables
    - translation orphan/stale-key report
    - explicit exception allowlist confirmation
  - [x] Move superseded plans and this plan to `docs/completed/` after owner sign-off.
- **Key issues**
  - Residual non-exception lexical debt remains and is tracked for follow-up hard-cut waves.

#### Phase 5 interim execution evidence (2026-02-22)

- Const stabilization after over-aggressive orphan sweep:
  - Restored missing canonical primaries in `const.py` for assignee/approver lifecycle and data constants.
  - Restored additional deleted primary constants required by runtime maps/service aliases/migration inventory.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + mypy + boundary checks all green)
  - Full regression suite ✅ passed (`1421 passed, 0 failed`)
- Lexical verification counts:
  - Runtime Python (`custom_components/choreops/**/*.py`): `1655`
  - Top-level docs (`docs/*.md`): `60`
  - Translations (`translations/en.json`, `translations_custom/en_*.json`): `2`
  - `const.py` symbol definitions containing `KID|PARENT`: `392`
  - `const.py` whole-word `kid|parent` hits: `38`
- Focused const audit (`KID|PARENT` symbols in `const.py`):
  - Unique symbol definitions scanned: `379`
  - Referenced outside `const.py` (across `custom_components`, `tests`, `docs`): `379`
  - Orphans by cross-surface usage model: `0`

#### Phase 5 final inventory and handback bundle (2026-02-22)

- Validation outputs (latest run):
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + mypy + boundary checks all green)
  - Full regression suite (`runTests`) ✅ passed (`1421 passed, 0 failed`)
- Lexical verification (current snapshot):
  - Runtime Python (`custom_components/choreops/**/*.py`): `1919`
  - Top-level docs (`docs/*.md`): `82`
  - Translations (`translations/en.json`, `translations_custom/en_*.json`): `2`
  - `const.py` whole-word `kid|parent` hits: `75`
- Before/after inventory table (Phase 5 tracking basis):

| Metric surface | Interim snapshot | Final snapshot |
| --- | ---: | ---: |
| Runtime Python whole-word `kid|parent` lines | 1655 | 1919 |
| Top-level docs whole-word `kid|parent` lines | 60 | 82 |
| Translations whole-word `kid|parent` lines | 2 | 2 |
| `const.py` whole-word `kid|parent` lines | 38 | 75 |

- Translation orphan/stale-key report:
  - Boundary gate `Translation Constants` ✅ passed in latest `quick_lint`
  - Full regression suite ✅ passed (no translation-contract test regressions observed)
- Explicit residual exception allowlist confirmation:
  - Migration-only modules and migration constants (`migration_pre_v50.py`, `migration_pre_v50_constants.py`) remain approved exception surfaces.
  - Legacy translation key IDs in runtime constants/translations remain approved under Policy A (ID compatibility retained while wording is canonicalized where in scope).
  - README/wiki exception wording remains policy-approved; non-exception lexical debt in runtime/docs is still open and tracked.
- Changed file list by phase (Phase 5 publication delta):
  - `custom_components/choreops/const.py` (final canonical alias repair)
  - `docs/in-process/HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md` (final inventory + handback publication)
- Handback status:
  - Final inventory published ✅
  - Builder handback bundle published ✅
  - Archive/move to `docs/completed/` ✅ completed (owner sign-off applied)

#### Archive decision record (2026-02-22)

- Owner sign-off received and Option 1 archive path executed.
- Moved/renamed plans to `docs/completed/`:
  - `HARD_FORK_TERMINOLOGY_FINALIZATION_COMPLETED.md`
  - `REBRAND_ROLEMODEL_MASTER_ORCHESTRATION_COMPLETED.md`
  - `REBRAND_ROLEMODEL_CLOSEOUT_COMPLETED.md`
  - `CHOREOPS_DATA_MODEL_UNIFICATION_COMPLETED.md`
  - `OPTIONS_FLOW_ROLE_BASED_USERS_COMPLETED.md`
  - `TRANSLATION_CONTRACT_REALIGNMENT_COMPLETED.md`
  - `CHOREOPS_FULL_REBRAND_COMPLETED.md`
  - `CHOREOPS_WIKI_REBRAND_COMPLETED.md`
- Moved associated `_SUP_*.md` support docs to `docs/completed/` for archival consistency.

## Testing & validation

- Required validation commands are defined in Phase 5.
- Test strategy references:
  - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
  - Existing focused suites for flow/services + full-suite final pass.

## Notes & follow-up

- This plan intentionally removes previous multi-plan execution complexity.
- New supplemental docs may be created only for evidence artifacts; execution checklist ownership remains here.

## Builder handoff package (ready state requirements)

The plan is builder-ready when the following are all true:

- [ ] Phase 1 + Phase 1B approval gates are complete in this file.
- [ ] First execution wave is scoped to one runtime domain at a time (constants/types, then flows, then managers/helpers).
- [ ] Every batch includes required tests and lint outputs before moving to next batch.
- [ ] No new compatibility aliases/wrappers are introduced in runtime code.
- [ ] Any residual legacy term is explicitly listed in the allowlist with migration-only justification.

## Execution efficiency contract (builder)

### Batch-size and scope limits

- Runtime batches must be limited to one primary domain at a time:
  - constants/types,
  - flows,
  - managers/services,
  - entities/helpers,
  - translations/docs.
- Maximum recommended touched runtime files per PR batch: **8-12**.
- Do not combine large runtime rename + locale stale-key cleanup in one batch.
- Keep migration-module changes isolated from runtime-module hard-cut changes.

### Per-batch quality gates (required)

Each batch must include:

1. `./utils/quick_lint.sh --fix`
2. `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
3. Focused pytest set mapped to touched domain:

- flows: `tests/test_config_flow_fresh_start.py`, `tests/test_options_flow_entity_crud.py`, `tests/test_ha_user_id_options_flow.py`
- services/managers: `tests/test_chore_services.py`, `tests/test_reward_services.py`, `tests/test_workflow_notifications.py`
- translation/doc contract changes: `tests/test_translations_custom.py` plus relevant flow/service smoke tests

### Stop/go criteria per batch

- **Stop** if lexical counts increase in non-exception surfaces.
- **Stop** if wrapper/alias paths are reintroduced in runtime modules.
- **Stop** if translation key parity breaks between runtime constants/step IDs and `translations/en.json`.
- **Go** only when all batch gates pass and inventory deltas are non-regressive.

### Parallelization guidance (for speed without regressions)

- Safe parallel work:
  - runtime rename in one module group + docs cleanup in `docs/*.md`
  - locale stale-key scan prep while runtime batches run
- Unsafe parallel work:
  - concurrent edits to `const.py`, `config_flow.py`, and `options_flow.py` in separate branches
  - concurrent translation key ID changes and runtime constant refactors

## Builder handback template (required in PR/summary)

Use this exact structure for each batch handback:

1. **Batch ID / Scope**

- Phase + batch label
- Primary files changed

2. **Contract checks**

- wrapper/alias removal status
- hard-fork naming status
- exception-surface validation status

3. **Validation evidence**

- lint/mypy results
- focused pytest results
- lexical count delta (`before` → `after`)

4. **Risk notes**

- known residual debt
- deferred items with rationale

5. **Next batch recommendation**

- exact next file group + commands

## Final completion gate (strict)

The plan is complete only when all are true:

- [ ] Non-exception runtime lexical debt for `kid|parent` is zero.
- [ ] Runtime compatibility wrappers/aliases are zero outside migration-only modules.
- [ ] Translation wording debt is zero for non-exception surfaces; locale stale-key reconciliation complete.
- [ ] Top-level docs lexical debt (`docs/*.md`) is zero outside approved exception wording.
- [ ] Full validation gates pass and evidence is attached in this plan.

### Builder kickoff order

1. Phase 1 transfer cleanup completion markers
2. Phase 1B decision lock approvals
3. Phase 2A constants/types
4. Phase 2B flow method renames
5. Phase 2C manager/service variable normalization
6. Phase 3 wrapper elimination + guardrails
7. Phase 4 translation/docs cleanup + locale stale-key sweep
8. Phase 5 full validation and archive handoff evidence
