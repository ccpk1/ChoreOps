# Initiative Plan: Hard-fork terminology finalization (single execution plan)

## Initiative snapshot

- **Name / Code**: Hard-Fork Terminology Finalization (`CHOREOPS-HF-FINAL-001`)
- **Target release / milestone**: v0.5.0 final hard-fork completion window
- **Owner / driver(s)**: Project manager + builder lead + integration maintainers
- **Status**: In progress (single authoritative execution plan)

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

| Phase / Step                          | Description                                        | % complete | Quick notes                                     |
| ------------------------------------- | -------------------------------------------------- | ---------- | ----------------------------------------------- |
| Phase 1 – Transfer lock               | Close old plans as deferred/transferred            | 50%        | Deferred status applied across superseded plans |
| Phase 1B – Decision lock              | Lock unresolved approvals from supplemental docs   | 0%         | Required before builder execution               |
| Phase 2 – Runtime hard-fork rename    | Remove role-bucket symbols/variables/methods       | 0%         | Largest scope area                              |
| Phase 3 – Wrapper elimination         | Remove compatibility aliases/wrappers from runtime | 0%         | Hard-fork requirement                           |
| Phase 4 – Translation/docs final pass | Clear non-exception wording debt                   | 0%         | Keep only intended exceptions                   |
| Phase 5 – Validation and closure      | Execute gates, publish evidence, archive           | 0%         | Finish-to-complete checkpoint                   |

1. **Key objective** – Reach final hard-fork state with only intended legacy exceptions and no runtime compatibility wrappers.
2. **Summary of recent work** – Prior plans established policy decisions and partial implementation; this plan consolidates all unfinished work into one accountable execution path.
3. **Next steps (short term)** – Execute Phase 1 governance transfer, then Phase 2 runtime rename batches in priority order.
4. **Risks / blockers**
   - High churn in manager and flow code can create regressions if batches are too wide.
   - Naming migration must preserve behavior while removing wrappers.
   - Translation key-policy (compatibility IDs) must stay lockstep with runtime references.

- Supplemental docs still contain unresolved approval gates that must be explicitly locked before coding batches.

5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md`
   - `docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md`
   - `docs/in-process/REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Hard-fork policy: no runtime compatibility wrappers/aliases.
     - Canonical role model naming is mandatory outside allowed exception surfaces.
     - Existing supplemental docs remain decision references; this plan is sole execution plan.
   - **Completion confirmation**: `[ ]` All phases complete with validation evidence and no non-exception naming debt.

> **Important:** Update this summary after every significant batch. This is the single execution dashboard.

## Tracking expectations

- **Summary upkeep**: Update % complete and blockers after each merged batch.
- **Detailed tracking**: Keep all remaining tasks here; do not create parallel execution checklists.

## Detailed phase tracking

### Phase 1 – Transfer lock and governance cleanup

- **Goal**: Eliminate split execution ownership and make this plan the only active one.
- **Steps / detailed work items**
  - [x] Mark all superseded plans as `Deferred – transferred to HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`
    - Files: all seven plans listed in transfer notice
    - Add a top transfer banner and remove active execution language.
  - [ ] Replace active checklist content in superseded plans with “historical reference only” note
    - Keep decisions and evidence sections intact for audit traceability.
  - [ ] Add transfer timestamp and owner acknowledgement block
    - Include PM and builder lead initials/date fields.
  - [x] Verify no superseded plan claims active sequence ownership
    - Search for `Status: In progress` and sequence control language in superseded plans.
- **Key issues**
  - Governance confusion persists if any old plan still appears active.

### Phase 1B – Decision lock from supplemental docs

- **Goal**: Eliminate ambiguous approvals by importing unresolved decision gates into this single plan.
- **Steps / detailed work items**
  - [ ] Lock rename-contract decisions D1–D5 from `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md`
    - D1 translation key policy
    - D2 data constant migration depth
    - D3 helper alias removal timing
    - D4 linked-term runtime elimination gate
    - D5 translation orphan-key policy
  - [ ] Lock service/event mapping approval checklist from `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md`
    - mapping table approval
    - service-by-service rename confirmation
    - event/notification parity approval
    - contract-lint targets approval
    - translation cleanup scope approval
  - [ ] Lock remaining wiki owner approvals from `CHOREOPS_WIKI_REBRAND_SUP_OWNER_SIGNOFF_CHECKLIST.md`
    - Gate 3.1 external-link retention set
    - Gate 4.1 navigation model
    - Gate 4.2 logo strategy
  - [ ] Record explicit approval block in this file with date + approver initials
- **Key issues**
  - Builder execution should not start until these decisions are marked approved here.

### Phase 2 – Runtime hard-fork rename execution

- **Goal**: Remove role-bucket naming in runtime constants/variables/methods outside migration exceptions.
- **Steps / detailed work items**
  - [ ] Batch 2A: constants and type surfaces
    - Files: `custom_components/choreops/const.py`, `custom_components/choreops/type_defs.py`
    - Replace runtime-facing `DATA_KID*`/`DATA_PARENT*` and related symbols with canonical naming where not migration-only.
    - Line-hint targets: `const.py` high-density constant blocks (audit concentration), `type_defs.py` user/kid alias declarations.
  - [ ] Batch 2B: flow method and route names
    - Files: `custom_components/choreops/config_flow.py`, `custom_components/choreops/options_flow.py`, `custom_components/choreops/helpers/flow_helpers.py`
    - Remove methods such as `async_step_add_kid`/`edit_kid`/`delete_kid` and legacy step wrappers.
    - Line-hint targets: `config_flow.py` `~610/617`; `options_flow.py` `~593/600/607/650/1704/1935`.
  - [ ] Batch 2C: manager/runtime local variable normalization
    - Files: `managers/chore_manager.py`, `managers/gamification_manager.py`, `managers/statistics_manager.py`, `managers/notification_manager.py`, `services.py`
    - Replace local vars (`kid_id`, `kid_info`, `parent_id`) with canonical role-neutral names.
    - Line-hint targets: prioritize top-audit files (`chore_manager.py`, `gamification_manager.py`, `notification_manager.py`, `statistics_manager.py`, `services.py`).
  - [ ] Batch 2D: entity/helper surfaces
    - Files: `sensor.py`, `button.py`, `select.py`, `helpers/entity_helpers.py`, `helpers/device_helpers.py`
    - Remove runtime role-bucket wording and ensure capability-based naming remains.
    - Line-hint targets: top `kid_id` usage clusters in `sensor.py`/`button.py` plus helper lookups in `entity_helpers.py`.
