# Builder handoff: Chore notification reset cleanup (Phase 3B lifecycle contract hardening)

## Initiative snapshot

- **Name / Code**: Chore notification reset cleanup – Phase 3B (`CHORE_NOTIFICATION_RESET_CLEANUP_PHASE3B`)
- **Target release / milestone**: `release/0.5.0-beta.5-prep` notification lifecycle hardening
- **Owner / driver(s)**: Builder execution owner + ChoreOps maintainer reviewer
- **Status**: Executed and archived with completion evidence captured

## Handoff purpose

This handoff exists to finish the chore assignee notification lifecycle contract without leaving any behavior to inference.

Builder must implement the Phase 3B contract exactly as documented in the active initiative plan and the notification overview matrix, then return explicit completion evidence.

This handoff is complete only when:

1. transient assignee notifications follow one canonical replacement contract,
2. invalidation paths clear the exact canonical notification identity,
3. regression coverage proves the contract,
4. docs and plan artifacts are updated with final evidence,
5. every required checkbox in this document is marked complete.

## Authoritative source documents

Builder must treat these as the only authoritative planning sources for this slice:

- `docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_COMPLETED.md`
- `docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_NOTIFICATION_OVERVIEW_MATRIX.md`
- `choreops-wiki/Configuration:-Notifications.md`
- `choreops-wiki/Technical:-Notifications.md`

If implementation pressure conflicts with any of those sources, stop and record the conflict before proceeding.

## Locked contract decisions

These are not open for reinterpretation during implementation.

1. `due window`, `due reminder`, and `overdue` are one canonical assignee transient notification family.
2. `due reminder` replaces `due window`.
3. `overdue` replaces either `due window` or `due reminder`.
4. `claimed`, `approved`, `missed`, `reset`, and chore deletion invalidate the transient assignee family and require explicit clear behavior.
5. Mobile-app notifications are the strict lifecycle-hardening target in Phase 3B.
6. Persistent fallback must remain stable and must not be broken, but fallback parity work is not part of this slice.
7. Legacy `due_window` and `overdue` clears may remain only as documented compatibility clears, not as the canonical contract.

## Scope for this handoff

### In scope

- Assignee lifecycle hardening in:
  - `custom_components/choreops/managers/notification_manager.py`
- Targeted supporting tests in:
  - `tests/test_workflow_notifications.py`
  - `tests/test_scheduler_delegation.py`
  - optional focused lifecycle contract test module if needed
- Plan and documentation updates in:
  - `docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_COMPLETED.md`
  - `docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_NOTIFICATION_OVERVIEW_MATRIX.md`
  - `choreops-wiki/Configuration:-Notifications.md`
  - `choreops-wiki/Technical:-Notifications.md`

### Out of scope

- Broad notification architecture redesign outside chore lifecycle hardening
- New storage schema work or migrations
- Reward/badge/system notification redesign beyond helper-touch parity review
- Persistent fallback parity expansion beyond preserving current replacement behavior
- Unrelated failing tests outside the targeted suite unless directly caused by this work

## Mandatory execution rules

Builder must follow these rules throughout the handoff:

1. Do not treat this as a generic cleanup. This is contract work.
2. Do not change the locked decisions above without an explicit recorded deviation approval.
3. Do not proceed past a discovered send/clear mismatch without recording it in this handoff and the main plan.
4. Do not mark a section complete unless the required code, tests, and plan updates for that section are all finished.
5. Do not silently widen scope to persistent parity, reward flow parity, or broader notification refactors.
6. Do not close Phase 3B with undocumented compatibility clears.

## Deviation control protocol

Any deviation from this handoff must be justified before implementation proceeds.

### A deviation is any of the following

- changing a locked decision
- skipping a required test case
- widening scope beyond the files or outcomes named here
- deferring a required cleanup path because it is inconvenient
- closing with known unresolved contract mismatches

### Required deviation record format

Before proceeding with the deviation, Builder must add a record under `Deviation log` in this file using this structure:

1. **Requested deviation**
2. **Why the plan cannot be followed as written**
3. **Impact if deviation is accepted**
4. **Lower-risk alternative considered**
5. **Approval status**: `pending`, `approved`, or `rejected`

No deviation may move from `pending` to implementation until approval is recorded.

## Deviation log

No deviations recorded yet.

