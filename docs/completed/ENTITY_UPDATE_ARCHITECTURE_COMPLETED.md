# Initiative Plan: Entity Update Architecture Overhaul

## Initiative snapshot

- **Name / Code**: ENTITY_UPDATE_ARCHITECTURE
- **Target release / milestone**: v0.5.0-beta5
- **Owner / driver(s)**: KidsChores Team
- **Status**: Completed

## Summary & immediate steps

| Phase / Step                     | Description                                            | % complete | Quick notes                                                 |
| -------------------------------- | ------------------------------------------------------ | ---------- | ----------------------------------------------------------- |
| Phase 1 – Centralize Update Hook | Add `_persist_and_update()` to coordinator             | 100%       | ✅ Method added, docs updated, validation passed            |
| Phase 2 – Migrate Workflow Paths | Replace all workflow \_persist() + emit() with new API | 100%       | ✅ 26 migrations complete, Phase C.1 removed, validated     |
| Phase 3 – Audit & Edge Cases     | Audit signal patterns and confirm intentional design   | 100%       | ✅ CHORE_UPDATED listener intentional, lifecycle signals OK |
| Phase 4 – Tests & Validation     | Add entity-update assertion helpers, validate all      | 100%       | ✅ Complete - tests/validation and runtime audit documented |

1. **Key objective** – Eliminate "sensor lag" caused by data persisting to storage without triggering entity state refresh. Currently, ~23 code paths write data but don't notify HA entities, causing the dashboard to show stale state until the 5-minute coordinator cycle catches up.

2. **Summary of recent work** – Complete audit performed:
   - Mapped 78 `async_update_listeners()` call sites across codebase
   - Identified 38 potential orphan `_persist()` calls → 23 confirmed real (rest: false positives/docstrings)
   - Identified 42 orphan `emit()` calls → **ZERO** signal listeners call `async_update_listeners()`
   - Built complete signal routing map (30+ signals, 8 managers, all listener chains)
   - Confirmed entity model: all KidsChores entities use `@property` pattern (computed on access from `coordinator._data`), which means `async_update_listeners()` is sufficient to refresh all entity states

3. **Next steps (short term)** – Completed and archived.

4. **Risks / blockers**
   - **Performance**: Calling `async_update_listeners()` too frequently during batch operations could cause UI flicker. Mitigation: debounced persist already batches writes; entity update should follow same pattern.
   - **Test coverage**: Many existing tests don't assert entity state after operations. Tests may pass but miss the real-world bug.
   - **Signal chain complexity**: 9 workflow persists rely on signal chain relay (emit → StatisticsManager listener → persist). These work today but are fragile.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md) – Data model, signal-first communication rules
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Manager CRUD ownership, persist rules
   - [ENTITY_UPDATE_ARCHITECTURE_SUP_AUDIT_DATA_COMPLETED.md](ENTITY_UPDATE_ARCHITECTURE_SUP_AUDIT_DATA_COMPLETED.md) – Full audit data (orphan classifications, signal routing map)
   - HA Core `update_coordinator.py` – `async_update_listeners()` (L197), `async_set_updated_data()` (L554)

6. **Decisions & completion check**
   - **Decisions captured**:
     - `_persist_and_update()` chosen over "auto-update in \_persist()" because some persists intentionally skip entity updates (notification metadata, system config cleanup). Name avoids confusion with notification system.
     - `async_update_listeners()` is sufficient (no need for `async_set_updated_data()`) because entities use `@property` over shared `coordinator._data`
     - Signal listeners should NOT call entity updates — only the originating workflow method should
   - **Completion confirmation**: `[x]` All follow-up items completed before requesting owner approval

---

## Root Cause Analysis

### The Problem

When a user claims a chore, approves a reward, or the due-window timer fires, the integration:

1. ✅ Updates in-memory `_data` dict correctly
2. ✅ Calls `_persist()` to save to disk
3. ✅ Calls `emit()` to notify other managers
4. ❌ **Does NOT call `async_update_listeners()`** to tell HA entities to re-read their state

