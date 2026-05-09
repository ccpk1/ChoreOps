# REQ template draft

- **Title**: `[REQ] Add runtime chore entity sync for dashboard-driven chore changes`
- **Feature area**: `Integration logic/state`

## Problem or use case

Following the later discussion on closed issue [#96](https://github.com/ccpk1/ChoreOps/issues/96), this looks less like one remaining `update_chore` bug and more like a broader runtime limitation.

Today, when chore membership or other chore-backed entity structure changes, ChoreOps relies on a full integration reload to rebuild the affected entities. That is a normal Home Assistant pattern, but it becomes disruptive for dashboard-driven chore changes because the dashboard depends on those live entities and helper surfaces.

When a reload happens during an assignment change, the page can be left stale or temporarily broken until the user manually refreshes. The late comments in [#96](https://github.com/ccpk1/ChoreOps/issues/96) suggest the most fragile cases are adding or removing assignees from a chore.

## Proposed solution

Add a targeted runtime synchronization path for chore-backed entities so ChoreOps can handle live chore graph changes without depending on a full integration reload for those specific operations.

This should cover chore create, update, and delete, including live add/remove/update of assignee-specific sensors, buttons, and dashboard helper surfaces. Full integration reload should remain available where it is still the right tool, but it should stop being the only backend path for chore CRUD cases that need smoother live behavior.

## Expected outcome

- Dashboard-driven chore updates stop leaving the page in a broken or stale state.
- Users no longer need a manual page refresh after chore assignment changes.
- Backend behavior becomes more consistent across service calls, dashboard actions, and config/options flows.
- Chore CRUD becomes a stronger foundation for more interactive native UI patterns in the future.

## Alternatives considered

- Adding delays or wait templates after dashboard scripts
- Forcing browser refresh with `browser_mod`
- Navigating away and back to the dashboard
- Continuing to patch isolated `update_chore` edge cases instead of addressing the runtime entity lifecycle directly

## Additional context

- In the latest discussion on [#96](https://github.com/ccpk1/ChoreOps/issues/96), the current understanding was that chore create/update/delete flows trigger integration reload because the system must recreate or remove user-specific entities when chore membership changes.
- That original reload-centric design appears intentional and standards-aligned with normal Home Assistant integration lifecycle patterns, not an accidental shortcut.
- The new ask is to move one step beyond that baseline for chore CRUD specifically, because ChoreOps now behaves more like an interactive application surface than a mostly static entity set.
- There is already active planning around this direction in the repo, but it would still be useful to track it as a user-facing enhancement request tied back to the field report and dashboard use case.
- @Crazypkr your follow-up testing and examples in [#96](https://github.com/ccpk1/ChoreOps/issues/96) were the key reason this broader backend limitation became clear.
