# Method Migration Map - Supporting Document

**Parent Plan**: [LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md](./LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md)

## Purpose

This document maps every public and significant private method in the current coordinator to its target location in the layered architecture.

---

## Current File Inventory

| File                              | Lines      | Status                        |
| --------------------------------- | ---------- | ----------------------------- |
| `coordinator.py`                  | 6,138      | Refactor to router            |
| `coordinator_chore_operations.py` | 3,971      | Delete after migration        |
| **Total**                         | **10,109** | Target: <1,000 in coordinator |

---

## Coordinator Method Categories

### Category 1: KEEP IN COORDINATOR (Orchestration Layer)

These methods stay in the coordinator as they are about routing, lifecycle, or property access.

| Method                             | Lines   | Reason to Keep                    |
| ---------------------------------- | ------- | --------------------------------- |
| `__init__`                         | 78-134  | Initialization, manager injection |
| `_async_update_data`               | 151-165 | HA coordinator contract           |
| `async_config_entry_first_refresh` | 167-306 | HA lifecycle                      |
| `_persist`                         | 308-377 | Storage persistence               |
| `_get_approval_lock`               | 379-399 | Concurrency infrastructure        |
| `_get_retention_config`            | 401-425 | Config access                     |
| **Properties**                     |         |                                   |
| `kids_data`                        | 427-430 | Data accessor                     |
| `parents_data`                     | 432-435 | Data accessor                     |
| `chores_data`                      | 437-440 | Data accessor                     |
| `badges_data`                      | 442-445 | Data accessor                     |
| `rewards_data`                     | 447-450 | Data accessor                     |
| `penalties_data`                   | 452-455 | Data accessor                     |
| `achievements_data`                | 457-460 | Data accessor                     |
| `challenges_data`                  | 462-465 | Data accessor                     |
| `bonuses_data`                     | 467-470 | Data accessor                     |
| `pending_reward_approvals`         | 472-475 | Data accessor                     |

### Category 2: MOVE TO NotificationManager

| Method                           | Lines     | New Location                                        |
| -------------------------------- | --------- | --------------------------------------------------- |
| `_convert_notification_key`      | 5342-5353 | `notification_manager.convert_key()`                |
| `_format_notification_text`      | 5355-5384 | `notification_manager.format_text()`                |
| `_translate_action_buttons`      | 5386-5428 | `notification_manager.translate_actions()`          |
| `send_kc_notification`           | 5430-5504 | `notification_manager.send()`                       |
| `_notify_kid`                    | 5506-5555 | `notification_manager.send_to_kid()`                |
| `_notify_kid_translated`         | 5557-5613 | `notification_manager.send_to_kid_translated()`     |
| `_notify_parents`                | 5615-5681 | `notification_manager.send_to_parents()`            |
| `_notify_parents_translated`     | 5683-5750 | `notification_manager.send_to_parents_translated()` |
| `clear_notification_for_parents` | ~5755     | `notification_manager.clear_for_parents()`          |

**Also move from `notification_helper.py`:**

- `async_send_notification()` → manager dispatch method
- `build_chore_actions()` → `notification_manager.build_chore_actions()`
- `build_reward_actions()` → `notification_manager.build_reward_actions()`
- `build_extra_data()` → `notification_manager.build_extra_data()`
- `build_notification_tag()` → `notification_manager.build_tag()`

### Category 3: MOVE TO EconomyEngine (Pure Logic)

| Method/Logic           | Source Lines                       | New Method                                  |
| ---------------------- | ---------------------------------- | ------------------------------------------- |
| Point rounding logic   | scattered                          | `EconomyEngine.round_points()`              |
| Multiplier calculation | `_update_point_multiplier_for_kid` | `EconomyEngine.calculate_with_multiplier()` |
| NSF validation         | inline in `redeem_reward`          | `EconomyEngine.validate_sufficient_funds()` |

### Category 4: MOVE TO EconomyManager (Stateful)

| Method                             | Lines     | New Method                                 |
| ---------------------------------- | --------- | ------------------------------------------ |
| `update_kid_points`                | 1431-1608 | `economy_manager.deposit()` / `withdraw()` |
| `_recalculate_point_stats_for_kid` | 1610-1628 | `economy_manager.recalculate_stats()`      |
| `_update_point_multiplier_for_kid` | 3041-3065 | `economy_manager.update_multiplier()`      |

### Category 5: MOVE TO ChoreEngine (Pure Logic)