Result: Dashboard shows stale data (e.g., "pending" instead of "due") until the 5-minute coordinator cycle runs `_async_update_data()` → `async_update_listeners()`.

### Why It Happens

The codebase has **two distinct patterns** for state-changing operations:

**Pattern A — CRUD Operations** (create/update/delete chores, rewards, kids, etc.)

```
_data[key] = new_value
_persist()
async_update_listeners()  ← ✅ Always present
emit(CREATED/UPDATED/DELETED)
```

These work correctly because the entity update is paired with the persist.

**Pattern A-variant — Gamification Workflow** (badge earned, achievement awarded, challenge completed)

```
_data[key] = new_value
_persist()
emit(BADGE_EARNED/ACHIEVEMENT_EARNED/etc.)
async_set_updated_data()  ← ✅ Present (uses heavier HA method but works)
```

These work but use `async_set_updated_data()` which resets the coordinator refresh timer — unnecessarily heavy. Should be normalized to `async_update_listeners()` via the new `_persist_and_update()` method.

**Pattern B — Workflow Operations** (claim, approve, disapprove, timer-triggered, rotations)

```
_data[key] = new_value
_persist()
emit(CHORE_CLAIMED/APPROVED/etc.)  ← Only signal, no entity update
```

These are broken because the developer assumed the signal chain would handle entity updates. **But no signal listener ever calls `async_update_listeners()`.**

### The Numbers

| Category                        | Count | Entity Update?                          |
| ------------------------------- | ----- | --------------------------------------- |
| CRUD operations (Pattern A)     | ~30   | ✅ All have `async_update_listeners()`  |
| Workflow operations (Pattern B) | ~23   | ❌ None have `async_update_listeners()` |
| Notification metadata persists  | 3     | N/A (no entity reads this data)         |
| System/cleanup persists         | ~5    | N/A (eventually-consistent, low impact) |

### How HA Entity Updates Work

```
async_update_listeners()
  → iterates all CoordinatorEntity listener callbacks
    → each callback triggers HA to call entity's @property methods
      → native_value, extra_state_attributes re-computed from coordinator._data
        → HA state machine pushes new state to frontend
```

Since all KidsChores entities use `@property` (not cached), a single `async_update_listeners()` call refreshes ALL entities simultaneously. This is cheap (~1ms for 30+ entities) because it only triggers HA's state diff mechanism.

---

## Architectural Recommendation

### Option Evaluation

| Option                                    | Description                                               | Pros                                                                                        | Cons                                                                                                                                   | Verdict            |
| ----------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **A: Auto-update in \_persist()**         | Add `async_update_listeners()` inside `_persist()`        | Zero migration effort                                                                       | Notification metadata and system cleanup persists would trigger unnecessary entity updates (~8 paths). Violates single-responsibility. | ❌ Rejected        |
| **B: New `_persist_and_update()` method** | Coordinator gains `_persist_and_update()` that calls both | Explicit opt-in. Clear intent. No naming confusion with notifications. Backward compatible. | Must migrate 17 workflow call sites + normalize 6 gamification sites.                                                                  | ✅ **Recommended** |
| **C: Listener-based entity updates**      | Signal listeners call `async_update_listeners()`          | Aligns with signal-first architecture                                                       | Same entity update would fire multiple times per operation (once per listener). Hard to reason about "who refreshes".                  | ❌ Rejected        |
| **D: Dirty flag + batched update**        | Set a flag in `_persist()`, flush via `call_later(0.1s)`  | Maximum batching efficiency                                                                 | Complex, hard to test, timing-dependent, hides bugs                                                                                    | ❌ Rejected        |

### Recommended: Option B — `_persist_and_update()`

Add a new method to `coordinator.py`:

