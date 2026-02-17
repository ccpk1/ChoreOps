# Async listener migration - implementation matrix

Status: Completed

## Scope and usage

- Parent initiative: `ASYNC_LISTENER_MIGRATION_COMPLETED`.
- This document is an execution aid for builder agents implementing async listener migration.
- Use this as the step-by-step source of truth for handler order, risk, and validation.
- No storage schema migration is included in this effort.

## Implementation policy (enforced)

1. **State-modifying listeners must be async**
   - Any listener that can trigger state machine updates, coordinator listener updates, persistence+update workflows, registry access, or notification send calls must use `async def`.
2. **Read-only/log-only listeners may stay sync**
   - Keep sync only when the handler mutates no shared state and calls no loop-bound async API.
3. **Remove manual thread marshaling where migration makes it obsolete**
   - Replace `call_soon_threadsafe(... async_create_task ...)` wrappers with direct awaited flow inside async listeners.
4. **Preserve signal payload contracts**
   - Keep payload keys and defaulting behavior unchanged.
5. **No opportunistic refactors**
   - Restrict edits to callback type migration and thread-safety wiring.

---

## Manager migration matrix

### 1) StatisticsManager (Phase 2 blueprint)

**File**: `custom_components/kidschores/managers/statistics_manager.py`

| Handler                           | Current | Target               | State/update touch | Priority | Notes                                                     |
| --------------------------------- | ------- | -------------------- | ------------------ | -------- | --------------------------------------------------------- |
| `_on_points_changed` (~212)       | sync    | async                | Yes                | P0       | Core point period mutations and update fan-out risk       |
| `_on_chore_approved` (~384)       | sync    | async                | Yes                | P0       | High-frequency workflow path                              |
| `_on_chore_completed` (~413)      | sync    | async                | Yes                | P0       | Completion stats path                                     |
| `_on_chore_claimed` (~544)        | sync    | async                | Yes                | P1       | Claims contribute to period stats                         |
| `_on_chore_disapproved` (~562)    | sync    | async                | Yes                | P1       | Disapprove counters                                       |
| `_on_chore_overdue` (~580)        | sync    | async                | Yes                | P1       | Overdue bucket writes                                     |
| `_on_chore_missed` (~636)         | sync    | async                | Yes                | P1       | Missed bucket writes                                      |
| `_on_chore_status_reset` (~733)   | sync    | review/likely async  | Maybe              | P2       | Keep sync only if cache-only and no loop-bound calls      |
| `_on_chore_undone` (~762)         | sync    | async                | Yes                | P1       | Undo path often updates counters                          |
| `_on_reward_approved` (~794)      | sync    | async                | Yes                | P0       | Reward period writes + rollups                            |
| `_on_reward_claimed` (~864)       | sync    | async                | Yes                | P1       | Claim tracking                                            |
| `_on_reward_disapproved` (~923)   | sync    | async                | Yes                | P1       | Disapprove tracking                                       |
| `_on_badge_earned` (~982)         | sync    | async                | Yes                | P0       | Badge stats + award side effects visibility               |
| `_on_bonus_applied` (~1068)       | sync    | async                | Yes                | P0       | Bonus period writes                                       |
| `_on_penalty_applied` (~1161)     | sync    | async                | Yes                | P0       | Penalty period writes                                     |
| `_on_data_reset_complete` (~1254) | sync    | async                | Yes                | P0       | Reset completion invalidation path                        |
| `_on_midnight_rollover` (~198)    | sync    | sync (unless needed) | Cache-only         | P3       | Can remain sync if it only invalidates local cache safely |
| `_on_chores_ready` (~361)         | async   | async                | Yes                | Keep     | Baseline already async                                    |

**Batching recommendation**

- Batch S1: P0 handlers only
- Batch S2: P1 handlers
- Batch S3: P2/P3 review handlers

---

### 2) NotificationManager (largest surface area)

**File**: `custom_components/kidschores/managers/notification_manager.py`

| Handler                               | Current | Target | Thread-risk reason                                  | Priority |
| ------------------------------------- | ------- | ------ | --------------------------------------------------- | -------- |
| `_handle_badge_earned` (~1667)        | sync    | async  | Calls async notification sends via task creation    | P0       |
| `_handle_achievement_earned` (~1723)  | sync    | async  | Same pattern                                        | P0       |
| `_handle_challenge_completed` (~1785) | sync    | async  | Same pattern                                        | P0       |
| `_handle_chore_claimed` (~1841)       | sync    | async  | High-volume parent/kid notification path            | P0       |
| `_handle_reward_claimed` (~1966)      | sync    | async  | Approval workflow notifications                     | P0       |
| `_handle_reward_approved` (~2025)     | sync    | async  | Award confirmation sends                            | P1       |
| `_handle_reward_disapproved` (~2067)  | sync    | async  | Disapproval sends                                   | P1       |
| `_handle_chore_disapproved` (~2109)   | sync    | async  | Chore disapproval sends                             | P1       |
| `_handle_chore_approved` (~2151)      | sync    | async  | Chore approval sends                                | P0       |
| `_handle_bonus_applied` (~2220)       | sync    | async  | Bonus event sends                                   | P1       |
| `_handle_penalty_applied` (~2254)     | sync    | async  | Penalty event sends                                 | P1       |
| `_handle_chore_due_window` (~2288)    | sync    | async  | Reminder lock + send path                           | P0       |
| `_handle_chore_due_reminder` (~2359)  | sync    | async  | Reminder lock + send path                           | P0       |
| `_handle_chore_overdue` (~2428)       | sync    | async  | Overdue fan-out path                                | P0       |
| `_handle_chore_missed` (~2591)        | sync    | async  | Missed lock notifications                           | P0       |
| `_handle_chore_deleted` (~2717)       | sync    | async  | Cleanup + possible async notification cleanup calls | P2       |
| `_handle_reward_deleted` (~2761)      | sync    | async  | Cleanup path                                        | P2       |
| `_handle_kid_deleted` (~2798)         | sync    | async  | Cleanup path                                        | P2       |

