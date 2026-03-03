# Hard fork rebase major efforts summary

## Scope

- Review window: commits after `8682d3f4ddfe79c2d6ab826680b465b5a85af110` through `HEAD`
- Total commits reviewed: 54
- Goal: identify major effort buckets for an interactive rebase cleanup
- Exclusion applied: `kidschores`/legacy-kidschores content is not used as a planning signal

## Executive recommendation

If you choose to do an interactive rebase for cleanup, compress the 52 commits into **10 major commits** that track true milestones (architecture, user model, dashboard pipeline, state contracts, and release readiness), not incremental fixups.

## Proposed clean commit set (interactive rebase target)

### Commit 1

`chore(branding): complete ChoreOps rebrand foundation and release metadata`

- Consolidates early rebrand and brand asset readiness work
- Source commits (ordered):
  - `4789fa6` refactor(rebrand): complete ChoreOps rename cleanup and release validation
  - `a683a6b` chore(branding): prepare HACS and brand-asset readiness
  - `4433c59` feat(rebrand): ChoreOps rebrand progress
  - `ef94769` feat(rebrand-orchestration): execute sequences 1–5 foundations

### Commit 2

`feat(gamification): unify target tracking scope and closeout`

- Unifies gamification target scope and supporting behavior adjustments
- Source commits:
  - `40e7296` feat(gamification): unify target scope and archive plan
  - `842c641` fix: chore handling fixes and logic improvements
  - `0c42c76` fix: rotation chore logic fixes and improvements
  - `5ac5d94` fix: chore logic fixes

### Commit 3

`refactor(unification): complete user-first role model and strict terminology`

- Executes hard-fork terminology and role model unification
- Source commits:
  - `3cf9e9e` refactor(unification): retire shadow-link service path
  - `1a2227a` feat(unification): complete users-first roleflow hardfork
  - `628abc9` chore(plan): consolidate hard-fork completion into single execution plan
  - `fce43ed` refactor(terminology): finalize strict consts
  - `54e3307` refactor(role-gating): unify user-first gating model
  - `c6f4121` feat: user first item roles initial phases
  - `8330570` refactor(events): standardize user payload contracts
  - `3a0f2c1` chore: update services to assigned_user_names and assigned_user_ids

### Commit 4

`feat(multi-instance): harden entry isolation and options-flow correctness`

- Delivers multi-instance boundary safety and chore form persistence correctness
- Source commits:
  - `7eddc7f` feat(multi-instance): harden entry-scoped isolation across ChoreOps
  - `3acaf65` fix(options-flow): preserve chore edit values in sectioned forms
  - `334fb05` fix(store): validate storage payloads before save
  - `57b1b97` fix(storage): harden schema handling across store and migration

### Commit 5

`feat(dashboard): establish manifest-driven dashboard registry pipeline`

- Introduces dashboard registry architecture, dependency checks, and richer template details
- Source commits:
  - `ccdd5f3` feat(dashboard-registry): ratify architecture and remediate gaps through R4
  - `a9b2ec4` feat(dashboard): enforce manifest-driven card dependency checks
  - `2ad0a09` feat(dashboard): add template details review with descriptions and preference docs
  - `280c630` feat: version standarizations and dashboard generator improvements
  - `388194f` feat(dashboard-generator): harden release execution and complete registry migration

### Commit 6

`chore(l10n): stabilize translation and crowdin sync workflows`

- Consolidates localization and translation automation correctness
- Source commits:
  - `a27dcb5` chore: update crowdin files
  - `690d81a` il10: crowdin changes
  - `33123a8` chore(il10): translation updates
  - `4525897` fix(l10n): translation scripts
  - `99ab129` l10n: test
  - `fa761ef` chore(l10n): sync translations from Crowdin
  - `12396aa` fix(l10n): translation scripts
  - `043ea6a` Merge pull request #2 from ccpk1/l10n_crowdin_action
  - `97b8d4e` fix(l10n): dashboard translation sync
  - `45f22c1` chore(l10n): sync translations from Crowdin
  - `5fad8e1` Merge pull request #3 from ccpk1/l10n_crowdin_action
  - `5269cc0` chore(l10n): sync translations from Crowdin
  - `5a114de` Merge pull request #4 from ccpk1/l10n_crowdin_action

### Commit 7

`docs(governance): standardize repo governance and automation hygiene`

- Applies pre-launch governance and documentation structure cleanup
- Source commits:
  - `4903518` refactor(governance): pre-launch docs, templates, labels, and workflow hygiene
  - `a9d61b5` doc(governance): repo documentation
  - `e35415c` doc: added hacs link

### Commit 8

`feat(chore-state): roll out completed-state signal and contract hardening`

- Establishes completed-state contract and verifies signal behavior
- Source commits:
  - `586a39e` feat(chore-state): complete Phase 1–5 state contract rollout
  - `7625e16` chore: added chore signal tests and audit
  - `31661da` fix(dashboard): keep current-installed local-only

### Commit 9

`feat(core-options): add configurable default chore points and challenge sunset`

- Introduces default chore points option and closes challenge sunset initiative
- Source commits:
  - `3585b31` fix: retrofit and refactor templates and achievement and challenges handling
  - `0d3e8fa` chore(challenge-sunset): complete Phase 0-current initiative closure
  - `d3863f0` feat(choreops): add configurable default chore points end-to-end