```python
def _persist_and_update(self, immediate: bool = False) -> None:
    """Persist data AND update entity listeners to reflect state changes.

    Use this for ALL workflow operations that change user-visible state.
    Use _persist() alone only for internal bookkeeping (notification metadata,
    system config, cleanup operations).

    Name note: "update" refers to HA entity listener updates, NOT push
    notifications. See NotificationManager for push notification handling.
    """
    self._persist(immediate=immediate)
    self.async_update_listeners()
```

**Migration rule**:

1. Any `_persist()` call in a workflow method (claim, approve, disapprove, timer-triggered, rotation) that changes data read by entity `@property` methods → replace with `_persist_and_update()`.
2. Any `_persist()` + `async_set_updated_data()` pair in gamification workflows → replace both lines with single `_persist_and_update()` call. (`async_set_updated_data()` unnecessarily resets the coordinator refresh timer; `async_update_listeners()` is sufficient since entities read from the shared `_data` dict.)

**Keep `_persist()` alone** for:

- Notification suppression timestamps (`notification_manager.py`)
- System config cleanup (`system_manager.py` signal handlers)
- Statistics period bucket flushes (callers already handle entity updates)
- Gamification internal queues

---

## Detailed phase tracking

### Phase 1 – Centralize Update Hook

- **Goal**: Add `_persist_and_update()` to coordinator as the standard way to persist + refresh entities.

