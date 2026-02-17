# Entity Update Architecture — Audit Data

Supporting document for [ENTITY_UPDATE_ARCHITECTURE_COMPLETED.md](ENTITY_UPDATE_ARCHITECTURE_COMPLETED.md)

Status: Completed

## 1. HA Core Entity Update Semantics

### `async_update_listeners()` (update_coordinator.py L197)

```python
def async_update_listeners(self) -> None:
    """Update all registered listeners."""
    for update_callback, _ in list(self._listeners.values()):
        update_callback()
```

- Iterates ALL registered `CoordinatorEntity` listeners
- Each callback triggers HA to call entity's `@property` methods (`native_value`, `extra_state_attributes`)
- Lightweight: ~1ms for 30 entities (no disk I/O, no network)
- **This is the correct method to use** in `_persist_and_update()`

### `async_set_updated_data(data)` (update_coordinator.py L554)

```python
def async_set_updated_data(self, data: _DataT) -> None:
    """Manually update data, notify listeners and reset refresh interval."""
    self._async_unsub_refresh()
    self._debounced_refresh.async_cancel()
    self.data = data
    self.last_update_success = True
    if self._listeners:
        self._schedule_refresh()
    self.async_update_listeners()
```

- Sets `self.data`, resets refresh timer, AND calls `async_update_listeners()`
- **Should NOT be used for KidsChores** because:
  1. Entities read from `coordinator._data` (shared dict), not `coordinator.data`
  2. Resets the coordinator refresh timer unnecessarily
  3. Heavier than needed — `async_update_listeners()` alone is sufficient

### Why `async_update_listeners()` Is Sufficient

KidsChores entities use `@property` pattern:

```python
class KidChoreStatusSensor(KidsChoresCoordinatorEntity, SensorEntity):
    @property
    def native_value(self) -> Any:
        # Reads directly from coordinator._data on every access
        return self.coordinator.chore_manager.get_chore_status_context(...)
```

Since `_data` is a shared mutable dict, changes are immediately visible. The entity just needs to be told to re-evaluate its properties — which is exactly what `async_update_listeners()` does.

---

## 2.5 Misuse of `async_set_updated_data()` (Normalize to `_persist_and_update()`)

These methods currently use the heavier `async_set_updated_data()` instead of `async_update_listeners()`. They are NOT broken (entities DO update), but should be normalized for consistency and to avoid unnecessary coordinator timer resets.

### GamificationManager (10 sites)

| #   | Line      | Method                           | Data Change                    |
| --- | --------- | -------------------------------- | ------------------------------ |
| 1   | 392+405   | `_award_achievement_to_kid()`    | Achievement progress → awarded |
| 2   | 452+465   | `award_challenge()`              | Challenge progress → completed |
| 3   | 1506+1507 | `update_badges_earned_for_kid()` | Badge earned metadata update   |
| 4   | 1733+1734 | `demote_cumulative_badge()`      | Cumulative badge → demoted     |
| 5   | 1811+1812 | `remove_awarded_badges()`        | Badge removed from kid         |
| 6   | 2039+2085 | `remove_awarded_badges_by_id()`  | Badge removed by ID            |
| 7   | 2085+2086 | `_record_badge_earned()`         | Badge tracking recorded        |
| 8   | 3114+3115 | `data_reset_badges()`            | All badge data cleared         |
| 9   | 3197+3198 | `data_reset_achievements()`      | Achievement progress cleared   |
| 10  | 3266+3267 | `data_reset_challenges()`        | Challenge progress cleared     |

### EconomyManager (2 sites)

| #   | Line    | Method            | Data Change                      |
| --- | ------- | ----------------- | -------------------------------- |
| 1   | 749+760 | `apply_penalty()` | Points deducted, penalty applied |
| 2   | 943+954 | `apply_bonus()`   | Points added, bonus applied      |

**Pattern**: All 12 use `_persist()` followed by `async_set_updated_data(self.coordinator._data)` — replacing both lines with a single `_persist_and_update()` call gives the same result with less overhead.

---

### Category A: UI-CRITICAL (13 orphans)

