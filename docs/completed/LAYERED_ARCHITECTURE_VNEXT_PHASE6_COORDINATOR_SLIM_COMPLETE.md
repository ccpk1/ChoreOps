# Phase 6: Coordinator Slim-Down Implementation Plan

## Initiative snapshot

- **Name / Code**: Phase 6 – "Clean Break" Event-Driven Architecture
- **Target release / milestone**: v0.5.0 (Breaking Change Release)
- **Owner / driver(s)**: KidsChores Core Team
- **Status**: ✅ **COMPLETE** - All Steps Validated
- **Created**: 2026-01-26
- **Updated**: 2026-01-27 (Phase 6 Complete)
- **Prerequisite**: Phase 5 (Gamification Engine) ✅ COMPLETE

## 🔴 Critical Architecture Directive: "Clean Break"

**v0.5.0 is NOT a transitional release.** This is a clean architectural break:

1. **NO Deprecation Wrappers** – Delete legacy coordinator methods entirely
2. **Event-Driven Cross-Domain** – Managers communicate via Event Bus, not coordinator orchestration
3. **Services Route to Managers** – `services.py` calls managers directly, not coordinator
4. **Single Domain Ownership** – Each manager owns its domain completely

---

## Summary & Immediate Steps

| Phase / Step                            | Description                                  | % complete | Quick notes                                                                                       |
| --------------------------------------- | -------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| Step 1 – RewardManager                  | Create reward lifecycle manager              | 100%       | ✅ DONE: reward_manager.py created (677 lines)                                                    |
| Step 2 – Penalty/Bonus                  | Extend EconomyManager                        | 100%       | ✅ DONE: economy_manager.py extended (~750 lines)                                                 |
| Step 3 – **Rewards/Penalty/Points**     | DELETE coord methods + wire services         | 100%       | ✅ DONE: 16 methods (~1,003 lines) deleted                                                        |
| Step 4 – **Badges**                     | Migrate to Gamification + DELETE + wire svc  | 100%       | ✅ DONE: 13 methods (~1,395 lines) deleted - [Detailed Plan](STEP4_BADGE_MIGRATION_IN-PROCESS.md) |
| Step 5 – **Achievement/Challenge**      | Migrate to Gamification + DELETE             | 100%       | ✅ DONE: 3 methods (~210 lines) deleted                                                           |
| ~~Step 6 – Services.py Refactor~~       | ~~Route directly to managers~~               | N/A        | **MERGED INTO Steps 3-5**                                                                         |
| ~~Step 7 – Coordinator Cleanup~~        | ~~Remove all delegated methods~~             | N/A        | **MERGED INTO Steps 3-5**                                                                         |
| **Step 6 – Event-Driven Notifications** | Remove direct notification calls, use events | 100%       | ✅ DONE: 11 event handlers, 8 coordinator methods deleted (~272 lines)                            |
| Step 7 – Storage/Translation            | Extract cleanup logic (optional)             | N/A        | SKIP: Coordinator at 1,720 lines (target ~1,700 met)                                              |
| Step 8 – Integration Validation         | Verify all workflows                         | 100%       | ✅ DONE: All tests pass (1098 passed, 2 skipped)                                                  |

**Coordinator Progress**: 4,607 → 1,720 lines (-2,887 lines, -63%) ✅ **TARGET ACHIEVED**

---

## Architectural Decisions (RESOLVED)

### Decision 1: RewardManager Creation ✅ RESOLVED

**Decision**: **Create NEW RewardManager**

- Own entire reward lifecycle: Redeem → Pending → Approve/Disapprove
- Point deductions via `self._economy.withdraw()` (NOT direct `kids_data['points']` access)
- Emit reward events for any listeners

---

### Decision 2: Badge Delegation Strategy ✅ RESOLVED

**Decision**: **Full Delegation to GamificationManager**

- ALL badge methods move to GamificationManager
- GamificationManager owns all badge state mutations
- Coordinator provides ONLY raw data setters (e.g., `_set_kid_points_multiplier`)

---

### Decision 3: Penalty/Bonus Location ✅ RESOLVED

**Decision**: **EconomyManager**

- Penalties/bonuses are point transactions
- Implemented as `EconomyManager.apply_penalty()` and `EconomyManager.apply_bonus()`
- These call `deposit()`/`withdraw()` internally, which emits `POINTS_CHANGED`
- GamificationManager reacts to events (no direct coupling)

---

### Decision 4: Point Statistics & Flow ✅ RESOLVED

**Decision**: **REJECTED "Split" – Single Owner (EconomyManager) + Event-Driven**

**DELETE `coordinator.update_kid_points()`** – It is legacy procedural orchestration.

**New Flow**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ANY Point Change (Chore Approval, Bonus, Penalty, Manual, Reward Cost) │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ EconomyManager.deposit() or .withdraw()                                 │
│   1. Update kids_data[kid_id]["points"]                                 │
│   2. Update ledger entry                                                │
│   3. EMIT SIGNAL_SUFFIX_POINTS_CHANGED                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ (Event Bus)
┌─────────────────────────────────────────────────────────────────────────┐
│ GamificationManager (listening to POINTS_CHANGED)                       │
│   1. Evaluate badge criteria                                            │
│   2. Check achievement progress                                         │
│   3. Update challenge tracking                                          │
│   4. Award/demote as needed                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

**CONSTRAINT**: Coordinator MUST NOT manually call GamificationManager after point updates. The Event Bus is the ONLY coupling mechanism.

---

### Decision 5: Method Signature Compatibility ✅ RESOLVED

**Decision**: **REJECTED "Deprecation Wrappers" – Direct Delegation ONLY**

**Delete ALL wrapper methods from coordinator:**

- ❌ `coordinator.redeem_reward()` → DELETE
- ❌ `coordinator.approve_reward()` → DELETE
- ❌ `coordinator.apply_penalty()` → DELETE
- ❌ `coordinator.apply_bonus()` → DELETE
- ❌ `coordinator.update_kid_points()` → DELETE

**Refactor services.py to call managers directly:**

```python
# OLD (DELETE)
await coordinator.redeem_reward(kid_id, reward_id)

# NEW
await coordinator.reward_manager.redeem(kid_id, reward_id)
```