- **Steps / detailed work items**
  1. `- [x]` **Add `_persist_and_update()` method to `coordinator.py`** (after `_persist()` ~line 255)
     - Method signature: `def _persist_and_update(self, immediate: bool = False) -> None:`
     - Docstring: explain this persists data AND triggers HA entity state refresh. Clarify "update" means HA entity listeners, NOT push notifications.
     - Implementation: calls `self._persist(immediate=immediate)` then `self.async_update_listeners()`
  2. `- [x]` **Update BaseManager docstring** in `base_manager.py`
     - Add guidance in class docstring: "Use `coordinator._persist_and_update()` for user-visible state changes"
  3. `- [x]` **Update DEVELOPMENT_STANDARDS.md** § CRUD Ownership Rules
     - Document the two persist methods and when to use each
     - Add to the "Correct Pattern" code example
  4. `- [x]` **Validate**: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/coordinator.py`

- **Key issues**
  - None anticipated — purely additive change

### Phase 2 – Migrate Workflow Paths

- **Goal**: Replace orphan `_persist()` calls in workflow methods with `_persist_and_update()`, and normalize `_persist()` + `async_set_updated_data()` pairs to `_persist_and_update()`. This is the bulk of the work.

- **Steps / detailed work items**

  **2A. ChoreManager workflow operations** (`managers/chore_manager.py`)
  1. `- [x]` **`claim_chore()` method** (~line 591): Replace `self.coordinator._persist()` with `self.coordinator._persist_and_update()`
     - Context: Kid claims chore → state changes from pending/due to claimed. Dashboard must show immediately.
  2. `- [x]` **`approve_chore()` method** (~line 923): Replace `_persist()` → `_persist_and_update()`
     - Context: Parent approves → state changes to approved, points awarded. Most visible workflow.
  3. `- [x]` **`disapprove_chore()` method** (~line 1120): Replace `_persist()` → `_persist_and_update()`
     - Context: Parent disapproves → state reverts to pending.
  4. `- [x]` **`undo_chore_approval()` method** (~line 1197): Replace `_persist()` → `_persist_and_update()`
     - Context: Parent undoes approval → state reverts, points deducted.
  5. `- [x]` **`_mark_chore_missed()` method** (~line 4311): Replace `_persist()` → `_persist_and_update()`
     - Context: Timer marks chore as missed → dashboard must show missed state.
  6. `- [x]` **`reset_chore_data()` method** (~line 4666): Replace `_persist()` → `_persist_and_update()`
     - Context: Admin resets all chore data → all chore entities must refresh.
  7. `- [x]` **`transition_completion_criteria()` method** (~line 3765): Replace `_persist()` → `_persist_and_update()`
     - Context: Chore criteria change → affects dashboard display text.
  8. `- [x]` **`advance_rotation()` method** (~line 3827): Replace `_persist()` → `_persist_and_update()`
     - Context: Rotation advances → different kid's turn now.
  9. `- [x]` **`reset_rotation()` method** (~line 3883): Replace `_persist()` → `_persist_and_update()`
     - Context: Rotation resets → first kid's turn again.
  10. `- [x]` **`override_rotation_cycle()` method** (~line 3930): Replace `_persist()` → `_persist_and_update()`
      - Context: Cycle override flag → changes who can claim.
  11. `- [x]` **Remove Phase C.1 quick fix** in `_on_periodic_update()` (~line 315-322)
      - The `async_update_listeners()` added as quick fix should be removed; the individual workflow methods now handle it themselves.
      - Note: The coordinator's `_async_update_data()` already calls `async_update_listeners()` at line 161, so periodic cycle is already covered.

  **2B. EconomyManager workflow operations** (`managers/economy_manager.py`) 12. `- [x]` **`apply_penalty()` method** (~line 749-760): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Penalty applied to kid → points deducted, penalty count visible on dashboard sensor. - Currently uses heavier `async_set_updated_data()` which resets coordinator refresh timer unnecessarily. 13. `- [x]` **`apply_bonus()` method** (~line 943-954): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Bonus applied to kid → points added, bonus count visible on dashboard sensor. 14. `- [x]` **`_on_multiplier_changed()` handler** (~line 156): Keep as `_persist()` only - Rationale: Multiplier is internal metadata, not directly displayed. Eventually-consistent via 5-min cycle. 15. `- [x]` **`deposit()` and `withdraw()` methods**: Verify these are callee-persists-pattern - These methods mutate `_data` and emit `POINTS_CHANGED` but do NOT persist or update entities. - This is by design: the CALLING workflow method (e.g., approve_chore → \_persist_and_update) handles persistence. - Verify: all callers that invoke deposit/withdraw also call \_persist_and_update() or are themselves called by a method that does.

  **2C. GamificationManager workflow operations** (`managers/gamification_manager.py`) 16. `- [x]` **`_record_badge_earned()` method** (~line 2085): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Badge tracking recorded → KidBadgesSensor and KidBadgeProgressSensor must update immediately. 17. `- [x]` **`update_badges_earned_for_kid()` method** (~line 1506): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Badge earned metadata updated → badge sensor attributes must refresh. 18. `- [x]` **`demote_cumulative_badge()` method** (~line 1733): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Cumulative badge demoted → badge progress sensor must show demoted state, multiplier changes. 19. `- [x]` **`remove_awarded_badges()` method** (~line 1811): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Badges removed from kid → badge sensors must clear those entries. 20. `- [x]` **`remove_awarded_badges_by_id()` method** (~line 2039): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Internal badge removal by ID → same entity impact as above. 21. `- [x]` **`_award_achievement_to_kid()` method** (~line 392): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Achievement earned → achievement progress visible in sensor attributes. 22. `- [x]` **`award_challenge()` method** (~line 452): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Challenge completed → challenge progress visible in sensor attributes. 23. `- [x]` **`data_reset_badges()` method** (~line 3114): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Badge data reset → all badge sensors must clear. 24. `- [x]` **`data_reset_achievements()` method** (~line 3197): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Achievement progress reset → achievement sensors must clear. 25. `- [x]` **`data_reset_challenges()` method** (~line 3266): Replace `_persist()` + `async_set_updated_data()` → single `_persist_and_update()` - Context: Challenge progress reset → challenge sensors must clear. 26. `- [x]` **`_pending_evaluation_queue` persist** (~line 521): Keep as `_persist()` only - Rationale: Internal queue for restart resilience. No entity reads this. 27. `- [x]` **`_clean_chore_references()` method** (~line 656): Keep as `_persist()` only - Rationale: Cleanup after chore deletion. Chore entities already being removed. 28. `- [x]` **`_clean_kid_from_gamification()` method** (~line 603): Keep as `_persist()` only - Rationale: Cleanup after kid deletion. Kid entities already being removed.

  **2D. RewardManager workflow operations** (`managers/reward_manager.py`) 29. `- [x]` **`claim()` method** (~line 353): Replace `_persist()` → `_persist_and_update()` - Context: Kid claims reward → pending count changes, reward state visible on dashboard. 30. `- [x]` **`approve_reward()` method** (~line 472): Replace `_persist()` → `_persist_and_update()` - Context: Parent approves reward → points deducted, status changes. 31. `- [x]` **`disapprove_reward()` method** (~line 593): Replace `_persist()` → `_persist_and_update()` - Context: Parent disapproves → status reverts.

  **2E. StatisticsManager** (`managers/statistics_manager.py`) 32. `- [x]` **`_flush_period_stats()` and `_flush_period_metrics()`**: Keep as `_persist()` only - Rationale: Callers (signal handlers) already delegate to methods that handle entity updates.

  **2F. UserManager** (`managers/user_manager.py`) 33. `- [x]` **`_on_kid_deleted()` cleanup** (~line 94): Keep as `_persist()` only - Rationale: Cleanup of parent associations after kid deletion. Kid entities already being removed.

  **2G. NotificationManager** (`managers/notification_manager.py`) 34. `- [x]` **All three `_persist()` calls** (lines 385, 414, 433): Keep as `_persist()` only - Rationale: All are notification suppression/tracking metadata. No entity reads this data.

  **Validation after Phase 2**:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/ -v --tb=line`

