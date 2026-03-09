# Initiative plan: Chore notification reset cleanup

## Initiative snapshot

- **Name / Code**: Chore notification reset cleanup (`CHORE_NOTIFICATION_RESET_CLEANUP`)
- **Target release / milestone**: v0.5.0-beta.5 follow-up / next notification bugfix PR
- **Owner / driver(s)**: ChoreOps maintainers + builder execution handoff
- **Status**: Phase 4 partial documentation closeout complete; release note and translation confirmation handled separately

## Summary & immediate steps

| Phase / Step                                    | Description                                                                | % complete | Quick notes                                                         |
| ----------------------------------------------- | -------------------------------------------------------------------------- | ---------: | ------------------------------------------------------------------- |
| Phase 1 – Reset-path audit and cleanup contract | Verify every reset path and define the narrow reset-cleanup fix            |        100 | Reset inventory locked; broad tag refactor deferred                 |
| Phase 2 – Reset-only implementation             | Add reset cleanup and accurate reset-event emission only                   |        100 | Reset now clears assignee due/overdue and approver status           |
| Phase 3 – Reset regression coverage             | Add tests proving reset cleanup without altering working replacement flows |        100 | Reset cleanup and deferred reset-emission paths now covered         |
| Phase 4 – Rollout check                         | Validate scope stayed narrow and user-visible behavior is safe             |         50 | Comment + validation closeout done; release/doc follow-up split out |

1. **Key objective** – Ensure chore due/overdue notifications are cleared from devices when a chore resets to `pending`, while preserving the existing Schedule-Lock resend behavior.
2. **Summary of recent work**
   - Reset and notification code paths were traced in `ChoreManager` and `NotificationManager`.

- Current behavior was confirmed to rely on `approval_period_start` invalidation for resend suppression, but not explicit device clearing.
- A reset-path audit confirmed that several reset methods persisted state changes without emitting `SIGNAL_SUFFIX_CHORE_STATUS_RESET`.
- Phase 2 now adds reset cleanup in `NotificationManager` and deferred post-persist reset emits in `ChoreManager` for externally persisted reset paths.
- Wiki review continues to block any broader tag-family refactor; this phase intentionally leaves assignee status notification semantics unchanged.

3. **Next steps (short term)**

- Handle the release-note/changelog note separately from this execution slice.
- Confirm translation-source impact separately; no runtime evidence currently suggests new translation keys are needed.
- Decide later whether persistent-notification fallbacks need separate reset cleanup handling or can stay out of scope.

4. **Risks / blockers**

- Broader tag normalization remains risky because the wiki describes intentional replacement behavior in some flows.
- Reset cleanup currently targets mobile push tag clearing; persistent-notification fallback behavior remains unchanged in this phase.
- Full-suite validation is currently blocked by unrelated failures in `tests/test_workflow_streak_schedule.py`.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [tests/AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [docs/in-process/CHORE_NOTIFICATION_RESET_CLEANUP_SUP_RESET_PATH_AUDIT.md](CHORE_NOTIFICATION_RESET_CLEANUP_SUP_RESET_PATH_AUDIT.md)
   - [choreops-wiki/Configuration:-Notifications.md](../../choreops-wiki/Configuration:-Notifications.md)
   - [choreops-wiki/Technical:-Notifications.md](../../choreops-wiki/Technical:-Notifications.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Treat this as a notification lifecycle bug, not a scheduling or storage-schema bug.
     - Preserve Schedule-Lock timestamp invalidation; add explicit device-clear behavior on reset.
     - Phase 1 is limited to reset cleanup and reset-event accuracy only.
     - Do not force tag-family unification until runtime behavior is reconciled with the wiki-documented replacement model.
     - No `.storage/choreops/choreops_data` schema change is planned for this initiative.
     - No new `TRANS_KEY_*` constants are expected if cleanup remains internal-only; current notification copy should be reused unchanged.
   - **Completion confirmation**: `[ ]` All follow-up items completed (runtime behavior, tests, docs, validation) before requesting owner approval.

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

### Phase 4 – Documentation and rollout check

- **Goal**: Close the initiative with validation evidence and lightweight documentation updates only where behavior expectations changed.
- **Steps / detailed work items**
  1. [x] Update inline code comments in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py) lines 260-406 to clarify that Schedule-Lock does not clear existing device notifications.
  2. [ ] Add a concise release-note or changelog note in the appropriate release documentation path if the user-visible effect is that stale overdue/due notifications now disappear on reset.
  3. [ ] Confirm that no translation source files require changes because the initiative reuses existing `TRANS_KEY_NOTIF_*` text paths.
  4. [x] Record final validation results and any residual edge cases in this plan before execution handoff is marked complete.
- **Key issues**
  - Documentation should stay narrow and not imply a storage migration or notification content change.
  - If new helper comments are added, they should reinforce the event-driven cross-manager contract rather than introduce new behavior assumptions.
  - Steps 2 and 3 are intentionally handled separately from this execution slice.

## Testing & validation

- **Planned validation commands**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `mypy tests/`
  - `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
  - `python -m pytest tests/test_scheduler_delegation.py -v --tb=line`
  - `python -m pytest tests/ -v --tb=line`
- **Outstanding tests**
  - `./utils/quick_lint.sh --fix` ✅ Passed (ruff, integration mypy, boundary checks)
  - `mypy custom_components/choreops/` ✅ Passed via `./utils/quick_lint.sh --fix`
  - `mypy tests/` ⚠️ Ran, but blocked by broad pre-existing test typing debt outside this initiative (for example `tests/test_chore_manager.py`, `tests/test_workflow_chores.py`, `tests/test_workflow_streak_schedule.py`)
  - `python -m pytest tests/test_workflow_notifications.py -v --tb=line` ✅ Passed (`28 passed`)
  - `python -m pytest tests/test_scheduler_delegation.py -v --tb=line` ✅ Passed (`13 passed`)
  - `python -m pytest tests/ -v --tb=line` ⚠️ Still blocked by unrelated existing failures in `tests/test_workflow_streak_schedule.py`
  - Performance and dashboard suites remain out of scope for this initiative.
  - Phase 4 note: no additional validation rerun was required for this documentation-only slice because the recorded runtime evidence already reflects the implemented notification-reset behavior.

## Notes & follow-up

- This initiative does **not** require a data migration or schema version bump because the planned changes are limited to event wiring, notification tag consistency, and test coverage.
- The expected first-phase implementation should remain inside `managers/` and `tests/`; no options flow, dashboard template, or storage-builder changes are expected.
- If execution discovers that persistent notifications behave differently from mobile push notifications for tag clearing, document that distinction before widening scope.