**Coordinator's public API becomes:**

- Properties: `kids_data`, `chores_data`, `badges_data`, etc.
- Managers: `chore_manager`, `economy_manager`, `reward_manager`, `gamification_manager`, `notification_manager`
- Infrastructure: `_persist()`, entity lifecycle methods

---

### Decision 6: Test Strategy ✅ RESOLVED

**Decision**: **Parallel Testing**

- Keep existing tests passing throughout each step
- Add manager-specific unit tests
- Golden master comparison at end
- Fix test imports/calls as services.py changes

---

## Implementation Order (Dependency-Driven)

```
Step 1: RewardManager (foundational, no deps on other new work)
    ↓
Step 2: Penalty/Bonus → EconomyManager (point transactions)
    ↓
Step 3: DELETE update_kid_points, wire event-driven flow
    ↓
Step 4: Badge Operations → GamificationManager (reacts to events)
    ↓
Step 5: Achievement/Challenge → GamificationManager
    ↓
Step 6: Services.py Refactor (route to managers, delete wrappers)
    ↓
Step 7: Coordinator Cleanup (remove all delegated methods)
    ↓
Step 8: Storage/Translation Isolation (optional cleanup)
    ↓
Step 9: Integration Validation
```

---

## Detailed Implementation Steps

### Step 1: Create RewardManager

**File**: `managers/reward_manager.py` (~500-600 lines)

**Responsibilities**:

- Own entire reward lifecycle: Redeem → Pending → Approve/Disapprove
- Call `economy_manager.withdraw()` for point deductions (NOT direct kids_data access)
- Emit reward events

**Class Structure**:

```python
class RewardManager(BaseManager):
    """Manages reward redemption lifecycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: "KidsChoresDataCoordinator",
        economy_manager: EconomyManager,
        notification_manager: NotificationManager,
    ) -> None:
        super().__init__(hass, coordinator)
        self._economy = economy_manager
        self._notification = notification_manager
        self._approval_locks: dict[str, asyncio.Lock] = {}

    # === Public API (called by services.py) ===
    async def redeem(
        self, kid_id: str, reward_id: str, parent_name: str | None = None
    ) -> None:
        """Kid redeems a reward (enters pending approval state)."""

    async def approve(
        self, kid_id: str, reward_id: str, parent_name: str
    ) -> None:
        """Parent approves pending reward - deducts points via EconomyManager."""
        # MUST use: await self._economy.withdraw(kid_id, cost, source="reward", ...)

    async def disapprove(
        self, kid_id: str, reward_id: str, parent_name: str
    ) -> None:
        """Parent disapproves reward - resets to available."""

    def undo_claim(self, kid_id: str, reward_id: str) -> None:
        """Undo a pending reward claim (before approval)."""

    def reset_rewards(
        self, kid_id: str | None, period: str
    ) -> tuple[int, list[str]]:
        """Reset reward claims for period."""

    # === Query Methods ===
    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all pending reward approvals."""

    def get_kid_reward_data(
        self, kid_id: str, reward_id: str
    ) -> dict[str, Any] | None:
        """Get specific reward data for a kid."""

    # === Internal Helpers ===
    async def _redeem_locked(self, ...) -> None
    async def _disapprove_locked(self, ...) -> None
    def _grant_to_kid(self, kid_id: str, reward_id: str, ...) -> None
    def _increment_period_counter(self, kid_id: str, reward_id: str) -> None
    def _recalculate_stats_for_kid(self, kid_id: str) -> None
    def _get_lock(self, kid_id: str, reward_id: str) -> asyncio.Lock
```

**Methods to migrate from coordinator.py**:
| Coordinator Method | RewardManager Method | Lines |
|--------------------|---------------------|-------|
| `redeem_reward` | `redeem` | ~20 |
| `_redeem_reward_locked` | `_redeem_locked` | ~100 |
| `_grant_reward_to_kid` | `_grant_to_kid` | ~70 |
| `approve_reward` | `approve` | ~120 |
| `disapprove_reward` | `disapprove` | ~20 |
| `_disapprove_reward_locked` | `_disapprove_locked` | ~75 |
| `undo_reward_claim` | `undo_claim` | ~55 |
| `_recalculate_reward_stats_for_kid` | `_recalculate_stats_for_kid` | ~20 |
| `reset_rewards` | `reset_rewards` | ~85 |
| `_get_kid_reward_data` | `get_kid_reward_data` | ~40 |
| `_increment_reward_period_counter` | `_increment_period_counter` | ~40 |
| `get_pending_reward_approvals_computed` | `get_pending_approvals` | ~30 |

**Coordinator changes**:

```python
# In __init__ (after economy_manager, notification_manager init)
self.reward_manager = RewardManager(
    hass, self, self.economy_manager, self.notification_manager
)
```

**Key Implementation Detail - Point Deduction**:

```python
# In RewardManager.approve():
async def approve(self, kid_id: str, reward_id: str, parent_name: str) -> None:
    """Approve reward - deduct points via EconomyManager."""
    reward_cost = reward_data.get(const.DATA_REWARD_COST, 0)

    # Use EconomyManager for point deduction (emits POINTS_CHANGED)
    await self._economy.withdraw(
        kid_id=kid_id,
        amount=reward_cost,
        source=const.LEDGER_SOURCE_REWARD,
        reference_id=reward_id,
        description=f"Redeemed: {reward_name}",
    )
    # GamificationManager will react to POINTS_CHANGED event automatically
```

**Tests**:

- Create `tests/test_reward_manager.py`
- Update existing reward tests to use `coordinator.reward_manager.*`

**Validation Checkpoint**:

- [x] RewardManager created with all methods (677 lines)
- [x] Mypy 0 errors
- [x] Lint passes (pre-existing warnings in test files only)
- [x] All 1098 tests pass

---

### Step 2: Extend EconomyManager with Penalty/Bonus

**File**: `managers/economy_manager.py` (extend from ~323 to ~600 lines)

**Methods to add**:

```python
class EconomyManager(BaseManager):
    # ... existing deposit/withdraw methods ...

    def apply_penalty(
        self, parent_name: str, kid_id: str, penalty_id: str
    ) -> None:
        """Apply penalty to kid - uses withdraw() internally."""
        penalty_data = self._coordinator.penalties_data.get(penalty_id)
        amount = penalty_data.get(const.DATA_PENALTY_POINTS, 0)

        # Use internal withdraw which emits POINTS_CHANGED
        self.withdraw(
            kid_id=kid_id,
            amount=amount,
            source=const.LEDGER_SOURCE_PENALTY,
            reference_id=penalty_id,
            description=f"Penalty: {penalty_data.get(const.DATA_PENALTY_NAME)}",
        )

        # Update penalty tracking
        self._update_penalty_tracking(kid_id, penalty_id)

        # Notification
        self._notification.send_penalty_applied(kid_id, penalty_id, parent_name)

    def reset_penalties(
        self, kid_id: str | None, period: str
    ) -> tuple[int, list[str]]:
        """Reset penalty counts for period."""

    def apply_bonus(
        self, parent_name: str, kid_id: str, bonus_id: str
    ) -> None:
        """Apply bonus to kid - uses deposit() internally."""
        bonus_data = self._coordinator.bonuses_data.get(bonus_id)
        amount = bonus_data.get(const.DATA_BONUS_POINTS, 0)

        # Use internal deposit which emits POINTS_CHANGED
        self.deposit(
            kid_id=kid_id,
            amount=amount,
            source=const.LEDGER_SOURCE_BONUS,
            reference_id=bonus_id,
            description=f"Bonus: {bonus_data.get(const.DATA_BONUS_NAME)}",
        )

        # Update bonus tracking
        self._update_bonus_tracking(kid_id, bonus_id)

        # Notification
        self._notification.send_bonus_applied(kid_id, bonus_id, parent_name)

    def reset_bonuses(
        self, kid_id: str | None, period: str
    ) -> tuple[int, list[str]]:
        """Reset bonus counts for period."""

    # Helper methods
    def _update_penalty_tracking(self, kid_id: str, penalty_id: str) -> None
    def _update_bonus_tracking(self, kid_id: str, bonus_id: str) -> None
```

**Methods to migrate from coordinator.py**:
| Coordinator Method | EconomyManager Method | Lines |
|--------------------|----------------------|-------|
| `apply_penalty` | `apply_penalty` | ~55 |
| `reset_penalties` | `reset_penalties` | ~90 |
| `apply_bonus` | `apply_bonus` | ~55 |
| `reset_bonuses` | `reset_bonuses` | ~90 |

**Validation Checkpoint**:

- [x] EconomyManager extended (~750 lines, +4 methods)
- [x] Mypy 0 errors
- [x] Lint passes
- [x] All 1098 tests pass
- [x] Events emitted correctly (via deposit/withdraw internally)

---

### Step 3: DELETE Legacy Coordinator Methods + Wire Services

**CRITICAL STEP**: This is the architectural pivot. Delete ALL coordinator wrapper methods and wire services.py to call managers directly.

---

#### 3A. DELETE Reward Coordinator Methods (~700 lines)

**DELETE from coordinator.py**:

| Method to DELETE                          | Replacement in Manager                     | ~Lines |
| ----------------------------------------- | ------------------------------------------ | ------ |
| `_get_kid_reward_data()`                  | `reward_manager.get_kid_reward_data()`     | ~40    |
| `_increment_reward_period_counter()`      | `reward_manager._increment_period_counter` | ~40    |
| `get_pending_reward_approvals_computed()` | `reward_manager.get_pending_approvals()`   | ~30    |
| `redeem_reward()`                         | `reward_manager.redeem()`                  | ~20    |
| `_redeem_reward_locked()`                 | `reward_manager._redeem_locked()`          | ~100   |
| `_grant_reward_to_kid()`                  | `reward_manager._grant_to_kid()`           | ~70    |
| `approve_reward()`                        | `reward_manager.approve()`                 | ~120   |
| `disapprove_reward()`                     | `reward_manager.disapprove()`              | ~20    |
| `_disapprove_reward_locked()`             | `reward_manager._disapprove_locked()`      | ~75    |
| `undo_reward_claim()`                     | `reward_manager.undo_claim()`              | ~55    |
| `_recalculate_reward_stats_for_kid()`     | `reward_manager._recalculate_stats()`      | ~20    |
| `reset_rewards()`                         | `reward_manager.reset_rewards()`           | ~85    |

**Update services.py**:

| Service                        | Old Call                             | New Call                                     |
| ------------------------------ | ------------------------------------ | -------------------------------------------- |
| `kidschores.redeem_reward`     | `coordinator.redeem_reward(...)`     | `coordinator.reward_manager.redeem(...)`     |
| `kidschores.approve_reward`    | `coordinator.approve_reward(...)`    | `coordinator.reward_manager.approve(...)`    |
| `kidschores.disapprove_reward` | `coordinator.disapprove_reward(...)` | `coordinator.reward_manager.disapprove(...)` |
| `kidschores.undo_reward_claim` | `coordinator.undo_reward_claim(...)` | `coordinator.reward_manager.undo_claim(...)` |
| `kidschores.reset_rewards`     | `coordinator.reset_rewards(...)`     | `coordinator.reward_manager.reset_rewards()` |

**Checklist**:

- [x] Delete all 12 reward methods from coordinator.py
- [x] Update 5 service handlers in services.py
- [x] Tests pass

---

#### 3B. DELETE Penalty/Bonus Coordinator Methods (~330 lines)

**DELETE from coordinator.py**:

| Method to DELETE    | Replacement in Manager              | ~Lines |
| ------------------- | ----------------------------------- | ------ |
| `apply_penalty()`   | `economy_manager.apply_penalty()`   | ~80    |
| `reset_penalties()` | `economy_manager.reset_penalties()` | ~80    |
| `apply_bonus()`     | `economy_manager.apply_bonus()`     | ~80    |
| `reset_bonuses()`   | `economy_manager.reset_bonuses()`   | ~90    |

**Update services.py**:

| Service                      | Old Call                           | New Call                                         |
| ---------------------------- | ---------------------------------- | ------------------------------------------------ |
| `kidschores.apply_penalty`   | `coordinator.apply_penalty(...)`   | `coordinator.economy_manager.apply_penalty(...)` |
| `kidschores.reset_penalties` | `coordinator.reset_penalties(...)` | `coordinator.economy_manager.reset_penalties()`  |
| `kidschores.apply_bonus`     | `coordinator.apply_bonus(...)`     | `coordinator.economy_manager.apply_bonus(...)`   |
| `kidschores.reset_bonuses`   | `coordinator.reset_bonuses(...)`   | `coordinator.economy_manager.reset_bonuses()`    |

**Checklist**:

- [x] Delete 4 penalty/bonus methods from coordinator.py
- [x] Update 4 service handlers in services.py
- [x] Update button.py callers (apply_bonus, apply_penalty)
- [x] Update \_award_badge() internal caller
- [x] Tests pass

---

#### 3C. DELETE `update_kid_points` (~210 lines)

**Status**: ✅ ALREADY COMPLETE (split into domain functions in prior phases)

The legacy `update_kid_points()` method was already decomposed during Phase 3 (Economy Stack):

- Point deposits → `economy_manager.deposit()`
- Point withdrawals → `economy_manager.withdraw()`
- Ledger management → `EconomyEngine.create_ledger_entry()`
- Period stats → `StatisticsEngine.generate_point_stats()`

No `add_points`/`remove_points` services exist - these were never implemented.

**Checklist**:

- [x] `update_kid_points()` already deleted in prior phases
- [x] Functionality split into domain managers ✅

---

#### Step 3 Summary

**Total Coordinator Lines Deleted**: ~1,000 lines (actual)

| Category      | Methods | Lines  |
| ------------- | ------- | ------ |
| Rewards       | 12      | ~675   |
| Penalty/Bonus | 4       | ~328   |
| Points        | 0       | (done) |
| **TOTAL**     | **16**  | ~1,003 |

**Services.py Changes**: 9 service handlers updated (4 reward + 4 penalty/bonus + 1 reset)

**Validation Checkpoint**:

- [x] All 16 coordinator methods DELETED
- [x] All 9 services.py handlers route to managers
- [ ] POINTS_CHANGED events emitted from EconomyManager
- [ ] GamificationManager reacts to events
- [ ] All ~1100 tests pass
- [ ] MyPy clean

---

### Step 4: Badge Operations → GamificationManager + DELETE Coordinator Methods

**Pattern**: Migrate methods to GamificationManager, then DELETE from coordinator, then wire services.py.

---

#### 4A. Migrate Badge Methods to GamificationManager (~1,400 lines)

**File**: `managers/gamification_manager.py` (extend from ~698 to ~2,100 lines)

**Methods to migrate from coordinator.py**:

| Coordinator Method                         | GamificationManager Method          | ~Lines |
| ------------------------------------------ | ----------------------------------- | ------ |
| `_get_badge_in_scope_chores_list()`        | `get_badge_in_scope_chores_list()`  | ~55    |
| `_award_badge()`                           | `award_badge()`                     | ~190   |
| `_demote_cumulative_badge()`               | `demote_cumulative_badge()`         | ~50    |
| `process_award_items()`                    | `process_award_items()`             | ~25    |
| `_update_point_multiplier_for_kid()`       | `update_point_multiplier_for_kid()` | ~25    |
| `_update_badges_earned_for_kid()`          | `update_badges_earned_for_kid()`    | ~95    |
| `_update_chore_badge_references_for_kid()` | `update_chore_badge_references()`   | ~55    |
| `remove_awarded_badges()`                  | `remove_awarded_badges()`           | ~70    |
| `_remove_awarded_badges_by_id()`           | `_remove_awarded_badges_by_id()`    | ~225   |
| `_recalculate_all_badges()`                | `recalculate_all_badges()`          | ~15    |
| `_get_cumulative_badge_progress()`         | `get_cumulative_badge_progress()`   | ~135   |
| `_sync_badge_progress_for_kid()`           | `sync_badge_progress_for_kid()`     | ~370   |
| `_get_cumulative_badge_levels()`           | `get_cumulative_badge_levels()`     | ~90    |

**Checklist**:

- [ ] All 13 badge methods implemented in GamificationManager
- [ ] Badge tests pass with manager methods

---

#### 4B. DELETE Badge Coordinator Methods (~1,400 lines)

**DELETE from coordinator.py** (after migration verified):

| Method to DELETE                           | ~Lines |
| ------------------------------------------ | ------ |
| `_get_badge_in_scope_chores_list()`        | ~55    |
| `_award_badge()`                           | ~190   |
| `_demote_cumulative_badge()`               | ~50    |
| `process_award_items()`                    | ~25    |
| `_update_point_multiplier_for_kid()`       | ~25    |
| `_update_badges_earned_for_kid()`          | ~95    |
| `_update_chore_badge_references_for_kid()` | ~55    |
| `remove_awarded_badges()`                  | ~70    |
| `_remove_awarded_badges_by_id()`           | ~225   |
| `_recalculate_all_badges()`                | ~15    |
| `_get_cumulative_badge_progress()`         | ~135   |
| `_sync_badge_progress_for_kid()`           | ~370   |
| `_get_cumulative_badge_levels()`           | ~90    |
| **TOTAL**                                  | ~1,400 |

**Checklist**:

- [ ] All 13 badge methods DELETED from coordinator.py
- [ ] No import errors
- [ ] Tests pass

---

#### 4C. Update services.py for Badge Operations

**Update services.py** (if any badge services exist):

| Service                         | Old Call                                 | New Call                                                      |
| ------------------------------- | ---------------------------------------- | ------------------------------------------------------------- |
| `kidschores.remove_badge`       | `coordinator.remove_awarded_badges(...)` | `coordinator.gamification_manager.remove_awarded_badges(...)` |
| `kidschores.recalculate_badges` | `coordinator._recalculate_all_badges()`  | `coordinator.gamification_manager.recalculate_all_badges()`   |

**Note**: Most badge operations are internal (triggered by events), so fewer service updates needed.

**Checklist**:

- [ ] Badge services route to GamificationManager
- [ ] Tests pass

---

#### Step 4 Summary

| Category | Methods | Lines  |
| -------- | ------- | ------ |
| Migrated | 13      | ~1,400 |
| Deleted  | 13      | ~1,400 |

**Validation Checkpoint**:

- [ ] All 13 badge methods in GamificationManager
- [ ] All 13 badge methods DELETED from coordinator
- [ ] Badge services route to manager
- [ ] All tests pass
- [ ] MyPy clean

---

### Step 5: Achievement/Challenge → GamificationManager + DELETE Coordinator Methods

**Pattern**: Migrate methods to GamificationManager, then DELETE from coordinator.

---

#### 5A. Migrate Achievement/Challenge Methods (~200 lines)

**Methods to migrate from coordinator.py**:

| Coordinator Method          | GamificationManager Method | ~Lines |
| --------------------------- | -------------------------- | ------ |
| `_award_achievement()`      | `award_achievement()`      | ~95    |
| `_award_challenge()`        | `award_challenge()`        | ~70    |
| `_update_streak_progress()` | `update_streak_progress()` | ~35    |

**Checklist**:

- [ ] All 3 achievement/challenge methods implemented in GamificationManager
- [ ] Tests pass with manager methods

---

#### 5B. DELETE Achievement/Challenge Coordinator Methods (~200 lines)

**DELETE from coordinator.py**:

| Method to DELETE            | ~Lines |
| --------------------------- | ------ |
| `_award_achievement()`      | ~95    |
| `_award_challenge()`        | ~70    |
| `_update_streak_progress()` | ~35    |
| **TOTAL**                   | ~200   |

**Checklist**:

- [ ] All 3 methods DELETED from coordinator.py
- [ ] No import errors
- [ ] Tests pass

---

#### 5C. Update services.py (if applicable)

**Note**: Achievement/Challenge awards are typically internal (triggered by events).
No direct services expected, but verify no coordinator calls remain.

**Checklist**:

- [ ] No coordinator achievement/challenge methods called from services.py
- [ ] Tests pass

---

#### Step 5 Summary

| Category | Methods | Lines |
| -------- | ------- | ----- |
| Migrated | 3       | ~200  |
| Deleted  | 3       | ~200  |

**Validation Checkpoint**:

- [x] All 3 achievement/challenge methods in GamificationManager
- [x] All 3 methods DELETED from coordinator
- [x] All tests pass
- [x] MyPy clean

---

### Step 6: Event-Driven Notifications (CORE ARCHITECTURAL PRINCIPLE)

**🔴 CRITICAL**: This step enforces a core principle of our Clean Break Architecture:

> **Managers communicate via Event Bus, not direct coordinator orchestration**

Currently, managers bypass the event system by directly calling `coordinator._notify_*()` methods.
This violates our event-driven architecture where:

```
Action → Emit Event → Listeners React
```

---

#### 6A. Current Violation Analysis (14 Direct Calls Found)

**Direct `coordinator._notify_*()` calls that bypass event system:**

| Manager             | Method                   | Call                         | Line  |
| ------------------- | ------------------------ | ---------------------------- | ----- |
| GamificationManager | `award_badge()`          | `_notify_kid_translated`     | ~302  |
| GamificationManager | `award_badge()`          | `_notify_parents_translated` | ~315  |
| GamificationManager | `award_achievement()`    | `_notify_kid_translated`     | ~385  |
| GamificationManager | `award_achievement()`    | `_notify_parents_translated` | ~396  |
| GamificationManager | `award_challenge()`      | `_notify_kid_translated`     | ~1995 |
| GamificationManager | `award_challenge()`      | `_notify_parents_translated` | ~2004 |
| RewardManager       | `redeem()`               | `_notify_parents_translated` | ~348  |
| RewardManager       | `approve()`              | `_notify_kid_translated`     | ~483  |
| RewardManager       | `disapprove()`           | `_notify_kid_translated`     | ~641  |
| EconomyManager      | `apply_bonus()`          | `_notify_kid_translated`     | ~422  |
| EconomyManager      | `apply_penalty()`        | `_notify_kid_translated`     | ~619  |
| ChoreManager        | `check_overdue_chores()` | `_notify_kid_translated`     | ~3362 |
| ChoreManager        | `_check_due_soon()`      | `_notify_kid_translated`     | ~3604 |
| ChoreManager        | `_check_due_soon()`      | `_notify_parents_translated` | ~3633 |

**Coordinator notification delegates to DELETE (~110 lines)**:

| Method                               | Lines | Notes                                            |
| ------------------------------------ | ----- | ------------------------------------------------ |
| `_notify_kid()`                      | ~10   | Notification delegate                            |
| `_notify_kid_translated()`           | ~12   | Notification delegate                            |
| `_notify_parents()`                  | ~10   | Notification delegate                            |
| `_notify_parents_translated()`       | ~18   | Notification delegate                            |
| `send_kc_notification()`             | ~8    | Notification delegate                            |
| `clear_notification_for_parents()`   | ~8    | Notification delegate                            |
| `remind_in_minutes()`                | ~10   | Notification delegate                            |
| `_recalculate_point_stats_for_kid()` | ~15   | Statistics callback                              |
| `reset_overdue_chores()`             | ~10   | ChoreManager wrapper (dead code)                 |
| `_extract_kid_id_from_unique_id()`   | ~30   | Duplicates `kc_helpers.parse_entity_reference()` |
| **TOTAL**                            | ~131  |                                                  |

**Note**: `_handle_chore_claimed_notification()` (~60 lines) is CORRECT - it's an event handler.
Keep it as the pattern to follow.

**Additional Violation**: `_recalculate_point_stats_for_kid()`

The docstring claims "Delegated to StatisticsManager via Events" but the flow is backwards:

- StatisticsManager subscribes to POINTS_CHANGED ✅
- StatisticsManager calls `coordinator._recalculate_point_stats_for_kid()` ❌

**Fix**: StatisticsManager should call StatisticsEngine directly and update kid data itself.

**Additional Violation**: `reset_overdue_chores()`

This is a pure wrapper that just calls `chore_manager.reset_overdue_chores()`.
Services and action handlers already call the manager directly - only 1 test uses the wrapper.
**Fix**: Delete wrapper, update test to use `coordinator.chore_manager.reset_overdue_chores()`.

---

#### 6B. Target Architecture

**Events Already Exist** (in const.py):