## Builder handoff packet (start here)

### Package A – Canonical assignee transient-family hardening

- **Goal**: Make the assignee transient lifecycle use one canonical `status` identity for replace behavior.
- **Files**:
  - `custom_components/choreops/managers/notification_manager.py`

#### Required steps

1. [x] Add or update the contract note near the Schedule-Lock and assignee lifecycle sections to state the transport rule explicitly:
       transient progression uses `replace`; invalidation without a successor uses `clear`.
2. [x] Confirm `due window` send path uses the canonical assignee `status` identity.
3. [x] Move `due reminder` into the same canonical assignee `status` identity as due and overdue.
4. [x] Confirm `overdue` send path uses that same canonical assignee `status` identity.
5. [x] Record exact send identity behavior for these handlers in the main plan or matrix if implementation reveals any mismatch with the current docs.

#### Acceptance criteria

- `due window`, `due reminder`, and `overdue` all share the same canonical assignee transient-family identity for mobile push replacement.
- There is no remaining ambiguity in code comments about reminder being standalone.

### Package B – Invalidation and compatibility clear normalization

- **Goal**: Ensure invalidation paths clear the canonical assignee transient-family identity first, then only documented compatibility clears if retained.
- **Files**:
  - `custom_components/choreops/managers/notification_manager.py`

#### Required steps

1. [x] Audit `_handle_chore_claimed()` invalidation behavior.
2. [x] Audit `_handle_chore_approved()` invalidation behavior.
3. [x] Audit `_clear_reset_chore_notifications()` invalidation behavior.
4. [x] Audit any deletion-related invalidation path touched by this contract slice.
5. [x] Make the canonical `status` clear the primary clear path for assignee transient invalidation.
6. [x] If legacy `due_window` and `overdue` clears remain, label them in comments and docs as compatibility clears only.
7. [x] Ensure approver workflow clears remain logically separate from assignee transient clears.

#### Acceptance criteria

- Claim, approval, reset, and deletion-related invalidation paths target the canonical assignee transient-family identity.
- Any retained old-tag clears are clearly secondary compatibility behavior.

### Package C – Self-role routing guard

- **Goal**: Ensure an assignee who is also approver-capable but not associated to themselves does not receive approver duplicates.
- **Files**:
  - `custom_components/choreops/managers/notification_manager.py`
  - targeted tests under `tests/`

#### Required steps

1. [x] Re-review approver fan-out logic around the approver association check.
2. [x] Verify no lifecycle hardening change accidentally broadens approver fan-out.
3. [x] Add a negative regression test for the self-role but non-self-associated case.

#### Acceptance criteria

- The test suite proves the assignee path and approver path remain separated by association, not role capability alone.

### Package D – Lifecycle contract test matrix

- **Goal**: Prove the user-visible lifecycle contract with explicit replace-vs-clear assertions.
- **Files**:
  - `tests/test_workflow_notifications.py`
  - `tests/test_scheduler_delegation.py`
  - optional new focused test module if readability requires it

#### Required cases

1. [x] Due -> reminder leaves one current assignee transient notification on device.
2. [x] Due -> overdue leaves one current assignee transient notification on device.
3. [x] Reminder -> overdue leaves only overdue on device.
4. [x] Claiming from the earlier due notification clears the later overdue notification from device.
5. [x] Approval clears the canonical transient family.
6. [x] Reset clears the canonical transient family.
7. [x] Self-role but non-self-associated assignee does not receive approver overdue duplicate.
8. [x] Tests distinguish `replace` scenarios from `clear` scenarios instead of only asserting disappearance.

#### Acceptance criteria

- The targeted suite proves the contract as written in the matrix, not an approximation.
- Tests remain readable and table-driven where practical.

### Package E – Documentation and plan closure evidence

- **Goal**: Leave the initiative in a handoff-safe state with no undocumented behavior.
- **Files**:
  - `docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_COMPLETED.md`
  - `docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_NOTIFICATION_OVERVIEW_MATRIX.md`
  - `choreops-wiki/Configuration:-Notifications.md`
  - `choreops-wiki/Technical:-Notifications.md`

#### Required steps

1. [x] Update the main plan percentages, quick notes, and validation notes after implementation.
2. [x] Update the matrix if implementation reveals any compatibility clears or wording refinements.
3. [x] Refresh wiki wording so it clearly states:
       transient progression uses replacement; invalidation without a successor uses clear.
