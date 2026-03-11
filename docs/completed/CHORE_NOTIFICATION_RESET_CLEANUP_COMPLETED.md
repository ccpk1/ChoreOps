# Initiative plan: Chore notification reset cleanup

## Initiative snapshot

- **Name / Code**: Chore notification reset cleanup (`CHORE_NOTIFICATION_RESET_CLEANUP`)
- **Target release / milestone**: v0.5.0-beta.5 follow-up / next notification bugfix PR
- **Owner / driver(s)**: ChoreOps maintainers + builder execution handoff
- **Status**: Complete; archived after Phase 4 closeout and validation evidence capture

## Summary & immediate steps

| Phase / Step                                    | Description                                                                | % complete | Quick notes                                                                                     |
| ----------------------------------------------- | -------------------------------------------------------------------------- | ---------: | ----------------------------------------------------------------------------------------------- |
| Phase 1 – Reset-path audit and cleanup contract | Verify every reset path and define the narrow reset-cleanup fix            |        100 | Reset inventory locked; broad tag refactor deferred                                             |
| Phase 2 – Reset-only implementation             | Add reset cleanup and accurate reset-event emission only                   |        100 | Reset now clears assignee due/overdue and approver status                                       |
| Phase 3 – Reset regression coverage             | Add tests proving reset cleanup without altering working replacement flows |        100 | Reset cleanup and deferred reset-emission paths now covered                                     |
| Phase 3B – Lifecycle contract hardening         | Unify live due/reminder/overdue/claim notification cleanup semantics       |        100 | Reminder now shares STATUS family; claim/approval/reset/delete clear canonical transient family |
| Phase 4 – Rollout check                         | Validate scope stayed narrow and user-visible behavior is safe             |        100 | Release-note wording drafted; docs synced; full test tree passed in staged 25% execution        |

1. **Key objective** – Ensure chore due, reminder, overdue, claim, and reset notifications follow one consistent device-lifecycle contract so the newest valid chore state is the only assignee-facing notification left on device.

- Be explicit about transport: transient progression should prefer replacement on the canonical notification identity, while invalidation without a successor should use explicit clear behavior.

2. **Summary of recent work**
   - Reset and notification code paths were traced in `ChoreManager` and `NotificationManager`.

- Current behavior was confirmed to rely on `approval_period_start` invalidation for resend suppression, but not explicit device clearing.
- A reset-path audit confirmed that several reset methods persisted state changes without emitting `SIGNAL_SUFFIX_CHORE_STATUS_RESET`.
- Phase 2 now adds reset cleanup in `NotificationManager` and deferred post-persist reset emits in `ChoreManager` for externally persisted reset paths.
- Wiki review continues to block any broader tag-family refactor; this phase intentionally leaves assignee status notification semantics unchanged.
- Field evidence now shows that deferring assignee status-tag normalization left a real lifecycle gap: claim cleanup does not remove the overdue notification that was actually sent, and reminder notifications can still stack separately from overdue.
- Companion App behavior also shows a technical distinction the plan must respect: replacement via tag is the more reliable primitive for transient progression, while explicit clears have platform caveats and should be used deliberately for invalidation cases.
- Phase 3B is now implemented: `due window`, `due reminder`, and `overdue` use the shared assignee `status` replacement family for mobile push.
- Claim, approval, reset, and chore deletion now clear the canonical assignee transient family first, while retaining legacy `due_window` and `overdue` clears as documented compatibility behavior.
- Targeted lifecycle regressions now cover due -> reminder replacement, reminder -> overdue replacement, canonical claim/approval clears, and the self-role non-association guard.
- Wiki and in-process documentation now explicitly distinguish `replace` from `clear`, and persistent fallback is documented as stability-only for this slice.

3. **Next steps (short term)**

- None for this initiative.
- Archive this plan and keep the supporting matrix, audit, and handoff artifacts as historical record in `docs/completed/`.
- Any future notification work should start as a new initiative instead of reopening this one implicitly.

4. **Risks / blockers**

