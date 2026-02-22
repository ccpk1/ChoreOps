# Initiative Plan: Rebrand role-model master orchestration

## Initiative snapshot

- **Name / Code**: Rebrand Role-Model Master Orchestration (`CHOREOPS-PROGRAM-MASTER-001`)
- **Target release / milestone**: v0.5.0-beta5 hardening closeout
- **Owner / driver(s)**: Project manager + builder lead + strategy owner
- **Status**: Deferred - execution transferred to `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

## Transfer notice

This plan is superseded for execution.
All remaining implementation work is tracked in:

- `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

This file remains as historical governance context only.

## Purpose

Provide one operating guide so PM and builder can use the four plans without overlap, contradiction, or lost context.

## The 4-plan stack (single-source hierarchy)

1. **Program authority**: `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`
   - Owns sequence, acceptance gates, and final archive decision.
2. **Runtime/data contract**: `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
   - Owns schema/runtime/model hard-fork tasks.
3. **Flow UX contract**: `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
   - Owns config/options user-flow behavior and validation.
4. **Translation contract**: `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
   - Owns runtime-to-translation key parity and migration safety.

Supporting policy used by all four plans:

- `REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`

## Scope and terminology guardrails

- `KidsChores` usage allowed only for migration, legacy attribution/credits, and fun attribution as `KidsChores Mode`.
- `kid` and `parent` must be removed from runtime method names, constants, variables, translations, and core docs.
- Intentional exception surfaces: `README.md` and wiki files in `/workspaces/choreops-wiki/`.

## Sequencing model (must follow in order)

| Sequence | Plan owner | What happens | Entry gate | Exit gate |
|---|---|---|---|---|
| 0 | Program authority | Reconcile contradictory status claims across plans | All four plans listed and linked | One agreed “current state” statement in each plan |
| 1 | Program authority + policy | Freeze terminology + compatibility policy | Sequence 0 complete | Policy text approved in all four plans |
| 2 | Data model plan | Runtime symbol and model hard-cut batches | Sequence 1 complete | Runtime naming debt closed or explicitly migration-tagged |
| 3 | Flow plan | Config/options flow contract alignment and wrapper reduction | Sequence 2 complete | Flow tests pass; no label-only alias routes remain |
| 4 | Translation plan | Runtime key parity and translation cleanup in lockstep | Sequence 3 complete | Zero missing runtime keys; terminology policy satisfied |
| 5 | Program authority | Docs exception review + archive decision | Sequence 4 complete | Acceptance checklist fully checked |

## Sequence progress and phase dependencies

Use this table as the PM advancement gate. A sequence is only complete when all required plan-phase checks for that row are complete.

| Sequence | Required plan/phase completion | Progress status | Evidence required to advance |
|---|---|---|---|
| 0 | `REBRAND_ROLEMODEL_CLOSEOUT`: Phase 1 (status reconciliation) complete; conflicting claims removed from all active plans | ☑ Complete | Cross-plan contradiction log + updated status text in each plan |
| 1 | `REBRAND_ROLEMODEL_CLOSEOUT`: Phase 2 (terminology freeze) complete; terminology policy approved in all four plans | ☑ Complete | Policy approval notes + explicit `KidsChores`/`KidsChores Mode` boundary confirmations |
| 2 | `CHOREOPS_DATA_MODEL_UNIFICATION`: runtime/model hard-cut phase complete for current batch scope; migration-only exceptions tagged | ☑ Complete | Runtime symbol rename/removal changelog + focused runtime regression results |
| 3 | `OPTIONS_FLOW_ROLE_BASED_USERS`: flow contract phase complete for current batch scope; wrapper reduction completed per gate | ☑ Complete | Config/options flow matrix + focused flow test evidence |
| 4 | `TRANSLATION_CONTRACT_REALIGNMENT`: Phase 1-3 completion for active wave (inventory, parity, lockstep mapping) | ☑ Complete | Translation mismatch inventory + zero-missing-runtime-key report + targeted tests |
| 5 | `REBRAND_ROLEMODEL_CLOSEOUT`: Phase 4/5 closeout governance execution | ☑ Complete | Final open-vs-done matrix + PM and builder lead sign-off |

### Advancement rule

- A sequence may advance only when:
   - its row is marked **Complete**,
   - required evidence is linked in the owning plan,
   - and no downstream plan reports a blocking contradiction.

### Current progress snapshot (update daily)

- Active sequence index: `5` complete
- Current owner: `Project manager + strategy owner`
- Blockers: `None (archive-ready patch prepared)`
- Next evidence checkpoint: `Archive/move decision and completed-plan handoff`

## PM operating instructions

### Daily control loop

- Start at the program authority plan and confirm which sequence index is active.
- Permit builder work only for the current sequence index.
- Reject out-of-order work unless blocker escalation is documented.
- Require same-day updates to:
  - current sequence status
  - risks/blockers
  - entry/exit evidence links

### Required artifacts per sequence

- Sequence 0: contradiction log and reconciled wording updates
- Sequence 1: frozen terminology policy decision record
- Sequence 2: runtime rename/removal changelog + targeted regression evidence
- Sequence 3: flow matrix evidence (config/options routes and wrappers)
- Sequence 4: translation parity inventory and mismatch report
- Sequence 5: final open-vs-done matrix and archive approval note

## Builder operating instructions

### Work packet contract (for every PR batch)

- **Packet header**: sequence index + plan name + specific phase/step IDs
- **Scope**: max 1 domain per packet (runtime, flow, translation, docs)
- **Evidence**:
  - changed files list
  - test/lint/mypy outcomes
  - terminology policy check outcome
- **Decision trace**: any exception must reference the policy file and approval note

### Stop conditions (do not continue batch)

- A plan conflict is discovered (status says complete but unresolved blocker exists)
- A translation key change is proposed without runtime lockstep mapping
- A runtime rename introduces new legacy aliases outside migration scope
- README/wiki legacy wording is changed without explicit “intentional exception” note

## Anti-confusion rules

- Only one active sequence index at a time.
- Only the program authority plan can advance sequence index.
- Sub-plans cannot self-declare program completion.
- If any sub-plan conflicts with program authority, program authority wins and sub-plan must be patched.
- Archive is blocked until all four plans have matching completion language.

## Program acceptance checklist

- [x] Sequence 0 through 5 completed in order
- [x] All four plans contain consistent status and completion statements
- [x] Terminology policy enforced in runtime, translations, and core docs
- [x] Intentional exceptions limited to README/wiki and documented
- [x] Runtime/translation lockstep evidence attached
- [x] Final open-vs-done matrix approved by PM and builder lead

## References

- `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`
- `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
- `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
- `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
- `REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`
