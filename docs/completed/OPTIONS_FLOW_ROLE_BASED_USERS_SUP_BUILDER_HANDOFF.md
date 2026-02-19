# Role-based user flow redesign - Builder handoff

---

status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-02-20
parent_plan: OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md
handoff_from: ChoreOps Strategist
handoff_to: ChoreOps Plan Agent
phase_focus: Phase 5 release hardening closeout + lexical/translation hygiene

---

## Handoff button

[HANDOFF_TO_BUILDER_FINISH_ROLEFLOW_NOW](OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md)

## Handoff objective

Finish `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md` with all identified misses resolved, specifically:

1. complete remaining Phase 5 release-hardening tests,
2. eliminate non-migration runtime role-bucket terminology in flow surfaces,
3. complete translation hygiene across both translation trees.

This is hard-fork contract work. Do not introduce new compatibility aliases in runtime surfaces.

## Scope for this handoff

### In scope

- Plan closure work for:
  - `docs/in-process/OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/data_builders.py`
- Translation cleanup and parity in:
  - `custom_components/choreops/translations/*.json`
  - `custom_components/choreops/translations_custom/*.json`
- Test and contract-lint updates needed to enforce no regression.

### Out of scope

- New feature work outside role-flow/contract cleanup.
- Broad migration redesign beyond already approved migration modules.
- Any architecture changes not already captured in in-process plans.

## Confirmed misses to close

1. **Flow lexical debt remains high** in runtime surfaces (config/options/helpers/builders), not migration-only.
2. **Legacy step/routing residue** still appears in parts of tests and translation surfaces.
3. **Translation hygiene incomplete** across English + locale files in both trees.
4. **No final artifact proving zero stale/orphan keys** across translation surfaces.

## Execution checklist (builder)

### Package A - Runtime lexical hard-cut

- [ ] Remove role-bucket runtime terminology from flow surfaces, keeping migration exceptions only.
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/data_builders.py`
- [ ] Remove or explicitly deprecate remaining legacy flow entrypoints where canonical user path exists.
- [ ] Produce before/after lexical inventory report (same query set, same files) and attach under `docs/in-process/`.

### Package B - Translation hygiene (both trees)

- [ ] Audit canonical English keys in:
  - `custom_components/choreops/translations/en.json`
  - `custom_components/choreops/translations_custom/en_dashboard.json`
  - `custom_components/choreops/translations_custom/en_notifications.json`
  - `custom_components/choreops/translations_custom/en_report.json`
- [ ] Remove orphaned English keys not referenced by runtime contract after hard-fork cleanup.
- [ ] Scan locale files for stale references to removed English keys in both trees and reconcile.
- [ ] Attach translation hygiene artifact (orphan/stale-key report) under `docs/in-process/`.

### Package C - Tests and gates

- [ ] Close remaining Phase 5 tests in:
  - `tests/test_options_flow_entity_crud.py`
  - `tests/test_options_flow_shadow_kid_entity_creation.py`
  - `tests/test_config_flow_fresh_start.py`
- [ ] Add/adjust tests for translation coverage and user-flow contract where needed.
- [ ] Run and report:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/` (or approved repo-local equivalent when environment parser mismatch applies)
  - `python -m pytest tests/test_options_flow_entity_crud.py tests/test_options_flow_shadow_kid_entity_creation.py tests/test_config_flow_fresh_start.py -v --tb=line`

## Acceptance criteria for handoff completion

- Runtime flow surfaces use canonical user-role hard-fork terminology, with migration-only exceptions documented.
- No unresolved orphan English keys remain in either `translations/` or `translations_custom/` English files.
- No unresolved stale locale key references remain in either translation tree.
- Phase 5 in `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md` is updated to 100% with evidence.
- Builder returns changed-file list + test/gate output summary + audit artifact links.

## Required handback payload from builder

1. Changed files list grouped by package (A/B/C).
2. Lexical inventory artifact link (before/after).
3. Translation hygiene artifact link (English orphan + locale stale references).
4. Test/gate command output summary.
5. Updated percent/status entries in `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`.