#### A.1: Signal-Chain Relayed (9) — emit() → listener → \_persist()

These have no direct entity update, but emit a signal that listeners catch. However, **no listener in any chain calls `async_update_listeners()`**, so these are still gaps.

| #   | File              | Line | Method                  | Data Change                    | Signal                        | Impact                                                |
| --- | ----------------- | ---- | ----------------------- | ------------------------------ | ----------------------------- | ----------------------------------------------------- |
| 1   | chore_manager.py  | 591  | `claim_chore()`         | Kid chore state → "claimed"    | `CHORE_CLAIMED`               | Dashboard shows stale "pending/due"                   |
| 2   | chore_manager.py  | 923  | `approve_chore()`       | State → "approved", points     | `CHORE_APPROVED`              | Dashboard doesn't show approval                       |
| 3   | chore_manager.py  | 1120 | `disapprove_chore()`    | State → "pending"              | `CHORE_DISAPPROVED`           | Dashboard doesn't show disapproval                    |
| 4   | chore_manager.py  | 4311 | `_mark_chore_missed()`  | Missed counter, timestamp      | `CHORE_MISSED`                | Dashboard doesn't show missed                         |
| 5   | chore_manager.py  | 4666 | `reset_chore_data()`    | All per-kid chore data cleared | `CHORE_DATA_RESET_COMPLETE`   | Dashboard shows old data                              |
| 6   | reward_manager.py | 353  | `claim()`               | Pending count +1               | `REWARD_CLAIMED`              | Reward status stale                                   |
| 7   | reward_manager.py | 472  | `approve_reward()`      | Grant tracking, pending -1     | `REWARD_APPROVED`             | Reward/points stale                                   |
| 8   | reward_manager.py | 593  | `disapprove_reward()`   | Pending -1                     | `REWARD_DISAPPROVED`          | Reward status stale                                   |
| 9   | chore_manager.py  | 1197 | `undo_chore_approval()` | State reverted                 | `CHORE_UNDONE` ⚠️ CONDITIONAL | **BUG**: Signal only fires when `previous_points > 0` |

#### A.2: No Entity Update Chain at All (4) — `CHORE_UPDATED` signal gap

| #   | File             | Line | Method                             | Data Change               | Signal          | Gap Reason                                                       |
| --- | ---------------- | ---- | ---------------------------------- | ------------------------- | --------------- | ---------------------------------------------------------------- |
| 10  | chore_manager.py | 3765 | `transition_completion_criteria()` | Criteria field changes    | `CHORE_UPDATED` | Only GamificationManager listens; it does NOT call entity update |
| 11  | chore_manager.py | 3827 | `advance_rotation()`               | `rotation_current_kid_id` | `CHORE_UPDATED` | Same gap                                                         |
| 12  | chore_manager.py | 3883 | `reset_rotation()`                 | Rotation to first kid     | `CHORE_UPDATED` | Same gap                                                         |
| 13  | chore_manager.py | 3930 | `override_rotation_cycle()`        | `rotation_cycle_override` | `CHORE_UPDATED` | Same gap                                                         |

### Category B: EVENTUALLY-CONSISTENT (6 orphans)

| #   | File                    | Line | Method                             | Data Change                    | Notes                               |
| --- | ----------------------- | ---- | ---------------------------------- | ------------------------------ | ----------------------------------- |
| 14  | chore_manager.py        | 416  | `clean_chore_references_for_kid()` | Per-kid assignment metadata    | Kid already being deleted           |
| 15  | economy_manager.py      | 156  | `_on_multiplier_changed()`         | Points multiplier              | Internal, affects future calcs only |
| 16  | gamification_manager.py | 603  | `_clean_kid_from_gamification()`   | Achievement/challenge kid refs | Kid already being deleted           |
| 17  | statistics_manager.py   | 1415 | `_flush_period_stats()`            | Period bucket data             | Callers handle entity update        |
| 18  | statistics_manager.py   | 1539 | `_flush_period_metrics()`          | Period bucket data             | Callers handle entity update        |
| 19  | user_manager.py         | 94   | `_on_kid_deleted()`                | Parent `associated_kids`       | Kid entities already being removed  |