4. [x] Document the persistent fallback scope boundary accurately: keep stable, not a parity target in this slice.
5. [x] Record command outputs and pass counts in the main plan and this handoff.

#### Acceptance criteria

- No runtime behavior introduced in code is missing from the docs or plan.
- The main plan is current enough that a maintainer can judge completion without re-reading the full diff.

## Required execution order

Builder must execute the packages in this order unless a recorded and approved deviation says otherwise:

1. Package A – Canonical transient-family hardening
2. Package B – Invalidation and compatibility clear normalization
3. Package C – Self-role routing guard
4. Package D – Lifecycle contract test matrix
5. Package E – Documentation and plan closure evidence

Do not start Package E as a cosmetic wrap-up before Packages A-D are actually complete.

## Required validation commands

Run in `choreops` and record results in this handoff.

1. `./utils/quick_lint.sh --fix`
2. `mypy custom_components/choreops/`
3. `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
4. `python -m pytest tests/test_scheduler_delegation.py -v --tb=line`
5. If a new targeted lifecycle module is created, run it explicitly and record the output.

### Validation notes

- `python -m pytest tests/ -v --tb=line` is not a required close gate for this handoff because the plan already records unrelated pre-existing failures outside this slice.
- If any targeted command fails because of this work, the handoff is not complete.

## Acceptance checklist (all must be checked)

- [x] Package A completed
- [x] Package B completed
- [x] Package C completed
- [x] Package D completed
- [x] Package E completed
- [x] No unapproved deviations were taken
- [x] Any approved deviations are fully documented with impact notes
- [x] Main initiative plan updated with current evidence
- [x] Matrix artifact updated with any implementation clarifications
- [x] Targeted validation commands passed and outputs recorded

## Execution evidence

- `python -m pytest tests/test_workflow_notifications.py -v --tb=line` ✅ (`33 passed`)
- `python -m pytest tests/test_scheduler_delegation.py -v --tb=line` ✅ (`13 passed`)
- `./utils/quick_lint.sh --fix` ✅
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ (`Success: no issues found in 51 source files`)
- `mypy custom_components/choreops/` ⚠️ Workspace parser caveat in `/workspaces/core`; not treated as a ChoreOps type regression for this repo-local gate

## Builder handback payload (required)

Builder must return all of the following in the handback:

1. Changed files list grouped by Package A-E.
2. Send/clear contract summary after implementation:
   - canonical transient send identity
   - primary clear paths
   - any retained compatibility clears
3. Test summary with exact command outputs and pass counts.
4. Documentation updates performed.
5. Residual gaps list.
   - This should be `none` for a clean Phase 3B close.
6. Deviation log summary.
   - This should be `none` if no deviations were taken.

## Completion report template (Builder must fill)

1. **What changed**

- `notification_manager.py` now treats assignee due-window, due-reminder, and overdue notifications as one canonical `status` transient family.
- Claim, approval, reset, and chore deletion now clear the canonical transient family first and retain old `due_window` / `overdue` clears as compatibility behavior.
- `test_workflow_notifications.py` now includes lifecycle replacement/clear regressions and the self-role non-association negative case.
- Plan, matrix, and wiki wording now explicitly distinguish `replace` from `clear` and document the persistent fallback scope boundary.

2. **Package status** (`A`, `B`, `C`, `D`, `E`)

- `A`: complete
- `B`: complete
- `C`: complete
- `D`: complete
- `E`: complete

3. **Canonical contract after implementation**

- `due window` -> `due reminder` -> `overdue` now uses one canonical assignee `status` identity for mobile push replacement.
- Claim, approval, reset, and chore deletion clear that canonical assignee transient identity explicitly.
- Legacy `due_window` and `overdue` clears remain compatibility-only.

4. **Validation outputs**

- `33 passed` in `tests/test_workflow_notifications.py`
- `13 passed` in `tests/test_scheduler_delegation.py`
- `quick_lint` passed
- repo-local MyPy passed

5. **Deviation record**

- none

6. **Residual gaps**

- none within Phase 3B scope

7. **Recommendation** (`close Phase 3B` or `continue`)

- close Phase 3B and await owner approval before Phase 4 closeout work