- No active blockers remain for the archived scope of this initiative.
- Persistent-notification fallback parity remains intentionally deferred; Phase 3B guaranteed mobile-push lifecycle hardening without widening fallback behavior.
- Raw `mypy custom_components/choreops/` from this multi-repo workspace can still trip a parser issue in `/workspaces/core`; the repo-local MyPy gate used by `quick_lint` and `mypy_quick.ini` remains the authoritative ChoreOps validation path.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [tests/AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
  - [docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_RESET_PATH_AUDIT.md](CHORE_NOTIFICATION_RESET_CLEANUP_SUP_RESET_PATH_AUDIT.md)

- [docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_NOTIFICATION_OVERVIEW_MATRIX.md](CHORE_NOTIFICATION_RESET_CLEANUP_SUP_NOTIFICATION_OVERVIEW_MATRIX.md)
- [docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_BUILDER_HANDOFF_PHASE3B.md](CHORE_NOTIFICATION_RESET_CLEANUP_SUP_BUILDER_HANDOFF_PHASE3B.md)
- [choreops-wiki/Configuration:-Notifications.md](../../choreops-wiki/Configuration:-Notifications.md)
- [choreops-wiki/Technical:-Notifications.md](../../choreops-wiki/Technical:-Notifications.md)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Treat this as a notification lifecycle bug, not a scheduling or storage-schema bug.
     - Preserve Schedule-Lock timestamp invalidation; add explicit device-clear behavior on reset.
     - Phase 1 is limited to reset cleanup and reset-event accuracy only.
     - Do not force tag-family unification until runtime behavior is reconciled with the wiki-documented replacement model.
     - `due reminder` is now part of the canonical assignee `status` transient family and replaces due-window.
     - Claim, approval, reset, and chore deletion now clear the canonical assignee transient family and retain legacy `due_window` / `overdue` clears only as compatibility behavior.
     - Persistent fallback remains in scope for stability only; parity expansion is explicitly deferred.
   - New Phase 3B exists specifically because the deferred tag-family decision is now proven user-visible in production behavior.
   - No `.storage/choreops/choreops_data` schema change is planned for this initiative.
   - No new `TRANS_KEY_*` constants are expected if cleanup remains internal-only; current notification copy should be reused unchanged.
  - **Completion confirmation**: `[x]` All follow-up items completed (runtime behavior, tests, docs, validation) before requesting owner approval.

> **Important:** Keep the Summary section current after each material implementation or validation update.

## Tracking expectations

- **Summary upkeep**: Update phase percentages, quick notes, and blockers after each merged implementation slice.
- **Detailed tracking**: Keep exact file anchors, validation notes, and edge cases in the phase sections below.

## Detailed phase tracking

### Phase 1 – Reset-path audit and cleanup contract

- **Goal**: Verify every reset path and define the smallest safe reset-only cleanup path without changing broader notification replacement semantics.
- **Steps / detailed work items**
  1. [x] Confirm the reset signal and due-state signal surface in [custom_components/choreops/const.py](../custom_components/choreops/const.py) around lines 235-249 and the notification tag constants around lines 3651-3653.
  2. [x] Audit `NotificationManager.async_setup()` in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) lines 157-201 to document current subscriptions and the missing `SIGNAL_SUFFIX_CHORE_STATUS_RESET` listener.
  3. [x] Document the existing Schedule-Lock storage contract in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) lines 260-406 and explicitly separate “resend suppression” from “device clear” behavior.
  4. [x] Verify each reset-producing method in [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py): `set_due_date()` lines 2569-2668, `skip_due_date()` lines 2676-2800, `reset_chore_to_pending()` lines 2801-2838, `reset_all_chore_states_to_pending()` lines 2840-2857, `reset_overdue_chores()` lines 2859-2905, and due-date change handling in `update_chore()` lines 3020-3041.
  5. [x] Confirm which reset paths emit `SIGNAL_SUFFIX_CHORE_STATUS_RESET` today through `_transition_chore_state()` in [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py) lines 4019-4147 and which do not because they use `persist=False` and an outer persist.
- **Key issues**
  - The highest-confidence gap is reset cleanup, not broad tag-family refactoring.
  - Several reset methods currently behave like true resets but do not emit `SIGNAL_SUFFIX_CHORE_STATUS_RESET` after persisting.

