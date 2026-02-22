# Supporting Doc: ChoreOps rename contract catalog (hard-fork)

## Purpose

Track and approve all rename decisions beyond service/event payloads:

- Data field contracts
- Translation key and translation text contracts
- Method/helper/API naming contracts

This is the authoritative tracker for rename coverage and implementation order.

## Final audit gate usage

This document is the required final audit gate artifact for the unification plan.
Before plan sign-off, all checklist items and execution batches here must be
reviewed and marked complete or explicitly deferred with owner approval.

End-of-plan audit outcome should be recorded here first, then summarized in the
main in-process plan.

## Policy boundary

- Architecture docs define canonical current-state architecture.
- This document carries transitional mapping and implementation sequencing details.
- Runtime hard-fork policy applies: no new legacy alias parsing in runtime paths.
- Runtime simplification policy applies: migration-only constants stay isolated in
  `custom_components/choreops/migration_pre_v50_constants.py`.
- Production/runtime modules should keep only minimal migration invocation hooks so
  pre-v50 support can be removed in a future release with low effort.

## Scope

- In scope:
  - Runtime/service/event request field renames (linked from service/event mapping doc)
  - Data model symbol renames in constants, TypedDicts, and runtime helpers
  - Translation key and user-facing text renames tied to role-based terminology
  - Helper/method naming alignment away from kid/parent role-bucket assumptions
  - Config/options/helper/builder runtime lexical cleanup for hard-fork terminology
  - Translation orphan-key/stale-reference cleanup in both `translations/` and `translations_custom/`
- Out of scope:
  - Historical migration internals not affecting runtime/API contract
  - Dashboard repository content ownership details (tracked separately in release/migration notes)

## Related documents

- Service/event mapping contract:
  - CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md
- Main initiative plan:
  - CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md

## Locked naming principles

1. Actor role terms in runtime request/event contracts:
   - assignee
   - approver
2. Capability terms remain explicit and separate:
   - can_be_assigned
   - can_approve
   - can_manage
3. Avoid role-bucket terminology in new runtime contracts:
   - no new kid*\* / parent*\* request/event keys
4. Name-based request fields remain available for user-facing service calls.
5. ID fields may remain supported but are secondary for user-facing guidance.
6. `linked_*` terminology must be eliminated from runtime by plan completion; it may
   remain only in migration code or persisted legacy-key handling.
7. If migration is implemented correctly, runtime compatibility helper usage is not
   required; compatibility helper logic should be migration-only.
8. Runtime flow/config/helper/data-builder surfaces must not carry new or retained
   role-bucket terminology (`kid`, `parent`, `kidschores`) outside migration-only
   allowlisted paths.
9. Translation hygiene is mandatory at plan completion: no orphaned English keys and
   no stale locale references to removed runtime keys across both translation trees.

## Class naming expectations (added)

These expectations apply to production runtime code after the hard-fork cleanup.

| Class category            | Required naming expectation    | Notes                                                                          |
| ------------------------- | ------------------------------ | ------------------------------------------------------------------------------ |
| Managers                  | `[Domain]Manager`              | Keep role-neutral domain naming (`UserManager`, not role-bucket classes)       |
| Home Assistant entities   | `[Scope][Feature][EntityType]` | Avoid new `Kid`/`Parent` role-bucket class names for runtime contract surfaces |
| TypedDict/data contracts  | Role-neutral model names       | Prefer `User*` and capability-oriented names over split-role class naming      |
| Migration classes/helpers | Legacy naming allowed          | Only in migration modules or migration-specific tests                          |

Additional enforcement:

- Do not introduce new runtime classes containing `Linked`, `Shadow`, `Kid`, or
  `Parent` when the class represents hard-fork contract behavior.
- Existing runtime classes with these terms should be queued for final-phase rename
  or removal before plan sign-off.

## Rename catalog

### A) Service/event contract fields (authoritative link)

Use the dedicated mapping file for exact field-by-field service/event cutover.
Do not duplicate that matrix here.

### B) Data model constants and storage/runtime symbols

Status legend:

- locked: approved direction
- removal: symbol should be removed from runtime
- pending: needs explicit decision