### Commit 10

`feat(dashboard-metadata): standardize metadata stamping for release artifacts`

- Completes dashboard metadata stamping and release alignment
- Source commit:
  - `6e5ee7e` feat(dashboard-metadata): complete stamping standardization rollout and archive plan

## Mapping to completed plans (non-kidschores)

Major effort groups were matched to completed plans added in this range:

- Rebrand + terminology + hard-fork closeout
  - `docs/completed/CHOREOPS_FULL_REBRAND_COMPLETED.md`
  - `docs/completed/HARD_FORK_TERMINOLOGY_FINALIZATION_COMPLETED.md`
  - `docs/completed/CHOREOPS_DATA_MODEL_UNIFICATION_COMPLETED.md`
  - `docs/completed/STRICT_CONST_TERMINOLOGY_ZERO_EXCEPTION_CLOSEOUT_COMPLETED.md`
  - `docs/completed/REBRAND_ROLEMODEL_CLOSEOUT_COMPLETED.md`

- User-first role model and unification evidence pack
  - `docs/completed/user-unification/USER_FIRST_ITEM_ROLE_CONTRACT_HARD_FORK_EXECUTION_IN-PROCESS.md`
  - `docs/completed/user-unification/USER_ROLE_MODEL_DRIFT_ANALYSIS_IN-PROCESS.md`
  - `docs/completed/user-unification/USER_ROLE_MODEL_DRIFT_ANALYSIS_SUP_FACT_TABLE.md`

- Multi-instance hardening
  - `docs/completed/MULTI_INSTANCE_HARDENING_COMPLETE.md`
  - `docs/completed/MULTI_INSTANCE_HARDENING_SUP_PHASE1_EXECUTION.md`
  - `docs/completed/MULTI_INSTANCE_HARDENING_SUP_PHASE2_DEEP_DIVE.md`
  - `docs/completed/MULTI_INSTANCE_HARDENING_SUP_TEST_STRATEGY.md`

- Dashboard architecture and registry generation
  - `docs/completed/DASHBOARD_REGISTRY_GENERATION_COMPLETED.md`
  - `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
  - `docs/completed/DASHBOARD_RELEASE_DOWNLOAD_RELIABILITY_COMPLETED.md`
  - `docs/completed/DASHBOARD_FLOW_UX_REWORK_COMPLETED.md`

- Chore state and signal contracts
  - `docs/completed/CHORE_STATUS_COMPLETED_ALIAS_SENSOR_ONLY_COMPLETED.md`
  - `docs/completed/CHORE_SIGNAL_CONTRACT_HARDENING_TESTS_COMPLETED.md`
  - `docs/completed/CHORE_SIGNAL_CONTRACT_AUDIT_POST_COMPLETED_COMPLETED.md`

- Default points and challenge sunset
  - `docs/completed/DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md`
  - `docs/completed/CHALLENGE_SUNSET_COMING_SOON_COMPLETED.md`

- Dashboard metadata stamping
  - `docs/completed/DASHBOARD_METADATA_STAMPING_STANDARDIZATION_COMPLETED.md`

## Suggested interactive rebase workflow

### Safety protections in place

Pre-rebase protections were created and verified before any history rewrite:

- Backup branch: `backup/pre-rebase-hardfork-20260303-010044` (points to pre-rebase `HEAD`)
- Annotated tag: `pre-rebase-hardfork-20260303-010044`
- Full offline bundle: `.git/rebase-safety/pre-rebase-hardfork-20260303-010044.bundle`
- Snapshot marker: `.git/rebase-safety/latest_snapshot.txt`

### Plan B rollback options

- Fast local rollback to the exact pre-rebase state:
  - `git reset --hard backup/pre-rebase-hardfork-20260303-010044`
- Rollback using the annotated tag:
  - `git reset --hard pre-rebase-hardfork-20260303-010044`
- Recover even if local refs are damaged (clone/import from bundle):
  - `git clone .git/rebase-safety/pre-rebase-hardfork-20260303-010044.bundle choreops-recovery`
- Recover via reflog if needed:
  - `git reflog`
  - `git reset --hard <reflog-sha>`

1. Confirm pre-created safety artifacts exist (branch/tag/bundle)
  - `git show-ref --verify refs/heads/backup/pre-rebase-hardfork-20260303-010044`
  - `git show-ref --verify refs/tags/pre-rebase-hardfork-20260303-010044`
2. Start interactive rebase from the hard-fork point
   - `git rebase -i 8682d3f4ddfe79c2d6ab826680b465b5a85af110`
3. Keep one commit per major effort (10 targets above)
   - Mark first commit in each bucket as `pick`, remaining as `squash`/`fixup`
4. Use final commit messages from this document (edit in rebase todo)
5. Validate before push
   - `./utils/quick_lint.sh --fix`
   - `mypy custom_components/choreops/`
   - `python -m pytest tests/ -v --tb=line`
6. Push safely
   - `git push --force-with-lease`

## Notes and caveats

- This rewrite is safest only if all active consumers can tolerate history rewrite.
- Merge commits from Crowdin sync branches were intentionally grouped into localization stabilization.
- If you want a lower-risk rewrite, keep commits 8–10 separate and only squash commits 1–7.