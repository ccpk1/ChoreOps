# Initiative Plan: Rebrand and role-model closeout alignment

## Initiative snapshot

- **Name / Code**: Rebrand + Role Model Closeout Alignment (`CHOREOPS-PROGRAM-ALIGN-001`)
- **Target release / milestone**: v0.5.0-beta5 hardening closeout
- **Owner / driver(s)**: Strategy + Integration maintainers
- **Status**: Deferred - execution transferred to `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

## Transfer notice

This plan is superseded for execution.
All remaining implementation work is tracked in:

- `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

This file remains as historical decision and policy context only.

## Historical reference-only checklist freeze

- All phase tables, progress percentages, and checklist-style items below are frozen historical snapshots.
- No unchecked item in this file is actionable execution work.
- Authoritative execution ownership is exclusively in `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`.
- Keep decision and policy evidence intact for audit traceability only.

## Transfer acknowledgment

- Transfer locked date: `2026-02-22`
- PM initials/date: `____ / ____`
- Builder lead initials/date: `____ / ____`

## Purpose

Unify conflicting status signals across active plans and define one methodical finish path for:

1. ChoreOps rebrand completion
2. User/assignee/approver model migration
3. Translation/runtime contract safety

## Terminal terminology contract (authoritative)

This section defines the required final-state language policy for runtime code, translations, and project docs.

### Required language policy

- `KidsChores` usage is restricted to:
  - migration-only compatibility context
  - legacy attribution and credits
  - explicit fun-mode naming as `KidsChores Mode`
- `kid` and `parent` must be removed from runtime-facing method names, constants, variables, translations, and core docs.
- Exception surface:
  - wiki and README are allowed to retain intentional references where explicitly documented.

### Enforcement domains

- **Runtime code**: `custom_components/choreops/**/*.py`
- **Translations**: `custom_components/choreops/translations/*.json` and `custom_components/choreops/translations_custom/*.json`
- **Core docs**: `docs/*.md` (top-level files only; subdirectories under `docs/` are excluded from lexical gate scope)
- **Intentional exception docs**:
  - `README.md`
  - wiki repository files under `/workspaces/choreops-wiki/`

### Completion meaning for this contract

- No non-exception runtime symbol or translation key/value introduces new `kid`/`parent` terminology.
- Remaining legacy terms are either:
  - migration-only compatibility identifiers with removal criteria, or
  - intentional attribution in approved exception surfaces.
- `KidsChores Mode` is the only fun attribution phrase permitted for gamification context.

## Scope

### In scope

- Active plans in `docs/in-process/`
  - `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
  - `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
  - `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
- Runtime contract surfaces
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/services.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/data_builders.py`
- Translation surfaces
  - `custom_components/choreops/translations/en.json`
  - `custom_components/choreops/translations_custom/en_*.json`

### Out of scope

- Non-English localization pipeline rollout
- New feature work outside rebrand/role-model closeout

## Evidence-based current state

### A) What is objectively complete

- Role-model behavior is broadly implemented in runtime paths:
  - options flow has canonical handlers (`async_step_add_assignee`, `edit_assignee`, `delete_assignee`) with legacy wrappers retained.
  - config flow has canonical handler path (`async_step_assignee_count`) with compatibility wrappers retained.
- Canonical service actor fields are already the underlying contract values:
  - `SERVICE_FIELD_ASSIGNEE_NAME = "assignee_name"`
  - `SERVICE_FIELD_APPROVER_NAME = "approver_name"`
  - legacy constants map to canonical values.
- Focused and full-suite validation evidence is already recorded in existing plans.

### B) What is partially complete / transitional by design

- Translation key IDs in `en.json` are still mostly legacy IDs (`kid_count`, `add_kid`, `invalid_kid`, etc.) but values are role-model wording (“Assignee”, “User”, “Approver”).
- Runtime constants and flow step IDs still reference legacy key IDs for many surfaces.
- Compatibility wrappers and aliases remain in runtime (step wrappers + legacy constant aliases), which indicates transitional state rather than hard-fork terminal state.

### C) Contradictions across plans

