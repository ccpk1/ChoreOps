# Initiative Plan: Scheduler Delegation to ChoreManager

## Initiative snapshot

- **Name / Code**: Scheduler Delegation (Phase 4.5b)
- **Target release / milestone**: v0.5.1 (Pre-Phase 5 dependency)
- **Owner / driver(s)**: Plan Agent (implementation), Strategic Agent (planning)
- **Status**: ✅ Complete

## Summary & immediate steps

| Phase / Step           | Description                                   | % complete | Quick notes                               |
| ---------------------- | --------------------------------------------- | ---------- | ----------------------------------------- |
| Phase 1 – Methods      | Add Manager methods for overdue/recurring     | 100%       | ✅ 2 public + 2 helper methods added      |
| Phase 2 – Integration  | Wire Coordinator timers to call Manager       | 100%       | ✅ Thin delegation + legacy preserved     |
| Phase 2.5 – Alignment  | Service delegation + query methods to Engine  | 100%       | ✅ 5 service + 4 query methods + bug fix  |
| Phase 3 – Tests        | Verify events emitted from timer paths        | 100%       | ✅ 10 tests in test_scheduler_delegation.py |
| Phase 4 – Cleanup      | Add deprecation notices to legacy methods     | 100%       | ✅ Comprehensive docstrings added         |

1. **Key objective** – Complete the Manager delegation pattern so that time-based chore state changes (`CHORE_OVERDUE`, `CHORE_STATUS_RESET`) emit proper events for Phase 5 Gamification Manager consumption.

2. **Summary of recent work**
   - Phase 4 implemented ChoreManager claim/approve/disapprove workflows with event emission
   - Legacy timer callbacks (`_process_recurring_chore_resets`, `_check_overdue_chores`) remain in `coordinator_chore_operations.py`
   - These legacy methods do NOT emit `SIGNAL_SUFFIX_CHORE_*` events
   - This blocks Phase 5's event-driven gamification architecture

3. **Next steps (short term)**
   - Add `update_overdue_status(now)` to ChoreManager
   - Add `update_recurring_chores(now)` to ChoreManager
   - Modify Coordinator timer registration to delegate to Manager methods

4. **Risks / blockers**
   - Risk: Regression in overdue detection if delegation breaks timing
   - Mitigation: Keep legacy logic callable as fallback during transition
   - Risk: Test coverage gaps for timer paths
   - Mitigation: Add dedicated tests verifying event emission