### Phase 2 – Reset-only implementation

- **Goal**: Define the smallest runtime change set that reliably clears stale notifications when chores reset, without altering other working notification flows.
- **Steps / detailed work items**
  1. [x] Add a `NotificationManager` cleanup handler plan for `SIGNAL_SUFFIX_CHORE_STATUS_RESET` in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) near lines 157-201 and place the new handler alongside other chore lifecycle handlers.
  2. [x] Review whether reset cleanup should clear assignee notifications only, or also approver workflow notifications, based on currently documented reset semantics and existing approver status-tag usage.
  3. [x] Refactor the reset contract in [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py) lines 2569-2668, 2676-2800, 2801-2905, and 3020-3041 so reset methods that persist externally also emit reset events consistently after persistence.
  4. [x] Keep `_transition_chore_state()` in [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py) lines 4019-4147 as the single-record emitter for `persist=True` paths unless a narrow deferred-emit helper is required for batch methods.
- **Key issues**
  - Emission currently happens only inside the `persist=True` branch of `_transition_chore_state()`, which makes batch behavior inconsistent.
  - The implementation must preserve the project’s persist-then-emit rule from the architecture and development standards.
  - This phase should not change due/reminder/overdue replacement behavior unless reset cleanup proves it is strictly necessary.
  - Decision captured: reset cleanup clears assignee `due_window` and `overdue` notifications plus approver `status` notifications; assignee `status` notification behavior remains unchanged in this phase.

### Phase 3 – Reset regression coverage

- **Goal**: Add targeted tests that prove reset-driven device clearing without weakening current Schedule-Lock behavior or other working notification flows.
- **Steps / detailed work items**
  1. [x] Extend [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py) around lines 815-880 with new tests that distinguish Schedule-Lock invalidation from explicit device notification clearing.
  2. [x] Add reset-focused workflow tests in [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py) for the reset cases that will be supported in Phase 2, without asserting a broader tag unification policy.
  3. [x] Extend [tests/test_scheduler_delegation.py](../../tests/test_scheduler_delegation.py) lines 260-356 to verify reset-producing methods emit `SIGNAL_SUFFIX_CHORE_STATUS_RESET` when they persist reset results.
  4. [x] Run `mypy tests/` in addition to production validation because test files are outside the default quick lint scope per [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md).
- **Key issues**
  - Tests should patch notification send/clear helpers rather than rely on live mobile integrations.
  - Existing scenario-based notification fixtures should be reused instead of inventing new names or raw data.
  - Tests should characterize current working notification behavior and only add reset assertions where behavior is intentionally changed.

### Phase 3B – Lifecycle contract hardening