| Method/Logic                | Source File                       | New Method                               |
| --------------------------- | --------------------------------- | ---------------------------------------- |
| State transition validation | `coordinator_chore_operations.py` | `ChoreEngine.can_transition()`           |
| Point calculation           | `coordinator_chore_operations.py` | `ChoreEngine.calculate_points()`         |
| Shared chore determination  | `coordinator_chore_operations.py` | `ChoreEngine.is_shared_chore()`          |
| Approval requirements check | `coordinator_chore_operations.py` | `ChoreEngine.meets_approval_threshold()` |
| Recurrence calculation      | wraps `schedule_engine`           | `ChoreEngine.get_next_due_date()`        |

### Category 6: MOVE TO ChoreManager (Stateful)

**From `coordinator_chore_operations.py` (43 methods):**

| Section                 | Methods                                                                                                                        | New Location                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| §1 Service Entry Points | `claim_chore`, `approve_chore`, `disapprove_chore`, `complete_chore_for_kid`, `skip_chore`, `undo_chore_claim`, `reset_chores` | `ChoreManager.*`                           |
| §2 Public API           | `chore_has_pending_claim`, `chore_is_overdue`, `get_kids_pending_approval`, etc.                                               | `ChoreManager.*` or `ChoreEngine.*`        |
| §3 Validation           | `_can_claim_chore`, `_can_approve_chore`                                                                                       | `ChoreEngine.can_claim()`, `can_approve()` |
| §4 State Machine        | `_transition_chore_state`, `_handle_state_change`                                                                              | `ChoreEngine.transition_state()`           |
| §5 Data Management      | `_get_chore_data_for_kid`, `_update_chore_data_for_kid`                                                                        | `ChoreManager._get_kid_chore_data()`       |
| §6 Query & Lookup       | Various query methods                                                                                                          | `ChoreManager.*`                           |
| §7 Scheduling           | `_process_due_date_reminders`                                                                                                  | `ChoreManager.process_reminders()`         |
| §8 Recurring Ops        | `_handle_recurring_chore`, `_process_recurring_chores`                                                                         | `ChoreManager.process_recurring()`         |
| §9 Daily Reset          | `_process_midnight_resets`, `_reset_chore_for_kid`                                                                             | `ChoreManager.process_daily_reset()`       |
| §10 Overdue Detection   | `_process_overdue_detection`, `_mark_chore_overdue`                                                                            | `ChoreManager.process_overdue()`           |
| §11 Reminders           | `_send_due_soon_reminder`                                                                                                      | `ChoreManager.send_due_reminder()`         |

### Category 7: MOVE TO GamificationEngine (Pure Logic)

| Method                                  | Lines     | New Method                                           |
| --------------------------------------- | --------- | ---------------------------------------------------- |
| Badge target evaluation logic           | 2591-2826 | `GamificationEngine.evaluate_badge_target()`         |
| `_handle_badge_target_points`           | 2591-2638 | `GamificationEngine._eval_points_target()`           |
| `_handle_badge_target_chore_count`      | 2640-2687 | `GamificationEngine._eval_chore_count()`             |
| `_handle_badge_target_daily_completion` | 2689-2751 | `GamificationEngine._eval_daily_completion()`        |
| `_handle_badge_target_streak`           | 2753-2826 | `GamificationEngine._eval_streak()`                  |
| Achievement progress calculation        | 4958-5060 | `GamificationEngine.evaluate_achievement()`          |
| Challenge progress calculation          | 5157-5230 | `GamificationEngine.evaluate_challenge()`            |
| `_get_cumulative_badge_progress`        | 3496-3627 | `GamificationEngine.calculate_cumulative_progress()` |
| `_get_cumulative_badge_levels`          | 4582-4669 | `GamificationEngine.get_cumulative_levels()`         |

### Category 8: MOVE TO GamificationManager (Stateful)

| Method                                   | Lines     | New Method                                               |
| ---------------------------------------- | --------- | -------------------------------------------------------- |
| `_check_badges_for_kid`                  | 2250-2535 | `gamification_manager.evaluate_badges()`                 |
| `_award_badge`                           | 2828-3015 | `gamification_manager.award_badge()`                     |
| `process_award_items`                    | 3017-3039 | `gamification_manager.process_badge_rewards()`           |
| `_update_badges_earned_for_kid`          | 3067-3158 | `gamification_manager._update_badges_earned()`           |
| `_update_chore_badge_references_for_kid` | 3160-3214 | `gamification_manager._update_chore_references()`        |
| `remove_awarded_badges`                  | 3216-3284 | `gamification_manager.remove_badge()`                    |
| `_remove_awarded_badges_by_id`           | 3286-3482 | `gamification_manager._remove_badge_by_id()`             |
| `_recalculate_all_badges`                | 3484-3494 | `gamification_manager.recalculate_all()`                 |
| `_manage_badge_maintenance`              | 3629-3896 | `gamification_manager.process_maintenance()`             |
| `_sync_badge_progress_for_kid`           | 3898-4263 | `gamification_manager._sync_progress()`                  |
| `_manage_cumulative_badge_maintenance`   | 4265-4580 | `gamification_manager._process_cumulative_maintenance()` |
| `_check_achievements_for_kid`            | 4958-5060 | `gamification_manager.evaluate_achievements()`           |
| `_award_achievement`                     | 5061-5155 | `gamification_manager.award_achievement()`               |
| `_check_challenges_for_kid`              | 5157-5230 | `gamification_manager.evaluate_challenges()`             |
| `_award_challenge`                       | 5233-5303 | `gamification_manager.award_challenge()`                 |
| `_update_streak_progress`                | 5305-5340 | `gamification_manager.update_streak()`                   |