- `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md` marks phases complete, but its “Detailed analysis (current-state findings)” still describes pre-migration problems as if unresolved.
- `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md` marks Phase 4 at 100% while also listing open short-term gates that are effectively release-critical.
- `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md` assumes missing legacy translation IDs in `en.json`; current file now retains legacy IDs, so that premise is stale.

### D) Real blocker category (current)

The main blocker is **program alignment and contract sequencing**, not immediate translation runtime breakage:

- Translation key IDs and runtime references are currently aligned (legacy IDs retained).
- But there is no single agreed sequence for moving from transitional compatibility to terminal hard-fork naming.

## Summary table (program-level)

| Phase | Description | % | Quick notes |
|-------|-------------|---|-------------|
| Phase 1 – Status reconciliation | Normalize plan truth across three active plans | 100% | Contradictions reconciled, historical sections re-labeled, and validation gates green |
| Phase 2 – Terminology freeze | Lock final language policy and exception boundaries | 100% | Policy approved across all active plans with compatibility-window endpoint |
| Phase 3 – Runtime and translation hard-cut plan | Execute lockstep rename/removal sequencing by domain | 100% | Runtime/data, flow-contract, and translation-parity packets reconciled with compatibility-window evidence |
| Phase 4 – Documentation and exception review | Apply core-doc cleanup + intentional exception declarations | 100% | README/wiki intentional exception declarations recorded |
| Phase 5 – Archive and governance | Close plans with evidence and guardrails | 100% | Open-vs-done matrix, checklist reconciliation, and sign-off record completed |

## Methodical approach (recommended)

### Phase 1 – Status reconciliation (documentation truth pass)

**Goal**: Make all in-process plans describe the same current reality.

- [x] Update `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
  - Move legacy “current-state findings” into a historical subsection or mark as resolved.
  - Keep only unresolved blockers in “Risks / blockers”.
- [x] Update `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
  - Split “Phase complete” from “program closeout outstanding” to avoid conflicting signals.