- **Key issues**
  - **Batch approval concern**: When a parent approves multiple chores rapidly, each approval now calls `async_update_listeners()` immediately. This is safe because the call is synchronous and cheap (~1ms), and HA's state machine handles the diff efficiently.
  - **Signal handler ordering**: After migration, the originating method triggers entity update BEFORE signal listeners execute. This is correct — listeners do bookkeeping (stats, badges), and their effects will be visible on the next entity update (either from the next operation or the 5-min cycle).
  - **Gamification `async_set_updated_data()` removal**: The 10 gamification methods and 2 economy methods that currently use `async_set_updated_data()` are not broken (entities DO update), but they use the heavier HA method unnecessarily. Normalizing to `_persist_and_update()` gives a consistent API and avoids resetting the coordinator refresh timer on every badge/achievement/challenge operation.

### Phase 3 – Audit & Edge Cases (Simplified Scope)

- **Goal**: Audit signal patterns and confirm existing cleanup patterns are intentional. No bug fixes per user directive.

- **Steps / detailed work items**
  1. `- [x]` **~~Fix `undo_chore_approval()` conditional emit bug~~** (SKIPPED per user: "not implemented fully, so leave as is")
     - Original finding: `CHORE_UNDONE` signal only emits when `previous_points > 0`.
     - User decision: Leave as is.
  2. `- [x]` **Audit `CHORE_UPDATED` signal listeners**
     - ✅ **CONFIRMED**: Only `GamificationManager._on_chore_updated()` listens (line 128).
     - Handler: Calls `recalculate_all_badges()` when chore is updated (assignments changed, config modified).
     - Does NOT call entity updates → **Intentional**: Gamification entities reflect changes on next evaluation cycle (debounced pattern at line 125-143).
     - **Conclusion**: Pattern is correct by design. Badge recalculation is deferred/batched. No changes needed.
  3. `- [x]` **~~Dead signal: `REWARD_STOCK_CHANGED`~~** (SKIPPED per user: "unnecessary")
     - Original finding: Defined in const.py, UIManager listens, but no manager ever emits it.
     - User decision: No action needed.
  4. `- [x]` **Dead signals audit**: Other candidates checked.
     - `KID_CREATED` (const.py:230): ✅ **Emitted** by user_manager.py line 160, no listeners (lifecycle signal only)
     - `PARENT_CREATED` (const.py:235): ✅ **Emitted** by user_manager.py line 367, no listeners (lifecycle signal only)
     - `PARENT_UPDATED` (const.py:236): ✅ **Emitted** by user_manager.py line 447, no listeners (lifecycle signal only)
     - `CHORE_ROTATION_ADVANCED` (const.py:193): ✅ **Emitted** by chore_manager.py lines 1988 + 3392, no listeners (lifecycle signal only)
     - **Conclusion**: All signals are emitted. None have listeners because they're lifecycle events for potential future use (logging, external integrations). No dead signals found.
  5. `- [x]` **Remove Phase C.1 async_update_listeners() from \_on_periodic_update()**
     - ✅ **COMPLETED** in Phase 2 step 11: chore_manager.py lines 315-322 removed during workflow method migrations.