- **Goal**: Finish the broader assignee notification lifecycle contract that Phase 2 intentionally deferred so due, reminder, overdue, claim, approval, and reset paths all clear or replace the exact notifications they actually send.
- **Steps / detailed work items**
  1. [x] Write a short contract note at the top of [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) around lines 260-406 and 1942-2053 defining the canonical assignee-facing notification family.
  - Explicitly decide whether assignee `due_window`, `due_reminder`, and `overdue` notifications are one collapsing family under `NOTIFY_TAG_TYPE_STATUS`, or whether reminder intentionally remains standalone.
  - Record the expected device result for each transition: `due_window -> overdue`, `due_reminder -> overdue`, `due/reminder -> claim`, `overdue -> approved`, `overdue -> reset`.
    - Use [docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_NOTIFICATION_OVERVIEW_MATRIX.md](CHORE_NOTIFICATION_RESET_CLEANUP_SUP_NOTIFICATION_OVERVIEW_MATRIX.md) as the archived contract table.
      - Implementation execution evidence is preserved in [docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_BUILDER_HANDOFF_PHASE3B.md](CHORE_NOTIFICATION_RESET_CLEANUP_SUP_BUILDER_HANDOFF_PHASE3B.md).
    - Explicitly separate domain events from transport operations: `claimed`, `approved`, `missed`, `reset`, and chore deletion are lifecycle events; `replace` and `clear` are notification operations.
  2. [x] Audit every assignee send path in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py): `_handle_chore_due_window()` lines 2501-2569, `_handle_chore_due_reminder()` lines 2571-2639, `_handle_chore_overdue()` lines 2641-2804, `_handle_chore_claimed()` lines 1942-2053, `_handle_chore_approved()` lines 2298-2339, and `_clear_reset_chore_notifications()` lines 1589-1613.
     - Build a matrix showing for each path: send tag used, notification ID behavior, whether the intended operation is `replace` or `clear`, clear tags attempted, and any legacy compatibility clears.
  - Treat any send/clear mismatch as a Phase 3B blocker, not a cleanup follow-up.
  3. [x] Normalize claim and approval cleanup to clear the canonical assignee status notification tag actually used by due-window and overdue sends.
  - Anchor review points: [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) lines 2051-2052 and lines 2318-2319.
  - If legacy `overdue` and `due_window` tag clears are retained for backward compatibility, document them as compatibility clears, not primary behavior.
  4. [x] Decide and implement the due-reminder policy explicitly instead of leaving it implicit.
  - Locked decision: move due reminders into the same `status` collapsing family so reminder replaces due, overdue replaces either prior transient state, and claim clears the canonical transient family.
  - Do not keep reminder standalone in this phase.
  - Selection rationale: tag-based replacement is the preferred transport primitive for transient progression and matches the desired user-visible behavior.
  5. [x] Classify delivery-backend guarantees before claiming the lifecycle contract is complete.
  - Review mobile push behavior versus persistent-notification fallback in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) lines 930-976, 1530-1613, and related helper paths.
  - Locked scope: do not spend Phase 3B implementation time adding persistent parity work.
  - Document the strict replace-plus-clear contract primarily for mobile-app notifications and only require that persistent fallback replacement behavior is not regressed.
  - Do not describe fallback parity in docs unless a real persistent dismiss path exists and is tested.
  6. [x] Add a self-role delivery guard review covering users who are both assignable and approver-capable accounts.
  - Review approver fan-out in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) lines 1140-1305 and verify that non-associated self-approver accounts never receive approver copies for their own chore.
  - Add a targeted negative test proving an assignee who is also an approver record, but not associated to themselves, receives only the assignee notification path.
  7. [x] Extend workflow tests in [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py) with real lifecycle regressions, not just reset-only coverage.
  - Required cases:
  - assignee due notification followed by overdue leaves one current assignee notification on device
  - assignee due notification followed by reminder leaves one current assignee notification on device
  - claiming from the earlier due notification clears the later overdue notification from device
  - due reminder followed by overdue follows the chosen Phase 3B contract
  - assignee-who-is-also-approver-but-not-self-associated does not receive an approver overdue duplicate
  - approval and reset still clear the canonical assignee notification family after the tag normalization
  - Add assertions that distinguish `replace` scenarios from `clear` scenarios so the tests enforce transport intent rather than just generic disappearance.
  8. [x] Reconcile docs and wiki wording against the finalized lifecycle contract before closeout.
     - Update [choreops-wiki/Configuration:-Notifications.md](../../choreops-wiki/Configuration:-Notifications.md) if the user-facing event matrix or auto-clear claims change.
     - Update [choreops-wiki/Technical:-Notifications.md](../../choreops-wiki/Technical:-Notifications.md) if the tag or replacement narrative changes.
     - Explicitly document the preferred rule: transient progression uses replacement; invalidation without a successor uses clear.
     - Preserve this supporting matrix as the maintainer-facing artifact even if the final user-facing wording is simplified.

  9. [x] Add a focused contract test module if needed instead of overloading one workflow file.
  - Candidate files: [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py) and [tests/test_scheduler_delegation.py](../../tests/test_scheduler_delegation.py).
  - Phase 3B kept the lifecycle contract in the existing workflow module because the cases remain readable and targeted without an additional file split.
  10. [x] Validate Phase 3B with targeted commands before reopening Phase 4 closeout.
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
  - `python -m pytest tests/test_scheduler_delegation.py -v --tb=line`