### Category 9: KEEP AS SERVICE FACADES

These coordinator methods become thin wrappers that delegate to managers:

```python
# coordinator.py - thin facades
def approve_chore(self, kid_id: str, chore_id: str, parent_name: str):
    """Facade to ChoreManager.approve()."""
    return await self.chore_manager.approve(kid_id, chore_id, parent_name)

def redeem_reward(self, parent_name: str, kid_id: str, reward_id: str):
    """Facade to EconomyManager/RewardManager."""
    ...
```

### Category 10: MOVE TO kc_helpers.py (Cleanup Utilities)

| Method                                   | Lines   | New Function                         |
| ---------------------------------------- | ------- | ------------------------------------ |
| `_remove_entities_in_ha`                 | 622-646 | `kh.remove_entities_by_id()`         |
| `_cleanup_chore_from_kid`                | 493-510 | `kh.cleanup_chore_from_kid()`        |
| `_cleanup_pending_reward_approvals`      | 512-523 | `kh.cleanup_pending_rewards()`       |
| `_cleanup_deleted_kid_references`        | 525-564 | `kh.cleanup_deleted_kid_refs()`      |
| `_cleanup_deleted_chore_references`      | 566-576 | `kh.cleanup_deleted_chore_refs()`    |
| `_cleanup_parent_assignments`            | 578-590 | `kh.cleanup_parent_assignments()`    |
| `_cleanup_deleted_chore_in_achievements` | 592-602 | `kh.cleanup_chore_in_achievements()` |
| `_cleanup_deleted_chore_in_challenges`   | 604-620 | `kh.cleanup_chore_in_challenges()`   |

### Category 11: KEEP BUT REFACTOR (Entity Lifecycle)

These stay in coordinator but become simpler:

| Method                      | Lines     | Refactor Notes             |
| --------------------------- | --------- | -------------------------- |
| `delete_kid_entity`         | 842-904   | Keep, calls `kh.cleanup_*` |
| `delete_parent_entity`      | 906-939   | Keep, simpler              |
| `delete_chore_entity`       | 941-971   | Keep, calls `kh.cleanup_*` |
| `delete_badge_entity`       | 973-1008  | Keep                       |
| `delete_reward_entity`      | 1010-1035 | Keep                       |
| `delete_penalty_entity`     | 1037-1061 | Keep                       |
| `delete_bonus_entity`       | 1063-1085 | Keep                       |
| `delete_achievement_entity` | 1087-1111 | Keep                       |
| `delete_challenge_entity`   | 1113-1141 | Keep                       |

---

## Migration Priority Order

Based on dependencies and risk:

1. **NotificationManager** (Phase 2)
   - No return values, side-effect only
   - Other managers depend on this for alerts
   - Low risk

2. **EconomyEngine + EconomyManager** (Phase 3)
   - Central to all operations
   - Other managers call `deposit`/`withdraw`
   - Medium risk

3. **ChoreEngine + ChoreManager** (Phase 4)
   - Largest extraction (3,971 lines)
   - Depends on EconomyManager
   - High complexity

4. **GamificationEngine + GamificationManager** (Phase 5)
   - Event listener pattern
   - Depends on all other managers
   - Complex badge logic

---

## Line Count Projections

| Target File                        | Estimated Lines | Source Methods                |
| ---------------------------------- | --------------- | ----------------------------- |
| `coordinator.py`                   | 800-1000        | Infrastructure + facades      |
| `managers/notification_manager.py` | 700-900         | 9 methods + helpers           |
| `managers/economy_manager.py`      | 400-600         | 3 methods + stats             |
| `managers/chore_manager.py`        | 1200-1500       | 43 methods from mixin         |
| `managers/gamification_manager.py` | 1200-1500       | 20+ badge/achievement methods |
| `engines/chore_engine.py`          | 300-400         | State machine + validation    |
| `engines/economy_engine.py`        | 150-250         | Math + ledger                 |
| `engines/gamification_engine.py`   | 500-700         | Evaluation logic              |

**Total projected**: ~5,500-6,500 lines (vs current 10,109)

- **Net reduction**: ~35-45% through deduplication and cleaner patterns