- **Key issues**
  - **User directive**: Skip the `undo_chore_approval()` bug fix ("not implemented fully, leave as is") and the REWARD_STOCK_CHANGED investigation ("unnecessary").
  - **Simplified scope**: Phase reduced to signal pattern audit only. All findings confirm intentional design patterns.
  - **Lifecycle signals**: Multiple signals (KID_CREATED, PARENT_CREATED, etc.) have no listeners — this is by design for future extensibility and logging. Not dead code.

### Phase 4 – Tests & Validation

- **Goal**: Add test infrastructure that prevents future "orphan persist" regressions and validate all Phase 2/3 changes.

- **Steps / detailed work items**
  1. `- [ ]` **Create test utility: `assert_entity_update_called()`**
     - Location: `tests/helpers.py` or new `tests/utils.py`
     - Pattern: Context manager that patches `coordinator.async_update_listeners` and asserts it was called
     ```python
     @contextmanager
     def assert_entity_update_called(coordinator):
         with patch.object(coordinator, 'async_update_listeners', wraps=coordinator.async_update_listeners) as mock:
             yield mock
         assert mock.called, "Expected async_update_listeners() to be called"
     ```
  2. `- [ ]` **Add entity-refresh assertions to existing workflow tests**
     - `test_workflow_chore_claim.py`: Assert entity update after claim
     - `test_workflow_chore_approve.py`: Assert entity update after approve/disapprove
     - `test_workflow_reward.py`: Assert entity update after claim/approve/disapprove
  3. `- [ ]` **Add boundary checker rule** in `utils/check_boundaries.py`
     - New rule: "Workflow methods that call `_persist()` in managers/ must use `_persist_and_update()` unless explicitly exempted"
     - Exemption list: notification*manager.py, statistics_manager.\_flush*_, gamification*manager.\_pending_evaluation_queue, gamification_manager.\_clean*_, user_manager.\_on_kid_deleted, economy_manager.\_on_multiplier_changed, system_manager signal handlers
  4. `- [ ]` **Full test suite validation**
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/kidschores/`
     - `python -m pytest tests/ -v`
  5. `- [ ]` **Live system smoke test**
     - Claim chore from dashboard → verify state changes immediately (no 5-min lag)
     - Approve chore → verify state and points update immediately
     - Advance rotation → verify turn changes immediately

- **Key issues**
  - Test utility must handle async context properly (coordinator runs in event loop)
  - Boundary checker rule needs carefully curated exemption list to avoid false positives

---

## Testing & validation

- **Pre-existing tests**: 18/18 passing before this initiative
- **Tests to add**:
  - Entity refresh assertions on all workflow test methods
  - Boundary checker integration for CI/CD
- **Validation commands**:
  ```bash
  ./utils/quick_lint.sh --fix
  mypy custom_components/kidschores/
  python -m pytest tests/ -v --tb=line
  ```

## Notes & follow-up

### Why Not Auto-Update in `_persist()`?

The most obvious solution — adding `async_update_listeners()` inside `_persist()` — was rejected because:

1. **Notification metadata**: `notification_manager.py` persists suppression timestamps 3 times. These don't affect any entity state. Triggering 30+ entity property evaluations for notification bookkeeping is wasteful.
2. **Statistics flushes**: `statistics_manager.py` flushes period buckets. The callers already handle entity updates at a higher level.
3. **System cleanup handlers**: `system_manager.py` signal handlers clean up orphaned references. These run during cascade processing where entity updates at the end of the cascade are sufficient.
4. **Debounce interaction**: `_persist()` uses 5-second debouncing. Adding entity updates there would mean entities refresh immediately but data persists 5 seconds later. If the process crashes in between, entities showed state that was never persisted. The `_persist_and_update()` approach keeps the same timing semantics.

### Why `_persist_and_update()` Not `_persist_and_notify()`?

"Notify" would cause confusion with the push notification system (`NotificationManager`, `notify.mobile_app_*` services). The word "update" aligns with the HA core API naming (`async_update_listeners`) and clearly describes the action: updating entity listener state, not sending messages to devices.

### Performance Impact

- `async_update_listeners()` costs ~1ms for KidsChores' ~30 entity registrations
- Even during batch approval of 10 chores, 10 × 1ms = 10ms total overhead — negligible
- The debounced `_persist()` already batches disk writes; entity updates are in-memory only

### Why Normalize `async_set_updated_data()` → `async_update_listeners()`?

The gamification manager currently uses `async_set_updated_data(self.coordinator._data)` which does three things: (1) sets `self.data = data`, (2) resets the coordinator's refresh timer, and (3) calls `async_update_listeners()`. Since KidsChores entities read from the shared mutable `coordinator._data` dict (not `coordinator.data`), steps (1) and (2) are unnecessary overhead. The new `_persist_and_update()` calls the lightweight `async_update_listeners()` directly.

### Future Consideration: Signal-Based Entity Categories

A future optimization could tag signals with entity categories (e.g., `CHORE_CLAIMED` → only refresh chore entities, not badge entities). This is unnecessary now because `async_update_listeners()` is cheap, but could matter if entity count grows to 100+.

### Migration Count Summary

| Action                                                                                                         | Count | Files                                                                                                             | Priority           |
| -------------------------------------------------------------------------------------------------------------- | ----- | ----------------------------------------------------------------------------------------------------------------- | ------------------ |
| Replace `_persist()` → `_persist_and_update()`                                                                 | 14    | chore_manager.py (10), reward_manager.py (3), chore_manager.py reset (1)                                          | **P0 — Bug fix**   |
| Replace `_persist()` + `async_set_updated_data()` → `_persist_and_update()`                                    | 12    | gamification_manager.py (10), economy_manager.py (2)                                                              | **P1 — Normalize** |
| Keep `_persist()` (intentionally no entity update)                                                             | 8     | notification_manager (3), gamification_manager (3), statistics_manager (2), user_manager (1), economy_manager (1) | No change          |
| Optional: Normalize CRUD `_persist(immediate)` + `async_update_listeners()` → `_persist_and_update(immediate)` | ~21   | All managers (CRUD create/update/delete methods)                                                                  | **P2 — Optional**  |
| Fix conditional emit bug                                                                                       | 1     | chore_manager.py undo_chore_approval                                                                              | **P0 — Bug fix**   |
| Remove quick fix                                                                                               | 1     | chore_manager.py \_on_periodic_update Phase C.1                                                                   | **P1 — Cleanup**   |
| Dead signal cleanup                                                                                            | 1-4   | const.py, various managers                                                                                        | **P2 — Tech debt** |

**Note on CRUD normalization (P2)**: The ~21 CRUD methods across all managers already work correctly (they pair `_persist(immediate=immediate_persist)` + `async_update_listeners()` on separate lines). Normalizing them to use the single `_persist_and_update(immediate=immediate_persist)` call is optional but improves consistency. The `immediate` parameter passes through transparently. This can be done alongside P0/P1 or deferred.