| Area                                              | Legacy symbol/pattern                                            | Target symbol/pattern                                     | Status  | Notes                                                 |
| ------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------- | ------- | ----------------------------------------------------- |
| Parent linked profile constants in runtime        | DATA_PARENT_LINKED_PROFILE_ID / DATA_PARENT_LINKED_SHADOW_KID_ID | remove from runtime constants                             | removal | Keep legacy key handling only in migration layer      |
| Linked profile marker in runtime records          | DATA_KID_IS_SHADOW                                               | remove from runtime model semantics                       | removal | Migration may still read legacy marker                |
| Linked parent pointer in runtime records          | DATA_KID_LINKED_PARENT_ID                                        | remove from runtime model semantics                       | removal | Replace with capability/role-driven logic             |
| Migration-only constants location                 | mixed legacy constants in runtime modules                        | move to `migration_pre_v50_constants.py`                  | locked  | Runtime should not retain legacy constant definitions |
| kid/parent collection naming in runtime contracts | kid/parent role bucket wording                                   | user/capability wording                                   | locked  | Continue Phase 3/4 cleanup pass                       |
| Service field constants                           | SERVICE_FIELD_KID_NAME / SERVICE_FIELD_PARENT_NAME               | SERVICE_FIELD_ASSIGNEE_NAME / SERVICE_FIELD_APPROVER_NAME | locked  | Implement in hard-fork cutover wave                   |
| Service ID constants                              | SERVICE_FIELD_KID_ID / parent ID equivalents                     | SERVICE_FIELD_ASSIGNEE_ID / SERVICE_FIELD_APPROVER_ID     | locked  | Keep supported with name-first guidance               |

### C) Translation keys and user-facing copy

| Area                                            | Legacy pattern                                     | Target pattern                                 | Status  | Notes                                                  |
| ----------------------------------------------- | -------------------------------------------------- | ---------------------------------------------- | ------- | ------------------------------------------------------ |
| Service field labels/help text                  | kid/parent actor wording in service docs           | assignee/approver actor wording                | locked  | Must align with service field cutover                  |
| Service schema docs                             | old key names in service docs                      | new key names in `services.yaml`               | locked  | Must be updated in same PR wave as handler changes     |
| Translation text                                | old actor terms in user-facing text                | assignee/approver and capability wording       | locked  | Update `translations/en.json` with contract cutover    |
| Flow titles and section headers                 | Kid/Parent labels for role semantics               | user/role-capability language where applicable | pending | Keep readability for setup UX; avoid user confusion    |
| Error keys mentioning shadow/linked semantics   | `shadow_*` / `linked_*` runtime-facing keys        | remove or replace with role/capability keys    | pending | Remove runtime-facing linked terminology by plan end   |
| Existing translation keys with kid/parent names | keep key names, update display text OR rename keys | explicit per-key decision                      | pending | Decide if key IDs are stable-internal or user-contract |

### D) Method/helper/API names

| Area                                             | Legacy pattern                           | Target pattern                       | Status  | Notes                                                               |
| ------------------------------------------------ | ---------------------------------------- | ------------------------------------ | ------- | ------------------------------------------------------------------- |
| Linked/shadow helper names in runtime            | `*_linked_*` / `*_shadow_*` helper names | remove from runtime helper API       | removal | Keep compatibility helpers only where migration-bound and temporary |
| Service handlers using parent/kid variable names | parent_name / kid_name locals            | approver_name / assignee_name locals | pending | Apply in service cutover PRs                                        |
| Notification parser data fields                  | parsed.kid_id                            | parsed.assignee_id                   | locked  | Same wave as notification contract cutover                          |

## Required decision log (must complete before full implementation)

### Decision D1: Translation key migration policy

Choose one:

- Option A: keep existing translation key IDs, update display text only
- Option B: rename translation key IDs for role-neutral consistency

Current recommendation:

- Option A for this hard-fork wave to minimize translation churn risk,
  while updating visible text to approved terminology.

### Decision D2: Internal data constant migration depth in this wave

Choose one:

- Option A: contract-surface first (service/event/helper names), defer deep DATA\_\* constant rename
- Option B: broad DATA\_\* rename now (larger migration scope)