5. **References**
   - [ARCHITECTURE.md § Event System](../ARCHITECTURE.md) - Signal patterns
   - [Phase 4 Implementation Guide](LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE4_IMPL.md) - Manager patterns
   - [const.py lines 71-76](../../custom_components/kidschores/const.py#L71-L76) - Signal constants

6. **Decisions & completion check**
   - **Decisions captured**:
     - Use thin delegation (Coordinator calls Manager, Manager executes logic)
     - Manager methods use existing `reset_chore()` and `mark_overdue()` internally
     - Preserve SHARED vs INDEPENDENT handling already in legacy code
   - **Completion confirmation**: `[x]` All follow-up items completed before marking done.
     - ✅ Bug fix: `_reset_approval_period` corrected to set right field
     - ✅ Tests: 10 new tests in `test_scheduler_delegation.py`
     - ✅ Deprecation: Legacy methods documented with migration path
     - ✅ Validation: All 1055 tests pass, lint 9.8+/10, mypy clean

---

## Detailed phase tracking

### Phase 1 – Manager Methods

- **Goal**: Add two public methods to ChoreManager that execute overdue/recurring logic and emit events.

- **Steps / detailed work items**

  1. `[x]` **Add `update_overdue_status(now: datetime)` method**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Location: After `mark_overdue()` method (~line 435)
     - Logic:
       - Iterate all chores
       - Skip if all assigned kids have claimed/approved
       - For each kid × chore: check if past due date
       - Call `self.mark_overdue(kid_id, chore_id, days_overdue, due_date_iso)` which already emits `SIGNAL_SUFFIX_CHORE_OVERDUE`
     - Return: `list[tuple[str, str]]` of (chore_id, kid_id) marked overdue
     - ✅ **DONE**: Added ~130 lines, handles SHARED/INDEPENDENT/SHARED_FIRST criteria

  2. `[x]` **Add `update_recurring_chores(now: datetime)` method**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Location: After `update_overdue_status()` method
     - Logic:
       - Call `_reschedule_recurring_chores(now)` for rescheduling (delegate to legacy for now)
       - Handle daily/weekly/monthly reset counts
       - For each reset: call `self.reset_chore()` which emits `SIGNAL_SUFFIX_CHORE_STATUS_RESET`
     - Return: `int` count of chores reset
     - ✅ **DONE**: Added ~80 lines + 2 helper methods (`_reset_shared_chore`, `_reset_independent_chore`)

  3. `[x]` **Add type imports if needed**
     - Ensure `datetime` is imported
     - Ensure `ChoreData` is in TYPE_CHECKING block
     - ✅ **DONE**: Added `datetime` to TYPE_CHECKING block

- **Key issues**
  - Must handle SHARED vs INDEPENDENT completion criteria (already handled in `_reschedule_recurring_chores`)
  - Must preserve NEVER_OVERDUE handling from legacy code

### Phase 2 – Coordinator Integration

- **Goal**: Wire Coordinator timer callbacks to delegate to ChoreManager methods.

- **Steps / detailed work items**

  1. `[x]` **Modify `_check_overdue_chores` to delegate to Manager**
     - File: `custom_components/kidschores/coordinator_chore_operations.py` (line ~3093)
     - Change:
       ```python
       async def _check_overdue_chores(self, now: datetime | None = None):
           """Check and mark overdue chores - delegates to ChoreManager."""
           now_utc = now or dt_util.utcnow()
           # Delegate to Manager which emits proper events
           await self.chore_manager.update_overdue_status(now_utc)
       ```
     - Preserve legacy logic in renamed method `_check_overdue_chores_legacy()` for reference
     - ✅ **DONE**: Delegated + legacy preserved with deprecation notice

  2. `[x]` **Modify `_process_recurring_chore_resets` to delegate to Manager**
     - File: `custom_components/kidschores/coordinator_chore_operations.py` (line ~2425)
     - Change:
       ```python
       async def _process_recurring_chore_resets(self, now: datetime):
           """Handle recurring resets - delegates to ChoreManager."""
           # Delegate to Manager which emits proper events
           await self.chore_manager.update_recurring_chores(now)
       ```
     - Preserve legacy logic in renamed method `_process_recurring_chore_resets_legacy()` for reference
     - ✅ **DONE**: Delegated + legacy preserved with deprecation notice

  3. `[x]` **Ensure `chore_manager` property exists on Coordinator**
     - Verify: `coordinator.chore_manager` returns ChoreManager instance
     - File: `custom_components/kidschores/coordinator.py`
     - Already implemented in Phase 4
     - ✅ **VERIFIED**: Line 142 `self.chore_manager = ChoreManager(hass, self, self.economy_manager)`

- **Key issues**
  - Timer callbacks are `async` - ensure Manager methods are `async` compatible
  - Must not break existing tests that call `coordinator._check_overdue_chores()` directly

### Phase 2.5 – Service Alignment & Query Methods

- **Goal**: Complete the Manager/Engine split by:
  1. Porting 5 "read-only" query methods to ChoreEngine as static methods
  2. Adding 5 service methods to ChoreManager
  3. Wiring 5 Coordinator service methods to delegate to ChoreManager

- **Why This Matters**:
  - Query methods are pure logic = belong in ChoreEngine (stateless)
  - Service methods modify state = belong in ChoreManager (can emit events)
  - "Split brain" problem: sensors calling Coordinator, Manager calling Coordinator = circular dependencies

- **Steps / detailed work items**

  **Part A: Port Query Methods to ChoreEngine**

  1. `[x]` **Add `chore_is_due()` static method to ChoreEngine**
     - Current location: `coordinator_chore_operations.py` line 752
     - Logic: Check if `due_window_start <= now < due_date`
     - Signature: `chore_is_due(chore_data: ChoreData, kid_due_date: str | None, due_window_offset_str: str | None, now: datetime) -> bool`
     - Note: Caller (Coordinator) will look up chore_data and pass relevant fields
     - ✅ **DONE**: Added lines 563-589, handles due window start calculation

  2. `[x]` **Add `get_due_date_for_kid()` static method to ChoreEngine**
     - Current location: `coordinator_chore_operations.py` line 820
     - Logic: Return SHARED chore-level or INDEPENDENT per-kid due date
     - Signature: `get_due_date_for_kid(chore_data: ChoreData, kid_id: str | None) -> str | None`
     - ✅ **DONE**: Added lines 591-620, handles SHARED/INDEPENDENT criteria

  3. `[x]` **Add `get_due_window_start()` static method to ChoreEngine**
     - Current location: `coordinator_chore_operations.py` line 856
     - Logic: Return `due_date - due_window_offset` or None
     - Signature: `get_due_window_start(due_date: datetime, due_window_offset: timedelta) -> datetime | None`
     - ✅ **DONE**: Added lines 622-645, integrated with chore_is_due

  4. `[x]` **Add `is_approved_in_period()` static method to ChoreEngine**
     - Current location: `coordinator_chore_operations.py` line 901
     - Logic: Check if `last_approved >= approval_period_start`
     - Signature: `is_approved_in_period(kid_chore_data: dict[str, Any], period_start: str | None) -> bool`
     - ✅ **DONE**: Added lines 647-680, moved from coordinator logic

  5. `[x]` **Note: `chore_allows_multiple_claims` already exists**
     - ChoreEngine line ~510 has this as static method
     - Coordinator method `_chore_allows_multiple_claims` (line 1981) is duplicate - can delegate
     - ✅ **VERIFIED**: Already implemented

  **Part B: Add Service Methods to ChoreManager**

  6. `[x]` **Add `set_due_date()` method to ChoreManager**
     - Port from `coordinator_chore_operations.py` line 225
     - Logic: Set due date, reset states, emit event
     - Emit: `SIGNAL_SUFFIX_CHORE_STATUS_RESET` (date change = new period)
     - ✅ **DONE**: Added lines 782-890, handles SHARED/INDEPENDENT due dates

  7. `[x]` **Add `skip_due_date()` method to ChoreManager**
     - Port from `coordinator_chore_operations.py` line 371
     - Logic: Reschedule recurring chore, reset states, emit event
     - Emit: `SIGNAL_SUFFIX_CHORE_STATUS_RESET`
     - ✅ **DONE**: Added lines 892-974, delegates to coordinator._reschedule_chore_due_date

  8. `[x]` **Add `reset_all_chores()` method to ChoreManager**
     - Port from `coordinator_chore_operations.py` line 529
     - Logic: Reset all chores to pending, emit events
     - Emit: `SIGNAL_SUFFIX_CHORE_STATUS_RESET` for each chore
     - ✅ **DONE**: Added lines 976-1005, iterates all kids × chores

  9. `[x]` **Add `reset_overdue_chores()` method to ChoreManager**
     - Port from `coordinator_chore_operations.py` line 579
     - Logic: Reset overdue chores, reschedule, emit events
     - Emit: `SIGNAL_SUFFIX_CHORE_STATUS_RESET` for each reset
     - ✅ **DONE**: Added lines 1007-1079, uses engine chore_is_overdue check

  10. `[x]` **Add `undo_claim()` method to ChoreManager**
      - Port from `coordinator_chore_operations.py` line 982
      - Logic: Kid undo their claim (no stats, no notification)
      - Emit: No event needed (silent undo)
      - Note: Verify points are NOT refunded (undo != disapprove)
      - ✅ **DONE**: Added lines 1081-1134, uses _get_chore_data_for_kid helper

  **Part C: Wire Coordinator Services to Delegate**

  11. `[x]` **Update `set_chore_due_date` to delegate to ChoreManager**
      - Keep method in Coordinator for API compatibility
      - Change body to: `self.chore_manager.set_due_date(chore_id, due_date, kid_id)`
      - ✅ **DONE**: Line 260, thin delegation wrapper

  12. `[x]` **Update `skip_chore_due_date` to delegate to ChoreManager**
      - Keep method signature
      - Change body to: `self.chore_manager.skip_due_date(chore_id, kid_id)`
      - ✅ **DONE**: Line 406, thin delegation wrapper

  13. `[x]` **Update `reset_all_chores` to delegate to ChoreManager**
      - Keep method signature
      - Change body to: `self.chore_manager.reset_all_chores()`
      - ✅ **DONE**: Line 564, thin delegation wrapper

  14. `[x]` **Update `reset_overdue_chores` to delegate to ChoreManager**
      - Keep method signature
      - Change body to: `self.chore_manager.reset_overdue_chores(chore_id, kid_id)`
      - ✅ **DONE**: Line 614, thin delegation wrapper with optional filtering

  15. `[x]` **Update `undo_chore_claim` to delegate to ChoreManager**
      - Keep method signature
      - Change body to: `self.chore_manager.undo_claim(kid_id, chore_id)`
      - ✅ **DONE**: Line 1017, thin delegation wrapper

  **Bug Fix During Validation**

  16. `[x]` **Fix `_reset_approval_period` method in ChoreManager**
      - Found during test failure investigation: method was setting WRONG field
      - OLD (incorrect): Set `DATA_KID_CHORE_DATA_LAST_APPROVED` = now
      - NEW (correct): Set `DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START` = now for INDEPENDENT
                        or `DATA_CHORE_APPROVAL_PERIOD_START` = now for SHARED
      - This fix ensures `chore_is_approved_in_period()` returns False after reset
      - ✅ **DONE**: Lines 2051-2086, matches coordinator logic

- **Key issues**
  - ✅ RESOLVED: Query methods remain callable via coordinator for sensor compatibility
  - ✅ RESOLVED: Coordinator methods are thin wrappers delegating to Engine (queries) or Manager (mutations)
  - ✅ RESOLVED: Bug in `_reset_approval_period` was causing test failure

### Phase 3 – Tests

- **Goal**: Verify time-based events are emitted correctly through the new delegation path.

- **Steps / detailed work items**

  1. `[x]` **Create `tests/test_scheduler_delegation.py`**
     - Test class: `TestOverdueEventEmission`
     - Tests:
       - `test_overdue_check_emits_chore_overdue_event` - Verify `SIGNAL_SUFFIX_CHORE_OVERDUE` fired
       - `test_overdue_check_respects_never_overdue` - NEVER_OVERDUE chores skip emission
       - `test_overdue_check_handles_independent_criteria` - Per-kid due dates work
     - ✅ **DONE**: 3 tests implemented and passing

  2. `[x]` **Add test class `TestRecurringResetEventEmission`**
     - Tests:
       - `test_recurring_reset_emits_status_reset_event` - Verify `SIGNAL_SUFFIX_CHORE_STATUS_RESET` fired
       - `test_reset_chore_via_manager_emits_event` - Direct reset verification
     - ✅ **DONE**: 2 tests implemented and passing

  3. `[x]` **Add test classes for delegation verification**
     - Test class: `TestDelegationPath`
       - `test_coordinator_check_overdue_delegates_to_manager` - Verify delegation path
       - `test_coordinator_process_recurring_delegates_to_manager` - Verify delegation path
     - Test class: `TestServiceDelegation`
       - `test_set_chore_due_date_delegates_to_manager` - Service delegation
       - `test_reset_all_chores_delegates_to_manager` - Service delegation
       - `test_undo_chore_claim_delegates_to_manager` - Service delegation
     - ✅ **DONE**: 5 tests implemented and passing

- **Key issues**
  - ✅ RESOLVED: Used event tracking wrapper pattern instead of dispatcher mocking
  - ✅ RESOLVED: Reused scenario_scheduling.yaml fixture for consistency

### Phase 4 – Cleanup (Optional)

- **Goal**: Add deprecation notices to legacy methods (do NOT delete yet).

- **Steps / detailed work items**

  1. `[x]` **Add deprecation docstrings to legacy methods**
     - `_check_overdue_chores_legacy` - Document it's retained for emergency fallback
     - `_process_recurring_chore_resets_legacy` - Same
     - `_handle_overdue_chore_state` - Note: Called by Manager now
     - ✅ **DONE**: Added comprehensive docstrings with:
       - [DEPRECATED] banner with v0.6.0 removal timeline
       - Replacement method references
       - Event emission migration path
       - Guidance on Manager methods

  2. `[x]` **Consider removing legacy code in Phase 6**
     - Not a Phase 4.5b concern
     - Track in future planning document
     - ✅ **NOTED**: Deferred to Phase 6 planning

- **Key issues**
  - Do NOT remove legacy code until Phase 5 validates event-driven architecture works

---

## Testing & validation

- **Tests to run**:
  ```bash
  # New scheduler delegation tests
  pytest tests/test_scheduler_delegation.py -v
  
  # Existing overdue tests (regression check)
  pytest tests/test_chore_scheduling.py -v -k overdue
  pytest tests/test_approval_reset_overdue_interaction.py -v
  
  # Full suite validation
  pytest tests/ -v --tb=line
  ```

- **Quality gates**:
  ```bash
  ./utils/quick_lint.sh --fix
  mypy custom_components/kidschores/
  ```

- **Event verification manual check**:
  - Enable debug logging
  - Trigger timer callback
  - Verify log shows `SIGNAL_SUFFIX_CHORE_OVERDUE` or `SIGNAL_SUFFIX_CHORE_STATUS_RESET`

---

## Notes & follow-up

### Why This Matters for Phase 5

The Event-Driven Gamification Manager (Phase 5) architecture:

```
Timer fires → Coordinator → ChoreManager → Event emitted
                                              ↓
                              GamificationManager listens
                                              ↓
                              Badge/Achievement/Challenge updates
```

Without this delegation, the event flow is broken:

```
Timer fires → Coordinator → Legacy Mixin (NO EVENT) → ❌ GamificationManager deaf
```

### Implementation Notes

1. **Manager methods should be idempotent** - Safe to call multiple times
2. **Preserve existing timing logic** - Don't change WHEN resets happen, just WHO executes
3. **Use existing `mark_overdue()` and `reset_chore()`** - They already emit correct events
4. **Keep legacy code accessible** - Rename to `*_legacy()` don't delete

### Follow-up for Future Phases

- Phase 5: GamificationManager subscribes to `SIGNAL_SUFFIX_CHORE_OVERDUE` and `SIGNAL_SUFFIX_CHORE_STATUS_RESET`
- Phase 6: Consider full removal of legacy timer logic if no regressions

---

> **Document Version:** 1.0
> **Created:** 2026-01-25
> **Author:** Strategic Planning Agent