- **Key issues**
  - Migration modules are allowed exceptions; runtime modules are not.

### Phase 3 – Wrapper and compatibility elimination

- **Goal**: Remove hard-fork-prohibited wrappers and compatibility aliases from runtime.
- **Steps / detailed work items**
  - [ ] Remove compatibility alias blocks and wrapper methods in runtime modules
    - Priority files from audit: `helpers/flow_helpers.py`, `const.py`, `options_flow.py`, `services.py`, `data_builders.py`.
  - [ ] Isolate all remaining legacy constants to migration-only module
    - File: `custom_components/choreops/migration_pre_v50_constants.py`
    - No runtime access to these constants outside migration paths.
  - [ ] Remove label-only alias routes and helper bridges
    - Verify no `manage_parent` style compatibility routing remains in active flow contract.
  - [ ] Enforce no-wrapper guardrails in boundary checks
    - File: `utils/check_boundaries.py`
    - Add failure patterns for runtime alias/wrapper reintroduction.
  - [ ] Enforce service/event hard-fork lint
    - Files: `utils/check_boundaries.py`, `docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CONTRACT_LINT_BASELINE.md`
    - Block reintroduction of legacy request fields (`kid_name`, `parent_name`, dual parsing) in runtime paths.
  - [ ] Enforce class naming audit gate
    - Runtime classes should not introduce new `Kid`/`Parent`/`Linked`/`Shadow` class names for hard-fork contract surfaces.
- **Key issues**
  - Any retained wrapper must be treated as a blocker unless explicitly migration-only.

### Phase 4 – Translation and docs finalization (non-exception surfaces)

- **Goal**: Remove remaining non-exception legacy terms from active translation/docs surfaces.
- **Steps / detailed work items**
  - [ ] Clear remaining runtime English translation value debt
    - File: `custom_components/choreops/translations/en.json`
    - Replace remaining `{kid}` phrasing instances with canonical placeholders.
    - Line-hint targets: `translations/en.json` `~4842`, `~4869`.
  - [ ] Validate custom English translation files remain clean
    - Files: `translations_custom/en_dashboard.json`, `en_notifications.json`, `en_report.json`.
  - [ ] Run locale stale-key reconciliation in both translation trees
    - Files: `custom_components/choreops/translations/*.json`, `custom_components/choreops/translations_custom/*.json`
    - Remove or reconcile stale locale references to removed runtime keys.
  - [ ] Regenerate translation hygiene evidence artifact
    - Replace stale prior snapshots with current post-change counts and mismatches.
  - [ ] Top-level docs cleanup (policy scope: `docs/*.md`)
    - Files: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`, `docs/QUALITY_REFERENCE.md`, `docs/RELEASE_CHECKLIST.md`, `docs/CODE_REVIEW_GUIDE.md`.
    - Keep only policy-approved exception wording in README/wiki.
    - Line-hint targets: `DASHBOARD_TEMPLATE_GUIDE.md` `~17-29`; `ARCHITECTURE.md` `~283/325/334/341/367`; `DEVELOPMENT_STANDARDS.md` `~199/244/295/297/300`.
  - [ ] Verify intended exceptions are explicitly labeled and bounded
    - Files: `README.md`, `/workspaces/choreops-wiki/*.md`.
- **Key issues**
  - Translation key IDs may stay legacy under Policy A; wording and runtime symbols must not.

### Phase 5 – Validation, evidence, and closure

- **Goal**: Prove hard-fork completion and close the initiative cleanly.
- **Steps / detailed work items**
  - [ ] Run quality and architecture gates
    - `./utils/quick_lint.sh --fix`
    - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - [ ] Run full regression suite
    - `python -m pytest tests/ -v --tb=line`
  - [ ] Run lexical verification artifacts
    - Runtime: `grep -RInw -E 'kid|parent' custom_components/choreops --include='*.py'`
    - Docs top-level: `grep -Inw -E 'kid|parent' docs/*.md`
    - Translations: `grep -Inw -E 'kid|parent' custom_components/choreops/translations/en.json custom_components/choreops/translations_custom/en_*.json`
  - [ ] Publish final before/after inventory in this plan
    - Include residual allowed exception list and justification.
  - [ ] Publish builder handback bundle
    - changed file list by phase
    - validation command outputs
    - lexical before/after tables
    - translation orphan/stale-key report
    - explicit exception allowlist confirmation
  - [ ] Move superseded plans and this plan to `docs/completed/` after owner sign-off.
- **Key issues**
  - Completion is blocked until non-exception lexical debt reaches zero.

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

### Builder kickoff order

1. Phase 1 transfer cleanup completion markers
2. Phase 1B decision lock approvals
3. Phase 2A constants/types
4. Phase 2B flow method renames
5. Phase 2C manager/service variable normalization
6. Phase 3 wrapper elimination + guardrails
7. Phase 4 translation/docs cleanup + locale stale-key sweep
8. Phase 5 full validation and archive handoff evidence