### Category C: NO-ENTITY-IMPACT (5 orphans)

| #   | File                    | Line | Method                      | Data Change                | Reason                    |
| --- | ----------------------- | ---- | --------------------------- | -------------------------- | ------------------------- |
| 20  | gamification_manager.py | 521  | pending_evaluation_queue    | Internal queue persist     | No entity reads this      |
| 21  | gamification_manager.py | 656  | `_clean_chore_references()` | `selected_chore_id` refs   | Internal targeting config |
| 22  | notification_manager.py | 385  | suppression timestamps      | Notification throttle data | No entity reads this      |
| 23  | notification_manager.py | 414  | clean chore notif records   | Notification metadata      | No entity reads this      |
| 24  | notification_manager.py | 433  | clean kid notif records     | Notification metadata      | No entity reads this      |

### False Positives in Original Scan (15)

| Type                      | Lines                             | Explanation                               |
| ------------------------- | --------------------------------- | ----------------------------------------- |
| Docstring references      | chore_manager 3618, 3628          | Text: "before \_persist()"                |
| Docstring references      | system_manager 203, 235, 267, 299 | Text: "\_persist() called"                |
| Docstring references      | statistics_manager 1316, 1444     | Text: "persist: If True"                  |
| Already has entity update | chore_manager 3396                | `async_update_listeners()` in same block  |
| Already has entity update | economy_manager 749, 943          | `async_update_listeners()` nearby         |
| Already has entity update | gamification_manager 392, 452     | `async_update_listeners()` nearby         |
| Already has entity update | user_manager 644                  | `async_update_listeners()` 10 lines later |

---

## 3. Signal Routing Map (Condensed)

### Signals WITH Active Listeners That Terminate in Entity Update

**None.** Zero signal listener chains terminate in an `async_update_listeners()` call. All entity updates in the codebase come from:

1. Direct `async_update_listeners()` calls in CRUD methods
2. The 5-minute coordinator periodic cycle (`_async_update_data()`)
3. The Phase C.1 quick fix in `_on_periodic_update()` (conditional)

### Entity Update Call Sites (Complete Inventory)

| Location                     | Method                                           | Trigger                           |
| ---------------------------- | ------------------------------------------------ | --------------------------------- |
| coordinator.py:161           | `_async_update_data()`                           | 5-minute periodic cycle           |
| chore_manager.py:315-322     | `_on_periodic_update()`                          | Phase C.1 quick fix (conditional) |
| chore_manager.py (×3)        | create/update/delete chore                       | CRUD operations                   |
| economy_manager.py (×6)      | create/update/delete bonus/penalty               | CRUD operations                   |
| reward_manager.py (×3)       | create/update/delete reward                      | CRUD operations                   |
| gamification_manager.py (×9) | create/update/delete badge/achievement/challenge | CRUD operations                   |
| user_manager.py (×7)         | create/update/delete kid/parent                  | CRUD operations                   |
| options_flow.py (×1)         | options save                                     | Config flow                       |
| datetime.py (×1)             | datetime entity                                  | Platform entity                   |
| select.py (×1)               | select entity                                    | Platform entity                   |

### High-Value Signals (Workflow) — All Missing Entity Updates

| Signal               | Emitter                          | Listeners                                                                              | Entity Update? |
| -------------------- | -------------------------------- | -------------------------------------------------------------------------------------- | -------------- |
| `CHORE_CLAIMED`      | ChoreManager.claim_chore         | UIManager, NotificationManager, StatisticsManager                                      | ❌ None        |
| `CHORE_APPROVED`     | ChoreManager.approve_chore       | EconomyManager, GamificationManager, UIManager, NotificationManager, StatisticsManager | ❌ None        |
| `CHORE_DISAPPROVED`  | ChoreManager.disapprove_chore    | EconomyManager, GamificationManager, StatisticsManager                                 | ❌ None        |
| `CHORE_UNDONE`       | ChoreManager.undo_chore_approval | UIManager, StatisticsManager                                                           | ❌ None        |
| `CHORE_MISSED`       | ChoreManager.\_mark_chore_missed | GamificationManager, NotificationManager, StatisticsManager                            | ❌ None        |
| `REWARD_CLAIMED`     | RewardManager.claim              | UIManager, NotificationManager, StatisticsManager                                      | ❌ None        |
| `REWARD_APPROVED`    | RewardManager.approve_reward     | EconomyManager, GamificationManager, UIManager, NotificationManager, StatisticsManager | ❌ None        |
| `REWARD_DISAPPROVED` | RewardManager.disapprove_reward  | UIManager, NotificationManager, StatisticsManager                                      | ❌ None        |