**Batching recommendation**

- Batch N1: P0 event handlers (user-visible workflows)
- Batch N2: P1 handlers
- Batch N3: P2 cleanup handlers

**Migration note**

- When converting, prefer direct `await` to notification coroutine methods rather than creating tasks from sync context.
- Preserve notification de-duplication/tag semantics and schedule-lock timestamps.

---

### 3) EconomyManager (remaining sync listeners)

**File**: `custom_components/kidschores/managers/economy_manager.py`

| Handler                                         | Current | Target     | Thread-risk reason                                             | Priority |
| ----------------------------------------------- | ------- | ---------- | -------------------------------------------------------------- | -------- |
| `_on_badge_earned` (~158)                       | sync    | async      | Uses `call_soon_threadsafe` wrappers for deposit/bonus/penalty | P0       |
| `_on_achievement_earned` (~252)                 | sync    | async      | Schedules async deposit from sync callback                     | P1       |
| `_on_challenge_completed` (~273)                | sync    | async      | Schedules async deposit from sync callback                     | P1       |
| `_on_points_multiplier_change_requested` (~131) | sync    | review     | Writes + persist but no async awaiting required                | P2       |
| `_on_chore_approved` (~294)                     | async   | keep async | Already compliant                                              | Keep     |
| `_on_chore_auto_approved` (~324)                | async   | keep async | Already compliant                                              | Keep     |
| `_on_reward_approved` (~336)                    | async   | keep async | Already compliant                                              | Keep     |
| `_on_chore_undone` (~364)                       | async   | keep async | Already compliant                                              | Keep     |

**Batching recommendation**

- Batch E1: Convert badge/achievement/challenge handlers first.
- Batch E2: Re-evaluate multiplier change listener only if it touches loop-bound APIs indirectly.

---

### 4) RewardManager

**File**: `custom_components/kidschores/managers/reward_manager.py`

| Handler                  | Current | Target | Thread-risk reason                                   | Priority |
| ------------------------ | ------- | ------ | ---------------------------------------------------- | -------- |
| `_on_badge_earned` (~87) | sync    | async  | Calls persist + update sequence from signal listener | P0       |

**Additional write-path verification points**

- Confirm all paths calling `async_set_updated_data` (around ~125, ~659, ~752, ~977) execute from loop-safe async context after migration.

---

## Sequence plan (implementation order)

1. **Step A**: Statistics P0 conversion (smallest high-value blueprint)
2. **Step B**: Notification P0 conversion
3. **Step C**: Economy + Reward P0 conversion
4. **Step D**: Statistics/Notification remaining P1-P2 conversion
5. **Step E**: Cleanup and removal of obsolete marshaling wrappers
6. **Step F**: Full validation + runtime warning audit

---

## Acceptance criteria per batch

A batch is done only when all are true:

- All handlers in that batch have target callback type.
- No `RuntimeError`/thread warnings are emitted for those event paths during test execution.
- No regression in payload behavior (same keys, same defaults).
- Lint/type checks pass for touched modules.
- Targeted tests for affected domains pass.

---

## Validation mapping

### Fast feedback (per batch)

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/kidschores/`
- `python -m pytest tests/test_workflow_chores.py -v --tb=line`
- `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
- `python -m pytest tests/test_workflow_gaps.py -v --tb=line`

### Final gate (after all batches)

- `python -m pytest tests/ -v --tb=line`
- Manual/automated log audit for thread misuse signatures (`async_create_task`, `async_write_ha_state`, registry/state access from worker thread)

---

## Risk controls during implementation

- **Do not alter signal names or payload schemas** while migrating callback type.
- **Do not combine with feature changes** (award logic changes, dashboard behavior, translations) in the same PR.
- **Retain dedupe and schedule-lock semantics** in notification paths.
- **Keep writes in manager boundaries** per event architecture and CRUD ownership rules.

---

## Handoff checklist for builder agent

- [x] Read parent plan: `docs/in-process/ASYNC_LISTENER_MIGRATION_IN-PROCESS.md`
- [x] Start with Statistics P0 handlers only
- [x] Run fast-feedback validation commands
- [x] Proceed manager-by-manager in listed order
- [x] Run full suite and log audit before marking done
- [x] Update both plan docs with phase percentages and outcomes