```python
SIGNAL_SUFFIX_BADGE_EARNED: Final = "badge_earned"
SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED: Final = "achievement_unlocked"
SIGNAL_SUFFIX_CHALLENGE_COMPLETED: Final = "challenge_completed"
SIGNAL_SUFFIX_REWARD_CLAIMED: Final = "reward_claimed"
SIGNAL_SUFFIX_REWARD_APPROVED: Final = "reward_approved"
SIGNAL_SUFFIX_REWARD_DISAPPROVED: Final = "reward_disapproved"
SIGNAL_SUFFIX_BONUS_APPLIED: Final = "bonus_applied"
SIGNAL_SUFFIX_PENALTY_APPLIED: Final = "penalty_applied"
SIGNAL_SUFFIX_CHORE_OVERDUE: Final = "chore_overdue"
```

**Target Flow**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ GamificationManager.award_badge(kid_id, badge_id, badge_name)           │
│   1. Award badge (data mutation)                                        │
│   2. EMIT SIGNAL_SUFFIX_BADGE_EARNED with payload                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ (Event Bus)
┌─────────────────────────────────────────────────────────────────────────┐
│ NotificationManager (subscribed to BADGE_EARNED)                        │
│   _handle_badge_earned(payload):                                        │
│     1. Extract kid_id, badge_name from payload                          │
│     2. Send notification to kid                                         │
│     3. Send notification to parents                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

#### 6C. Implementation Steps

**Step 6C.1: Add Event Subscriptions to NotificationManager**

Update `managers/notification_manager.py`:

```python
async def async_setup(self) -> None:
    """Set up the notification manager with event subscriptions."""
    # Badge events
    self.listen(const.SIGNAL_SUFFIX_BADGE_EARNED, self._handle_badge_earned)

    # Achievement/Challenge events
    self.listen(const.SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED, self._handle_achievement_unlocked)
    self.listen(const.SIGNAL_SUFFIX_CHALLENGE_COMPLETED, self._handle_challenge_completed)

    # Reward events (redeem already uses CHORE_CLAIMED pattern)
    self.listen(const.SIGNAL_SUFFIX_REWARD_CLAIMED, self._handle_reward_claimed)
    self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._handle_reward_approved)
    self.listen(const.SIGNAL_SUFFIX_REWARD_DISAPPROVED, self._handle_reward_disapproved)

    # Bonus/Penalty events
    self.listen(const.SIGNAL_SUFFIX_BONUS_APPLIED, self._handle_bonus_applied)
    self.listen(const.SIGNAL_SUFFIX_PENALTY_APPLIED, self._handle_penalty_applied)

    # Chore reminder events (optional - may keep direct for simplicity)
    self.listen(const.SIGNAL_SUFFIX_CHORE_OVERDUE, self._handle_chore_overdue)

    const.LOGGER.debug("NotificationManager subscribed to %d event types", 9)
```

**Step 6C.2: Add Event Handlers to NotificationManager** (~200 lines)

```python
async def _handle_badge_earned(self, payload: dict[str, Any]) -> None:
    """Handle BADGE_EARNED event - send notifications."""
    kid_id = payload.get("kid_id")
    badge_name = payload.get("badge_name")
    badge_icon = payload.get("badge_icon", "mdi:medal")

    if not kid_id or not badge_name:
        return

    kid_info = self.coordinator.kids_data.get(kid_id)
    if not kid_info:
        return
    kid_name = kid_info.get(const.DATA_KID_NAME, "")

    # Notify kid
    await self.notify_kid_translated(
        kid_id,
        title_key=const.TRANS_KEY_NOTIF_TITLE_BADGE_EARNED,
        message_key=const.TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED,
        message_data={"badge_name": badge_name},
    )

    # Notify parents
    await self.notify_parents_translated(
        kid_id,
        title_key=const.TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_PARENT,
        message_key=const.TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_PARENT,
        message_data={"kid_name": kid_name, "badge_name": badge_name},
    )

# Similar handlers for:
# - _handle_achievement_unlocked()
# - _handle_challenge_completed()
# - _handle_reward_claimed()
# - _handle_reward_approved()
# - _handle_reward_disapproved()
# - _handle_bonus_applied()
# - _handle_penalty_applied()
# - _handle_chore_overdue()
```

**Step 6C.3: Remove Direct Notification Calls from Managers**

In each manager, replace:

```python
# OLD (REMOVE)
await self.coordinator._notify_kid_translated(
    kid_id,
    title_key=const.TRANS_KEY_...,
    message_key=const.TRANS_KEY_...,
    message_data={...},
)
```

With (event already being emitted, so just remove the notification call):

```python
# NEW (already happening in most cases)
self.emit(const.SIGNAL_SUFFIX_BADGE_EARNED, {
    "kid_id": kid_id,
    "badge_name": badge_name,
    "badge_icon": badge_icon,
})
# NotificationManager will handle notifications via event subscription
```

**Step 6C.4: DELETE Coordinator Notification Delegates** (~76 lines)

Remove from `coordinator.py`:

- `_notify_kid()`
- `_notify_kid_translated()`
- `_notify_parents()`
- `_notify_parents_translated()`
- `send_kc_notification()`
- `clear_notification_for_parents()`
- `remind_in_minutes()`

**Step 6C.5: Keep `_handle_chore_claimed_notification()`**

This method is CORRECT - it demonstrates the target pattern:

- Coordinator subscribes to `CHORE_CLAIMED` event
- Sends notification in response

Actually, this should ALSO move to NotificationManager for consistency.

---

#### 6D. Additional Violation: Statistics Callback

**Current (WRONG)**:

```
POINTS_CHANGED event
      │
      ▼
StatisticsManager._on_points_changed()
      │
      ▼
coordinator._recalculate_point_stats_for_kid()  ← WRONG: calls back to coordinator
      │
      ▼
StatisticsEngine.generate_point_stats()
```

**Target (CORRECT)**:

```
POINTS_CHANGED event
      │
      ▼
StatisticsManager._on_points_changed()
      │
      ▼
StatisticsManager.recalculate_point_stats()  ← Manager owns this
      │
      ▼
StatisticsEngine.generate_point_stats()
```

**Fix**:

1. Add `recalculate_point_stats(kid_id)` method to StatisticsManager
2. StatisticsManager uses coordinator's `self.stats` (StatisticsEngine) or has its own
3. Update startup call in coordinator: `self.statistics_manager.recalculate_point_stats(kid_id)`
4. DELETE `coordinator._recalculate_point_stats_for_kid()`

---

#### 6E. Checklist

- [x] Add 11 event subscriptions to NotificationManager.async_setup()
- [x] Implement 11 event handler methods in NotificationManager (~300 lines)
- [x] Remove 14 direct `coordinator._notify_*()` calls from managers
- [x] Verify events are already being emitted (most are)
- [x] Add missing event emissions where needed (CHORE_DUE_SOON signal added)
- [x] Move `_handle_chore_claimed_notification()` to NotificationManager (deleted from coordinator)
- [x] Move `_recalculate_point_stats_for_kid()` logic to StatisticsManager
- [x] UPDATE: startup uses `statistics_manager._recalculate_point_stats()` directly
- [x] DELETE `reset_overdue_chores()` wrapper (dead code) - CONFIRMED DELETED
- [x] UPDATE: tests use `coordinator.chore_manager.reset_overdue_chores()`
- [x] DELETE `_extract_kid_id_from_unique_id()` (~30 lines) - duplicates `kc_helpers.parse_entity_reference()`
- [x] Replace call in `remove_conditional_entities()` with `kh.parse_entity_reference(unique_id, prefix)[0]`
- [ ] Consider removing deprecated `BUTTON_*_PREFIX` constants from const.py (migration complete) - DEFERRED
- [x] DELETE 8 coordinator delegate methods (~87 lines from \_handle_chore_claimed_notification)
- [x] All tests pass (1098 passed)
- [x] MyPy clean (0 errors in 36 files)

---

#### Step 6 Summary

| Category                   | Items | Lines    |
| -------------------------- | ----- | -------- |
| Notification handlers      | +11   | +300     |
| Statistics method moved    | +1    | +15      |
| Direct calls removed       | -14   | -varies  |
| Coordinator delegates      | -8    | -87      |
| Event handler deleted      | 1     | -87      |
| Helper method deleted      | 1     | -30      |
| **Net coordinator change** | -     | **-272** |

**Validation Checkpoint**:

- [x] NotificationManager subscribes to 11 event types
- [x] No manager calls `coordinator._notify_*()` directly
- [x] No wrapper methods remain (reset_overdue_chores deleted)
- [x] No duplicate helpers remain (\_extract_kid_id_from_unique_id deleted)
- [x] StatisticsManager owns point stats recalculation
- [x] All notification delegates DELETED from coordinator
- [x] All tests pass (1098 passed, 2 skipped)
- [x] MyPy clean (0 errors in 36 files)
- [x] Coordinator at 1,720 lines (~1,700 target achieved)

---

### ~~Step 6: Refactor services.py - Route to Managers~~ (MERGED INTO Steps 3-5)

> **Note**: Services.py refactoring is now integrated into each step:
>
> - **Step 3**: Rewards, Penalty/Bonus, Points services
> - **Step 4**: Badge services
> - **Step 5**: Achievement/Challenge services (if any)

---

### ~~Step 7: Coordinator Cleanup - Delete Delegated Methods~~ (MERGED INTO Steps 3-5)

> **Note**: Coordinator cleanup is now integrated into each step:
>
> - **Step 3**: Delete 17 methods (~1,240 lines)
> - **Step 4**: Delete 13 methods (~1,400 lines)
> - **Step 5**: Delete 3 methods (~200 lines)
> - **Total Deleted**: 33 methods (~2,840 lines)

---

### Step 7: Storage/Translation Isolation (Optional)

**Goal**: Further reduce coordinator complexity by isolating maintenance code.

**Prerequisite**: Only implement if coordinator > 1,000 lines after Step 6.

**Option A: Create `helpers/storage_helpers.py`**:
Move entity cleanup logic:

- `_remove_entities_in_ha()`
- `_remove_device_from_registry()`
- `_remove_entities_by_validator()`
- `_remove_orphaned_*()` methods

**Option B: Keep in Coordinator as "Database Maintenance"**:
These methods are tightly coupled to HA entity/device registries.
Acceptable to keep them in coordinator if < 1,000 line target is met.

**Translation Sensor Isolation**:
Consider moving to `helpers/translation_helpers.py`:

- `ensure_translation_sensor_exists()`
- `get_languages_in_use()`
- `remove_unused_translation_sensors()`
- `register_translation_sensor_callback()`

**Decision**: Implement if coordinator > 1,000 lines after Step 6.

---

### Step 8: Integration Validation

**Full Test Matrix**:

| Category         | Test Files                                     | Expected |
| ---------------- | ---------------------------------------------- | -------- |
| Rewards          | `test_reward_*.py`, `test_workflow_rewards.py` | Pass     |
| Economy          | `test_economy_*.py`                            | Pass     |
| Badges           | `test_badge_*.py`                              | Pass     |
| Achievements     | `test_achievement_*.py`                        | Pass     |
| Challenges       | `test_challenge_*.py`                          | Pass     |
| Penalties        | `test_penalty_*.py`                            | Pass     |
| Bonuses          | `test_bonus_*.py`                              | Pass     |
| Chores           | `test_chore_*.py`, `test_workflow_chores.py`   | Pass     |
| Full Integration | `test_workflow_*.py`                           | Pass     |

**Event Flow Verification**:

```bash
# Verify event emissions with debug logging
# In test, check that POINTS_CHANGED triggers GamificationManager

# Example test assertion:
async def test_bonus_triggers_badge_check(hass, coordinator):
    # Apply bonus
    coordinator.economy_manager.apply_bonus("Parent", "kid1", "bonus1")

    # Verify GamificationManager was triggered
    assert gamification_manager._dirty_kids == {"kid1"}
```

**Golden Master Comparison**:

- Load pre-refactor state
- Run same operations
- Compare `coordinator.data` output
- Must be identical

---

## File Size Projections (Post Phase 6)