### Dead/Orphaned Signals

| Signal                    | Status               | Details                                     |
| ------------------------- | -------------------- | ------------------------------------------- |
| `REWARD_STOCK_CHANGED`    | Dead (never emitted) | UIManager listens but no manager emits      |
| `KID_CREATED`             | No listeners         | Emitted by UserManager, nothing subscribes  |
| `PARENT_CREATED`          | No listeners         | Emitted by UserManager, nothing subscribes  |
| `PARENT_UPDATED`          | No listeners         | Emitted by UserManager, nothing subscribes  |
| `CHORE_ROTATION_ADVANCED` | No listeners         | Emitted by ChoreManager, nothing subscribes |

---

## 4. Manager Listener Registrations (Complete)

### ChoreManager (`async_setup`)

- `DATA_READY` → `_on_data_ready()`
- `PERIODIC_UPDATE` → `_on_periodic_update()`
- `MIDNIGHT_ROLLOVER` → `_on_midnight_rollover()`
- `KID_DELETED` → `clean_chore_references_for_kid()`

### EconomyManager (`async_setup`)

- `CHORE_APPROVED` → `_on_chore_approved()` (deposits points)
- `CHORE_DISAPPROVED` → `_on_chore_disapproved()` (reverts points)
- `REWARD_APPROVED` → `_on_reward_approved()` (deducts points)
- `BADGE_EARNED` → `_on_badge_earned()` (deposits bonus)
- `BADGE_DEMOTED` → `_on_badge_demoted()` (no action currently)
- `CHALLENGE_COMPLETED` → `_on_challenge_completed()` (deposits bonus)
- `ACHIEVEMENT_COMPLETED` → `_on_achievement_completed()` (deposits bonus)

### GamificationManager (`async_setup`)

- `STATS_READY` → `_on_stats_ready()`
- `CHORE_APPROVED` → `_on_chore_event()` (evaluates badges)
- `CHORE_DISAPPROVED` → `_on_chore_event()`
- `CHORE_MISSED` → `_on_chore_event()`
- `CHORE_RESET` → `_on_chore_event()`
- `CHORE_UPDATED` → `_on_chore_updated()`
- `POINTS_CHANGED` → `_on_points_changed()`
- `BONUS_APPLIED` → `_on_economy_event()`
- `PENALTY_APPLIED` → `_on_economy_event()`
- `REWARD_APPROVED` → `_on_reward_event()`
- `CHORE_DELETED` → `_clean_chore_references()`
- `KID_DELETED` → `_clean_kid_from_gamification()`

### StatisticsManager (`async_setup`)

- Listens to 24 signals (all major workflow events)
- Accumulates counts, updates period buckets
- Emits `STATS_READY` on startup

### NotificationManager (`async_setup`)

- Listens to 17 signals (all user-facing workflow events)
- Sends push notifications to configured services
- Never emits signals, never calls entity updates

### UIManager (`async_setup`)

- Listens to 11 signals (workflow events + CRUD)
- Updates dashboard helper sensor attributes
- Never emits signals, never calls entity updates

### SystemManager (`async_setup`)

- Listens to `CHORE_DELETED`, `REWARD_DELETED`, `BADGE_DELETED`, `KID_DELETED`
- Cleans orphaned references
- Emits `DATA_READY` on startup, `MIDNIGHT_ROLLOVER` from timer

### UserManager (`async_setup`)

- Listens to `KID_DELETED` → `_on_kid_deleted()` (cleans parent associations)
- Emits kid/parent lifecycle signals
