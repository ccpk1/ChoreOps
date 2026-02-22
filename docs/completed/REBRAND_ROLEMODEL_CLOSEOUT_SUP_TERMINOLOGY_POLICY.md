# Supporting Plan: Rebrand closeout terminology policy

## Purpose

Define enforceable, file-scoped terminology rules for the final hard-fork closeout so implementation teams can execute without ambiguity.

## Policy matrix

| Domain                                              | Allowed canonical terms                   | Allowed legacy terms                                                               | Disallowed terms                                                   | Notes                                                                |
| --------------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------- |
| Runtime code (`custom_components/choreops/**/*.py`) | `user`, `assignee`, `approver`, `manager` | `kid`/`parent` only in migration-only compatibility surfaces with removal criteria | New runtime symbols/methods/constants using `kid` or `parent`      | Migration files are temporary; must include removal gates            |
| Runtime translations (`translations/*.json`)        | `user`, `assignee`, `approver` wording    | legacy key IDs only during approved compatibility window                           | New non-compatibility key/value language using `kid` or `parent`   | Key-ID policy follows closeout plan decision gate                    |
| Custom translations (`translations_custom/*.json`)  | Same as runtime translations              | Legacy attribution where approved                                                  | Casual/leftover `kid`/`parent` wording outside approved exceptions | Includes dashboard/notifications/report surfaces                     |
| Core docs (`docs/*.md`, top-level only)            | Canonical role model terms                | Historical references in archived/completed docs                                   | New active-plan/core-doc wording centered on `kid`/`parent`        | Subdirectories under `docs/` are excluded from this lexical gate     |
| README (`README.md`)                                | Canonical terms preferred                 | Explicitly intentional `KidsChores` attribution                                    | Unexplained legacy carryover                                       | Must include clear note for intentional legacy attribution           |
| Wiki (`/workspaces/choreops-wiki/*.md`)             | Canonical terms preferred                 | Intentional explanatory legacy terms                                               | Unreviewed drift or inconsistent mixed terminology                 | Wiki is an intentional exception surface with review-based retention |

## Explicit `KidsChores` rules

- `KidsChores` usage is allowed only when referring to:
  - migration compatibility
  - legacy attribution/credit
  - fun gamification attribution as `KidsChores Mode`
- `KidsChores Mode` is the only approved fun-context phrase.
- Any other new `KidsChores` usage requires explicit plan-level approval before merge.

## Cross-repo glossary note

- Canonical wording for active runtime/docs/translations: `user`, `assignee`, `approver`.
- Legacy wording (`kid`, `parent`, `KidsChores`) is allowed only in approved exception or compatibility contexts:
  - migration-compatibility contracts,
  - legacy attribution/credits,
  - README/wiki intentional exception language,
  - compatibility key IDs governed by lockstep translation policy.

## Execution checklist (builder handoff)

### Phase A – Inventory

- [ ] Build lexical inventory of `kid|parent|KidsChores` across runtime, translations, and docs.
- [ ] Tag each hit as: `migration-only`, `intentional exception`, `requires rename`, or `historical archive`.
- [ ] Publish inventory artifact for PR reviewers.

### Phase B – Runtime and translation cleanup

- [ ] Remove/rename non-exception runtime symbols and local variables using `kid`/`parent`.
- [ ] Align translation values to canonical role language while preserving approved key-contract behavior.
- [ ] Clean `translations_custom` files to remove non-exception legacy wording.

### Phase C – Documentation cleanup and declaration

- [ ] Update core docs and active plans to canonical language.
- [ ] Add explicit intentional-attribution note in `README.md` where `KidsChores` is retained.
- [ ] Validate wiki pages that intentionally retain legacy terms include clear contextual framing.

### Phase D – Validation and gates

- [ ] Run quality gates and focused regression suites.
- [ ] Run lexical gate to ensure non-exception domains are clean.
- [ ] Record final evidence in closeout plan and archive gate.

## Validation commands (execution phase)

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/`
- `python -m pytest tests/ -v --tb=line`
- `grep -RInE '\bkid\b|\bparent\b|KidsChores' custom_components/choreops custom_components/choreops/translations custom_components/choreops/translations_custom README.md docs/*.md`

## Decision references

- `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`
- `CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`
- `OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`
- `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`