- **Key issues**
  - The real bug is now a lifecycle-contract mismatch, not a reset-only bug.
  - `Schedule-Lock` dedup timestamps must stay separate from device-clear behavior; Phase 3B should not conflate them.
  - The transport contract must explicitly say when ChoreOps expects `replace` versus `clear`; otherwise code comments, wiki language, and tests will keep drifting.
  - Mobile push currently has the strongest lifecycle tooling because it supports both tag-based replacement and explicit clear; persistent fallback should be kept stable but is not a Phase 3B parity target.
  - “Bullet proof” here means every send path and every clear path must be explainable from one contract table, with no orphaned legacy tags left as undocumented behavior.
  - If reminder behavior is kept distinct, that must be an explicit product decision, not an accidental omission.
  - The ChoreOps docs tree still lacks a stable notification overview matrix; this phase should finish with both a maintainer artifact and refreshed wiki language.

### Phase 4 – Documentation and rollout check

- **Goal**: Close the initiative with validation evidence and lightweight documentation updates only where behavior expectations changed.
- **Steps / detailed work items**
  1. [x] Update inline code comments in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) lines 260-406 to clarify that Schedule-Lock does not clear existing device notifications.
  2. [x] Draft concise release-note wording for release PR or release checklist use: "Chore mobile notifications now collapse more reliably to the latest valid due-state. Due reminders replace due-window prompts, overdue replaces earlier transient prompts, and claim, approval, reset, and delete now clear stale chore notifications more consistently."
  3. [x] Confirm that no translation source files require changes because the initiative reuses existing `TRANS_KEY_NOTIF_*` text paths.
  4. [x] Record final Phase 3B validation results and residual edge cases in this plan before execution handoff is archived.
- **Key issues**
  - Closeout remains documentation-only; no storage migration or notification content change was required.
  - Release publication should reuse the drafted wording above in the release PR or release notes path.
  - Persistent fallback parity is intentionally deferred and is not a completion blocker for this initiative.

## Testing & validation

- **Planned validation commands**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `mypy tests/`
  - `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
  - `python -m pytest tests/test_scheduler_delegation.py -v --tb=line`
  - `python -m pytest tests/ -v --tb=line`
- **Outstanding tests**
  - `./utils/quick_lint.sh --fix` ✅ Passed after Phase 3B implementation (ruff, repo-local integration mypy, boundary checks)
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ Passed (`Success: no issues found in 51 source files`)
  - `mypy custom_components/choreops/` ⚠️ Workspace parser caveat in `/workspaces/core/homeassistant/helpers/device_registry.py`; not a ChoreOps type failure in this repo layout
  - `mypy tests/` ⚠️ Ran, but blocked by broad pre-existing test typing debt outside this initiative (for example `tests/test_chore_manager.py`, `tests/test_workflow_chores.py`, `tests/test_workflow_streak_schedule.py`)
  - `python -m pytest tests/test_workflow_notifications.py -v --tb=line` ✅ Passed after Phase 3B implementation (`33 passed`)
  - `python -m pytest tests/test_scheduler_delegation.py -v --tb=line` ✅ Passed (`13 passed`)
  - Full `tests/` tree coverage ✅ Passed in four deterministic 25% chunks across all `tests/test_*.py` files (`1673 passed, 4 skipped, 2 deselected` total)
  - New Phase 3B lifecycle tests are now written and passing; current targeted validation covers the broader assignee claim/reminder/overdue contract.
  - Performance and dashboard suites remain out of scope for this initiative.
  - Phase 4 closeout completed: release-note wording drafted, architecture/standards/wiki docs aligned, and no additional runtime changes were required.

## Notes & follow-up

- This initiative does **not** require a data migration or schema version bump because the planned changes are limited to event wiring, notification tag consistency, and test coverage.
- The expected first-phase implementation should remain inside `managers/` and `tests/`; no options flow, dashboard template, or storage-builder changes are expected.
- If execution discovers that persistent notifications behave differently from mobile push notifications for tag clearing, document that distinction before widening scope.
- Phase 3B exists to close the exact class of regression reported from live device use: overdue remained after claim, and multiple assignee-facing chore notifications coexisted when the intended “latest valid state wins” contract was not fully enforced.
- Archived outcome: the mobile-push lifecycle contract is now aligned across runtime code, workflow tests, architecture docs, development standards, and wiki documentation.