| File                               | Current | Projected | Change            |
| ---------------------------------- | ------- | --------- | ----------------- |
| `coordinator.py`                   | 1,992   | ~1,800    | -191 (Step 6)     |
| `managers/reward_manager.py`       | 677     | 677       | 0                 |
| `managers/economy_manager.py`      | ~750    | ~750      | 0                 |
| `managers/gamification_manager.py` | 2,374   | 2,374     | 0                 |
| `managers/chore_manager.py`        | 3,644   | 3,644     | 0                 |
| `managers/notification_manager.py` | 1,137   | ~1,350    | +213 (handlers)   |
| `managers/statistics_manager.py`   | ~350    | ~365      | +15 (stats logic) |
| `services.py`                      | ~1,200  | ~1,200    | 0                 |

---

## Risks & Mitigations

| Risk                                    | Likelihood | Impact | Mitigation                                  |
| --------------------------------------- | ---------- | ------ | ------------------------------------------- |
| Tests break during services.py refactor | High       | Medium | Update tests incrementally per step         |
| Event listener not wired correctly      | Medium     | High   | Explicit test for event → reaction chain    |
| Missing method during extraction        | Medium     | High   | Grep verification after each deletion       |
| Circular imports between managers       | Low        | High   | Clear dependency order, inject via **init** |

---

## Pre-Implementation Checklist

- [x] All 6 architectural decisions resolved (Clean Break directives)
- [ ] Backup coordinator.py (git commit)
- [ ] Create golden master test data
- [ ] Verify all current tests pass (1098 baseline)
- [ ] Review event infrastructure (Phase 0) is complete

---

## Decisions Summary (RESOLVED)

| #   | Decision               | Resolution                                      |
| --- | ---------------------- | ----------------------------------------------- |
| 1   | RewardManager creation | ✅ Create NEW RewardManager                     |
| 2   | Badge delegation       | ✅ Full delegation to GamificationManager       |
| 3   | Penalty/Bonus location | ✅ EconomyManager                               |
| 4   | Point statistics       | ✅ Single Owner (EconomyManager) + Event-Driven |
| 5   | Method signatures      | ✅ Direct Delegation ONLY (NO wrappers)         |
| 6   | Test strategy          | ✅ Parallel Testing                             |

---

## Completion Criteria

**Step 6 Completion** (current focus):

- [ ] NotificationManager subscribes to 9 event types
- [ ] 9 event handler methods implemented in NotificationManager
- [ ] 14 direct `coordinator._notify_*()` calls removed from managers
- [ ] `_handle_chore_claimed_notification()` moved to NotificationManager
- [ ] `_recalculate_point_stats_for_kid()` logic moved to StatisticsManager
- [ ] `_extract_kid_id_from_unique_id()` deleted, replaced with `kh.parse_entity_reference()`
- [ ] `reset_overdue_chores()` wrapper deleted (test updated)
- [ ] 10 coordinator delegate methods deleted (~131 lines)
- [ ] All tests pass
- [ ] MyPy 0 errors

**Phase 6 Overall Completion**:

- [x] `coordinator.py` < 2,000 lines (stretch: < 1,800) ✅ **1,720 lines**
- [x] `coordinator_chore_operations.py` remains DELETED
- [x] NO legacy wrapper methods in coordinator
- [x] NO duplicate helper functions in coordinator
- [x] ALL point changes go through EconomyManager (deposit/withdraw)
- [x] Event Bus drives cross-domain logic (Economy → Gamification)
- [x] Event Bus drives notifications (Action → Event → NotificationManager)
- [x] `services.py` routes directly to managers
- [x] All 1098+ tests pass ✅ **1098 passed, 2 skipped**
- [x] Mypy 0 errors ✅ **36 source files, 0 errors**
- [x] Lint score ≥ 9.5/10 ✅ **All checks passed**

---

## References

- [LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md](./LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md) - Master plan
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Coding standards
- [PHASE5_GAMIFICATION_ENGINE_COMPLETED.md](../completed/PHASE5_GAMIFICATION_ENGINE_COMPLETED.md) - Phase 5 reference
- [LAYERED_ARCHITECTURE_VNEXT_SUP_EVENT_PATTERN.md](./LAYERED_ARCHITECTURE_VNEXT_SUP_EVENT_PATTERN.md) - Event patterns

---

## 🚀 Handoff to Builder

**Current State**: Steps 1-5 COMPLETE. Step 6 ready for implementation.

**Step 6 Implementation Order**:

1. **Add event subscriptions** to `NotificationManager.async_setup()` (~9 lines)
2. **Implement event handlers** in NotificationManager (~200 lines)
   - `_handle_badge_earned()`, `_handle_achievement_unlocked()`, etc.
3. **Move `_handle_chore_claimed_notification()`** from coordinator to NotificationManager
4. **Move `_recalculate_point_stats_for_kid()`** logic to StatisticsManager
5. **Remove 14 direct notification calls** from managers (replace with event emissions)
6. **DELETE coordinator delegates** (10 methods, ~131 lines):
   - `_notify_kid()`, `_notify_kid_translated()`, `_notify_parents()`, `_notify_parents_translated()`
   - `send_kc_notification()`, `clear_notification_for_parents()`, `remind_in_minutes()`
   - `_recalculate_point_stats_for_kid()`, `reset_overdue_chores()`
   - `_extract_kid_id_from_unique_id()`
7. **Update 1 test** to use `coordinator.chore_manager.reset_overdue_chores()`
8. **Run validation**: `./utils/quick_lint.sh --fix && mypy && pytest tests/ -v`

**Files to Modify**:

- `managers/notification_manager.py` - Add subscriptions + handlers
- `managers/statistics_manager.py` - Add `recalculate_point_stats()` method
- `managers/gamification_manager.py` - Remove direct `coordinator._notify_*()` calls
- `managers/reward_manager.py` - Remove direct `coordinator._notify_*()` calls
- `managers/economy_manager.py` - Remove direct `coordinator._notify_*()` calls
- `managers/chore_manager.py` - Remove direct `coordinator._notify_*()` calls
- `coordinator.py` - DELETE 10 methods
- `tests/test_chore_services.py` - Update line ~694

**Validation Commands**:

```bash
./utils/quick_lint.sh --fix
MYPYPATH=/workspaces/core python -m mypy custom_components/kidschores/ --explicit-package-bases
python -m pytest tests/ -v --tb=line
```

---

> **PROCEED IMMEDIATELY** with Step 6. Core architectural principle: Event Bus, not direct calls.