- [x] Update `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
  - Replace stale “missing legacy IDs” premise with current alignment model:
    - legacy IDs retained + role-based wording values.

### Phase 2 – Contract freeze (decision gate)

**Goal**: Lock the end-state contract before additional edits.

- [x] Decide and document one of two policies:
  - **Policy A (recommended now)**: Keep legacy translation key IDs until terminal runtime rename wave; modernize values only.
  - **Policy B**: Rename translation key IDs now and update all runtime constants/step IDs in same wave.
- [x] Set compatibility window end schema/version for removing wrappers and alias constants.
- [x] Define “done” criteria for hard-fork closeout:
  - No runtime compatibility wrappers outside migration-only allowlist.
  - Canonical naming in constants/classes/helpers as approved.

### Phase 2 – Terminology freeze (decision gate)

**Goal**: Freeze language and exception policy before implementation waves.

- [x] Add explicit allowlist for `KidsChores` mentions with file-level scope
  - File: `docs/in-process/REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`
  - Include only: migration/legacy/credits and `KidsChores Mode` fun attribution.
- [x] Define disallowed token policy for runtime/core-doc domains
  - Files: `custom_components/choreops/**/*.py`, `custom_components/choreops/translations/**/*.json`, `docs/*.md`
  - Exclude approved exception surfaces (`README.md`, wiki files).
- [x] Record compatibility-window endpoint for migration-only legacy identifiers
  - File: `docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
  - Add line-item criteria for residual alias removal.
- [x] Approve terminal policy in all three active plans
  - Files: all three in-process plans
  - Add same decision text verbatim to prevent drift.

### Phase 3 – Runtime and translation hard-cut plan (when coding resumes)

**Goal**: Eliminate piecemeal drift with strict batch ordering.

- [x] Batch 3A: runtime symbol cleanup (`kid`/`parent` removal)
  - Files: `const.py`, `config_flow.py`, `options_flow.py`, `services.py`, `helpers/flow_helpers.py`, `data_builders.py`
  - Replace with canonical `user`/`assignee`/`approver` naming except migration-only allowlist.
  - Sequence 2/3 evidence confirms canonical assignee/approver naming is primary in active runtime surfaces, with residual legacy identifiers constrained to compatibility-window/migration-policy allowlists.
- [x] Batch 3B: translation key/value and custom translation cleanup
  - Files: `translations/en.json`, `translations_custom/en_dashboard.json`, `translations_custom/en_notifications.json`, `translations_custom/en_report.json`
  - Keep runtime contract safe while removing non-exception `kid`/`parent` language.
  - Sequence 4 parity artifact confirms policy-A lockstep contract: legacy key IDs retained for runtime safety while non-exception wording modernized.
- [x] Batch 3C: compatibility alias reduction pass
  - Files: runtime modules with wrapper methods/constants
  - Remove remaining aliases outside migration-allowed surfaces.
  - Compatibility wrappers were reduced to documented migration/contract allowlists with schema-window endpoint criteria.
- [x] Batch 3D: lexical and contract validation pass
  - Add explicit checks for disallowed terms in non-exception domains.
  - Run focused flow/service/translation regression suite.
  - Validation evidence: `./utils/quick_lint.sh --fix` passed, full regression suite passed (`1421 passed, 2 skipped, 2 deselected`), scoped mypy gate passed.

### Phase 4 – Documentation and exception review

**Goal**: Align docs to terminal naming while preserving intentional exception wording.

- [x] Core docs rename pass for non-exception files
  - Files: `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`, `docs/RELEASE_CHECKLIST.md`, active `docs/in-process/*.md`
  - Remove non-historical `kid`/`parent` language where not required.
  - Core-doc lexical gate scope is now explicitly top-level-only (`docs/*.md`) to prevent recursive archival noise while preserving active governance surfaces.
- [x] README intentional exception declaration
  - File: `README.md`
  - Add explicit note where `KidsChores` attribution is intentionally retained.
- [x] Wiki intentional exception declaration
  - Files: relevant `/workspaces/choreops-wiki/*.md`
  - Keep legacy/helpful wording where intentional and documented.
- [x] Add one cross-repo glossary note
  - File: `docs/in-process/REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`
  - Clarify canonical vs legacy phrasing rules.

### Phase 5 – Archive and governance

**Goal**: Close initiative set with auditable evidence.

- [x] Produce final “open vs done” matrix artifact.
- [x] Mark both major plans archive-ready only after cross-plan acceptance checklist passes.
- [x] Move completed plans to `docs/completed/` readiness is prepared via archive-ready patch and sign-off record (execution follows archivist workflow).
- [x] Record PM + builder lead sign-off note in sequence evidence.

## Program acceptance checklist

- [x] All three active plans agree on current state and remaining work.
- [x] Terminology policy is approved with explicit `KidsChores` and `KidsChores Mode` boundaries.
- [x] Translation contract policy (A or B) is explicitly approved.
- [x] No conflicting “100% complete” claim remains where release-blocking items are open.
- [x] Runtime/translation compatibility state is documented with exact key policy.
- [x] Non-exception surfaces contain no unresolved `kid`/`parent` naming debt in symbols or user-facing text.
- [x] Final closeout gate references a single authoritative checklist.

## Sign-off record (sequence 5)

- PM directive sign-off: approved in-session to proceed with Option 1 closeout reconciliation (`2026-02-21`).
- Builder lead execution sign-off: governance reconciliation, matrix artifact, and validation gates completed (`2026-02-21`).

## Decisions & completion check

- **Decisions captured**:
  - Approved terminal terminology policy: `KidsChores` is restricted to migration/legacy/credit references and the explicit fun label `KidsChores Mode`; `kid` and `parent` are disallowed in runtime symbols/translations/core docs outside documented migration-only compatibility and intentional README/wiki exceptions.
  - Runtime and translation surfaces must converge to `user`/`assignee`/`approver` terminology outside migration-only compatibility zones.
  - Wiki and README are intentional exception surfaces and must document any retained legacy language.
- **Completion confirmation**: `[x]` All phase gates complete and all active plans reflect the same terminal terminology contract.

## References

- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_STANDARDS.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/in-process/REBRAND_ROLEMODEL_MASTER_ORCHESTRATION_IN-PROCESS.md`
- `docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
- `docs/in-process/OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
- `docs/in-process/TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
- `docs/in-process/REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`
