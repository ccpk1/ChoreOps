# Supporting audit: Chore reset paths and notification cleanup impact

## Purpose

This audit narrows the initiative to the first phase only:

- identify every current chore reset path
- verify whether it emits `SIGNAL_SUFFIX_CHORE_STATUS_RESET`
- verify which existing managers listen to that signal
- isolate the smallest safe notification cleanup path for reset events only

This document intentionally does **not** decide broader tag-family refactors or notification replacement policy changes.

## Current reset listeners

The following existing consumers listen for `SIGNAL_SUFFIX_CHORE_STATUS_RESET` today:

- [custom_components/choreops/managers/gamification_manager.py](../custom_components/choreops/managers/gamification_manager.py#L120-L126)
- [custom_components/choreops/managers/statistics_manager.py](../custom_components/choreops/managers/statistics_manager.py#L133-L139)
- [custom_components/choreops/managers/ui_manager.py](../custom_components/choreops/managers/ui_manager.py#L74-L80)
- [custom_components/choreops/calendar.py](../custom_components/choreops/calendar.py#L123-L130)
- [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L154-L168) for cache invalidation

`NotificationManager` does **not** currently listen for `SIGNAL_SUFFIX_CHORE_STATUS_RESET` in [custom_components/choreops/managers/notification_manager.py](../custom_components/choreops/managers/notification_manager.py#L157-L201).

## Verified reset-path inventory

### 1. Scheduled reset via `_apply_reset_action()`

- **Path**: scheduled approval-reset logic
- **Anchor**: [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L1543-L1588)
- **State change**: `_transition_chore_state(..., CHORE_STATE_PENDING)`
- **Persist mode**: default `persist=True`
- **Reset signal today**: **Yes** via `_transition_chore_state()`
- **Notification cleanup today**: **No** because `NotificationManager` does not listen for reset
- **Confidence**: high

### 2. `set_due_date()`

- **Path**: due-date update resets chore state to `pending`
- **Anchor**: [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L2569-L2668)
- **State change**: one or more `_transition_chore_state(..., persist=False)` calls
- **Persist mode**: outer method persists once at the end
- **Reset signal today**: **No**
- **Notification cleanup today**: **No**
- **Notes**: this is a real reset path, not just a scheduling-data update

### 3. `skip_due_date()`

- **Path**: recurring due-date skip / reschedule
- **Anchor**: [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L2676-L2800)
- **State change**: one or more `_transition_chore_state(..., persist=False)` calls
- **Persist mode**: outer method persists once at the end
- **Reset signal today**: **No**
- **Notification cleanup today**: **No**
- **Notes**: this is especially relevant because skip can be triggered from overdue notifications through the action flow

### 4. `reset_chore_to_pending()`

- **Path**: explicit reset helper for all assigned users on one chore
- **Anchor**: [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L2801-L2838)
- **State change**: `_transition_chore_state(..., persist=False)` inside loop
- **Persist mode**: optional outer persist after loop
- **Reset signal today**: **No**, even when `persist=True` on this method
- **Notification cleanup today**: **No**
- **Notes**: docstring/comment intent and runtime behavior are currently out of sync here

### 5. `reset_all_chore_states_to_pending()`

- **Path**: manual bulk reset
- **Anchor**: [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L2840-L2857)
- **State change**: calls `reset_chore_to_pending(..., persist=False)` for each chore
- **Persist mode**: one final batch persist
- **Reset signal today**: **No**, despite method docstring saying it emits reset events
- **Notification cleanup today**: **No**
- **Notes**: this is a confirmed accuracy gap between docs/comments and runtime behavior

### 6. `reset_overdue_chores()`

- **Path**: overdue reset helper and notification action skip path
- **Anchor**: [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L2859-L2905)
- **State change**: `_transition_chore_state(..., persist=False)` per affected assignee/chore pair
- **Persist mode**: one final batch persist
- **Reset signal today**: **No**
- **Notification cleanup today**: **No**
- **Notes**: this is directly relevant to overdue notifications because the skip action eventually routes here

### 7. `update_chore()` when due-date fields change

- **Path**: chore edit path
- **Anchor**: [custom_components/choreops/managers/chore_manager.py](../custom_components/choreops/managers/chore_manager.py#L3020-L3041)
- **State change**: indirect call to `reset_chore_to_pending(chore_id, persist=False)`
- **Persist mode**: outer update method persists after merge
- **Reset signal today**: **No**
- **Notification cleanup today**: **No**
- **Notes**: this path matters because editing due dates can invalidate outstanding due/overdue notifications

## Reset-path conclusions

### Confirmed accurate conclusions

1. There is **one** reset family that already emits `CHORE_STATUS_RESET` today:
   - scheduled single-record reset through `_transition_chore_state(..., persist=True)`

2. There are **multiple** reset families that currently do **not** emit `CHORE_STATUS_RESET`:
   - `set_due_date()`
   - `skip_due_date()`
   - `reset_chore_to_pending()`
   - `reset_all_chore_states_to_pending()`
   - `reset_overdue_chores()`
   - `update_chore()` when due dates are changed

3. Even the reset path that does emit the signal does not currently clear notifications, because `NotificationManager` is not subscribed.

4. The current planning focus can be reduced to a safe, narrow first phase:
   - establish a proper notification cleanup path on reset
   - make reset-event emission accurate for reset methods that currently claim or imply reset semantics

## What this first phase should not decide yet

- whether all due-state notifications should collapse into one tag family
- whether due reminders should replace due-window notifications or remain independent
- whether delete cleanup should also be widened
- whether missed notifications need separate reset semantics

Those can remain follow-up questions after reset cleanup is reliable.

## Recommended first-phase implementation boundary

The safe first phase is:

1. Add reset cleanup handling to `NotificationManager`
2. Ensure reset paths that semantically perform a reset actually emit `CHORE_STATUS_RESET` after persistence
3. Add characterization tests for current notification send behavior and focused tests for reset cleanup

This keeps the effort tightly scoped to reset semantics and avoids destabilizing notification flows that are already working well.