Current recommendation:

- Option A in this wave, with explicit backlog line items for deep constant migration.

### Decision D4: Linked-term runtime elimination gate

Choose one:

- Option A: enforce full runtime removal by plan completion (migration-only allowance)
- Option B: keep linked-term runtime symbols longer

Current recommendation:

- Option A.

### Decision D3: Legacy helper alias removal timing

Choose one:

- Option A: remove aliases in same hard-fork implementation wave
- Option B: keep aliases until next schema migration milestone

Current recommendation:

- Option A. Runtime compatibility helper aliases should be eliminated; keep any
  legacy helper behavior only in migration modules.

### Decision D5: Translation orphan-key policy

Choose one:

- Option A: strict removal of orphaned keys in `en.json` and locale files in same wave
- Option B: keep deprecated keys for one additional milestone

Current recommendation:

- Option A. Hard-fork release should close with zero orphaned/stale translation keys.

## Implementation sequence (recommended)

1. Finalize and approve service/event mapping contract.
2. Execute service/event/notification field cutover.
3. Align translation text for impacted services/events in same PR wave.
4. Apply helper/method variable renames in touched modules.
5. Remove linked-term runtime symbols and aliases outside migration modules.
6. Add contract-lint guards for legacy request/event field reintroduction.
7. Execute flow/config/helper/builder lexical hard-cut and remove runtime role-bucket terms.
8. Run translation hygiene pass (`en.json` + locale files) and remove orphan/stale keys.
9. Schedule deeper data-constant rename pass after contract-surface stabilization.
10. Run final-phase contract test proving zero runtime compatibility-helper reliance.

## Approval checklist

- [x] D1 translation key policy approved
- [x] D2 data constant migration depth approved
- [x] D3 helper alias removal timing approved
- [x] D4 linked-term runtime elimination approved
- [x] D5 translation orphan-key policy approved
- [x] Service/event mapping contract approved
- [x] Translation update scope approved
- [x] Method/helper rename scope approved

Approval lock record (2026-02-22):

- D1: Option A
- D2: Option A
- D3: Option A
- D4: Option A
- D5: Option A
- Approved by: `CCPK1` (PM lock)

## Execution tracking

### Batch 1: Contract surface

- [ ] constants: service/event field constants
- [ ] services.py schemas/handlers
- [ ] notification_action_handler.py parsing/dispatch
- [ ] services.yaml field docs

### Batch 2: Translation alignment

- [ ] translations/en.json impacted service/event labels and descriptions
- [ ] translation keys/texts updated per approved policy and synced with new contract naming
- [ ] services.yaml and translations/en.json validated for key/text parity with runtime handlers
- [ ] orphan-key audit completed for `translations/en.json` (runtime key inventory vs actual keys)
- [ ] orphan-key audit completed for `translations_custom/en_dashboard.json`, `en_notifications.json`, and `en_report.json`
- [ ] stale-key audit completed for all locale files in `custom_components/choreops/translations/`
- [ ] stale-key audit completed for all locale files in `custom_components/choreops/translations_custom/`
- [ ] release notes migration examples
- [ ] README migration snippets

### Batch 3: Helper/method cleanup

- [ ] helper alias call-site cleanup
- [ ] local variable naming cleanup in service handlers/managers
- [ ] remove deprecated helper aliases approved for same-wave removal
- [ ] remove `linked_*` runtime symbols and helper names (migration-only exceptions documented)

### Batch 4: Guardrails and tests

- [ ] contract-lint rules for legacy field patterns
- [ ] contract-lint rules for legacy runtime lexical patterns in flow/config/helper/builder surfaces
- [ ] mixed-role scenario matrix tests
- [ ] hard-fork regression suite updates
- [ ] final-phase proof: no runtime compatibility-helper usage outside migration modules
- [ ] final-phase proof: class naming contract satisfied (no new runtime role-bucket class names)

### Batch 5: Final audit evidence

- [ ] lexical inventory artifact attached (before/after counts by file)
- [ ] translation hygiene artifact attached (English orphan keys + locale stale-key scan)
- [ ] migration-only allowlist documented and approved
