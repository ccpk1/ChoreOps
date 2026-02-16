# Schedule-Aware Streak System

**Initiative Code**: STREAK-001
**Target Release**: v0.5.x
**Owner**: TBD
**Status**: ✅ IMPLEMENTATION COMPLETE - READY FOR MERGE

---

## Initiative Snapshot

| Field              | Value                        |
| ------------------ | ---------------------------- |
| Name               | Schedule-Aware Streak System |
| Code               | STREAK-001                   |
| Priority           | High                         |
| Complexity         | Medium                       |
| Schema Change      | No                           |
| Migration Required | No                           |

---

## Problem Statement

Current streak logic uses a **day-gap** approach: "Was chore completed yesterday?"

This works for daily chores but **breaks** for:

- Weekly chores (shows broken streak every day except completion day)
- Every-3-days chores (false positives on days 2-3)
- Monthly chores (completely broken)

### User Impact

- Streaks reset unexpectedly for non-daily chores
- Users lose motivation when streak tracking is inaccurate
- Weekly/monthly chores show artificially low streaks

---

## Solution Summary

Implement **schedule-aware** streak calculation:

- Use `RecurrenceEngine.has_missed_occurrences()` to check if any scheduled occurrences were skipped
- Preserves existing streak data (no migration)
- Falls back to legacy logic on errors (graceful degradation)
- Documented limitations for edge cases handled in future releases

---

## Summary Table

| Phase   | Description                                        | Status      | Notes                                      |
| ------- | -------------------------------------------------- | ----------- | ------------------------------------------ |
| Phase 1 | Add `has_missed_occurrences()` to RecurrenceEngine | ✅ Done     | schedule_engine.py ~line 178               |
| Phase 2 | Update coordinator streak logic                    | ✅ Done     | coordinator.py lines 4737-4810             |
| Phase 3 | Testing & validation                               | ✅ Done     | 27 tests: 16 unit + 11 integration passing |

---

## Decision Log

| Decision                             | Rationale                                  | Date       |
| ------------------------------------ | ------------------------------------------ | ---------- |
| Schedule-aware (Option 1)            | More accurate for all schedule types       | 2026-01-20 |
| Minimal viable implementation        | Handle core cases first, edge cases later  | 2026-01-20 |
| No migration/schema change           | Existing data structures sufficient        | 2026-01-20 |
| Preserve existing streaks            | Better UX than reset-all approach          | 2026-01-20 |
| Inline in coordinator                | Avoid refactor to StatisticsEngine for now | 2026-01-20 |
| Chores without schedules skip streak | No schedule = no definition of "miss"      | 2026-01-20 |

---

## Known Limitations (Documented, Not Blocking)

1. **Chores without schedules** - No streak calculation
2. **Historical streak validation** - Not retroactive
3. **Vacation/pause handling** - Not retroactive
4. **Schedule changes mid-streak** - Uses current schedule
5. **Multi-claim same day** - Counts once (by design)
6. **Shared chore team streaks** - Per-kid only
7. **Timezone edge cases** - Precise timestamp math

---

## Supporting Documents

| Document                                                                   | Purpose                           |
| -------------------------------------------------------------------------- | --------------------------------- |
| [STREAK_SYSTEM_SUP_MATRIX.md](STREAK_SYSTEM_SUP_MATRIX.md)                 | Decision matrix comparing options |
| [STREAK_SYSTEM_SUP_SIMPLE_PLAN.md](STREAK_SYSTEM_SUP_SIMPLE_PLAN.md)       | **Primary implementation plan**   |
| [STREAK_SYSTEM_SUP_STRATEGY.md](STREAK_SYSTEM_SUP_STRATEGY.md)             | Original strategy notes           |
| [STREAK_SYSTEM_SUP_IMPLEMENTATION.md](STREAK_SYSTEM_SUP_IMPLEMENTATION.md) | Detailed implementation notes     |
| [STREAK_SYSTEM_SUP_EDGE_CASES.md](STREAK_SYSTEM_SUP_EDGE_CASES.md)         | Edge case catalog                 |

**Primary Reference**: Use `STREAK_SYSTEM_SUP_SIMPLE_PLAN.md` for implementation

---

## Files Modified

| File                                      | Change Type   | Status     |
| ----------------------------------------- | ------------- | ---------- |
| `schedule_engine.py`                      | Add method    | ✅ Done    |
| `coordinator.py`                          | Modify        | ✅ Done    |
| `tests/test_schedule_engine_streaks.py`   | New file      | ✅ Created |
| `tests/test_workflow_streak_schedule.py`  | New file      | ✅ Created |
| `tests/test_statistics_engine.py`         | New file      | ✅ Created |

---

## Completion Checklist

### Phase 1: RecurrenceEngine Enhancement

- [x] Add `has_missed_occurrences()` method
- [x] Unit tests pass (existing 42 tests still passing)
- [x] MyPy passes
- [x] Ruff passes

### Phase 2: Coordinator Integration

- [x] Replace day-gap logic with schedule-aware check
- [x] Add fallback to legacy on errors
- [x] Handle chores without schedules (FREQUENCY_NONE → legacy logic)
- [x] Existing tests still pass (824/824)

### Phase 3: Validation

- [x] Unit tests for `has_missed_occurrences()` (16 tests in `test_schedule_engine_streaks.py`)
- [x] Integration tests for streak preservation (11 tests in `test_workflow_streak_schedule.py`)
- [x] All 27 streak tests pass
- [x] Full regression suite passes (851 tests)
- [x] MyPy passes
- [x] Ruff passes

#### Bugs Fixed During Testing

1. **Coordinator bug #1**: `last_approved` was read AFTER being updated, causing incorrect comparison. Fixed by capturing `previous_last_approved_str` BEFORE update.
2. **Coordinator bug #2**: `ScheduleConfig.base_date` used `chore.due_date` (future date) instead of `previous_last_approved_str` (past date). Fixed to use previous approval as base.
3. **Schedule engine bug #3**: `rrule.after()` truncates microseconds to 0, but `current_completion` retained microseconds. This caused `occ < current` to incorrectly pass for same-second comparisons. Fixed by truncating microseconds from `current_completion` before comparison.

---

## Phase 3: Test Scenarios

### Unit Tests for `has_missed_occurrences()` (test_schedule_engine_streaks.py)

| ID     | Scenario               | Inputs                                                  | Expected               |
| ------ | ---------------------- | ------------------------------------------------------- | ---------------------- |
| HMO-01 | Daily consecutive      | last=Jan 1 10am, current=Jan 2 10am                     | `False`                |
| HMO-02 | Daily skip one day     | last=Jan 1 10am, current=Jan 3 10am                     | `True`                 |
| HMO-03 | Daily skip two days    | last=Jan 1 10am, current=Jan 4 10am                     | `True`                 |
| HMO-04 | Every 3 days on-time   | last=Jan 1, current=Jan 4                               | `False`                |
| HMO-05 | Every 3 days early     | last=Jan 1, current=Jan 3                               | `False`                |
| HMO-06 | Every 3 days late      | last=Jan 1, current=Jan 8                               | `True` (missed Jan 4)  |
| HMO-07 | Weekly consecutive     | last=Mon Jan 6, current=Mon Jan 13                      | `False`                |
| HMO-08 | Weekly skip            | last=Mon Jan 6, current=Mon Jan 20                      | `True` (missed Jan 13) |
| HMO-09 | Monthly consecutive    | last=Jan 15, current=Feb 15                             | `False`                |
| HMO-10 | Monthly skip           | last=Jan 15, current=Mar 15                             | `True` (missed Feb 15) |
| HMO-11 | FREQUENCY_NONE         | any dates                                               | `False` (always)       |
| HMO-12 | Same day completion    | last=Jan 1 9am, current=Jan 1 5pm                       | `False`                |
| HMO-13 | Biweekly consecutive   | last=Jan 6, current=Jan 20                              | `False`                |
| HMO-14 | Biweekly skip          | last=Jan 6, current=Feb 3                               | `True` (missed Jan 20) |
| HMO-15 | Applicable days filter | weekly Mon, last=Mon, current=next Mon with Wed between | `False`                |

### Integration Tests for Coordinator Streak Logic (test_workflow_streak_schedule.py)

| ID     | Scenario                  | Setup                                            | Action           | Expected                                    |
| ------ | ------------------------- | ------------------------------------------------ | ---------------- | ------------------------------------------- |
| STK-01 | First approval            | Kid has no last_approved for chore               | Approve          | streak = 1                                  |
| STK-02 | Daily consecutive         | Chore daily, approved yesterday, streak=5        | Approve today    | streak = 6                                  |
| STK-03 | Daily break               | Chore daily, approved 2 days ago, streak=5       | Approve today    | streak = 1                                  |
| STK-04 | Weekly on-time            | Chore weekly Mon, approved last Mon, streak=3    | Approve this Mon | streak = 4                                  |
| STK-05 | Weekly break              | Chore weekly Mon, approved 2 weeks ago, streak=3 | Approve today    | streak = 1                                  |
| STK-06 | No frequency legacy       | Chore has FREQUENCY_NONE, approved yesterday     | Approve today    | streak continues (legacy)                   |
| STK-07 | Error fallback            | Chore has invalid schedule config                | Approve          | streak continues (legacy fallback)          |
| STK-08 | All-time update           | streak=10, new approval continues                | Approve          | all_time longest = 11                       |
| STK-09 | Period updates            | Daily approval                                   | Approve          | daily/weekly/monthly/yearly streaks updated |
| STK-10 | Every 3 days continue     | Chore every 3 days, approved 3 days ago          | Approve today    | streak continues                            |
| STK-11 | Every 3 days break        | Chore every 3 days, approved 7 days ago          | Approve today    | streak = 1                                  |
| STK-12 | Existing streak preserved | Kid has streak=10 from yesterday                 | Approve today    | streak = 11 (not reset)                     |

### Edge Cases

| ID      | Scenario              | Notes                                      |
| ------- | --------------------- | ------------------------------------------ |
| EDGE-01 | Midnight boundary     | Approval at 11:59pm vs 12:01am next day    |
| EDGE-02 | Timezone edge         | Local vs UTC comparison                    |
| EDGE-03 | Missing base_date     | Schedule config without base_date uses now |
| EDGE-04 | Empty applicable_days | Should not constrain occurrences           |

---

## Test Builder Handoff

**Task**: Create tests for schedule-aware streak system

### Files to Create

1. **`tests/test_schedule_engine_streaks.py`** - Unit tests for `has_missed_occurrences()`
2. **`tests/test_workflow_streak_schedule.py`** - Integration tests for coordinator streak logic

### Implementation Reference

**Method under test**: `RecurrenceEngine.has_missed_occurrences(last_completion, current_completion)`

- Location: `custom_components/kidschores/schedule_engine.py` line ~178
- Returns `True` if any scheduled occurrence was missed between the two timestamps
- Returns `False` if streak should continue

**Coordinator logic under test**: `_update_kid_chore_state()` streak calculation

- Location: `custom_components/kidschores/coordinator.py` lines 4737-4810
- Uses `has_missed_occurrences()` for chores with frequency
- Falls back to legacy day-gap for FREQUENCY_NONE or errors

### Test Patterns to Follow

```python
# Unit test pattern for has_missed_occurrences
from custom_components.kidschores.schedule_engine import RecurrenceEngine
from custom_components.kidschores.type_defs import ScheduleConfig

def test_hmo_01_daily_consecutive():
    """Daily chore: consecutive days = no miss."""
    config: ScheduleConfig = {
        "frequency": const.FREQUENCY_DAILY,
        "base_date": "2026-01-01T10:00:00+00:00",
    }
    engine = RecurrenceEngine(config)
    last = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    current = datetime(2026, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    assert not engine.has_missed_occurrences(last, current)
```

```python
# Integration test pattern - use scenario fixtures
async def test_stk_02_daily_consecutive(
    hass: HomeAssistant,
    coordinator: KidsChoresDataCoordinator,
    scenario_medium: dict,
) -> None:
    """Daily chore streak continues on consecutive days."""
    kid = get_kid_by_name(coordinator, "Lyra")
    chore = get_chore_by_name(coordinator, "Make Bed")

    # Setup: Set chore frequency to DAILY
    chore[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_DAILY

    # Setup: Set yesterday's streak to 5
    # ... (see STREAK_SYSTEM_SUP_SIMPLE_PLAN.md for full pattern)

    # Action: Approve today
    await approve_chore_via_button(hass, coordinator, kid, chore)

    # Assert: Streak is now 6
    assert today_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] == 6
```

### Priority

1. **High**: HMO-01 through HMO-08 (daily, every-N-days, weekly)
2. **Medium**: STK-01 through STK-05 (first approval, consecutive, break)
3. **Lower**: Edge cases (can be added later)

### Existing Test Patterns

Reference `tests/test_schedule_engine.py` for RecurrenceEngine test patterns.
Reference `tests/test_workflow_chores.py` for coordinator integration test patterns.

---

### Final Checklist

- [x] All quality gates pass (mypy, ruff, 851 tests)
- [ ] Move docs to `completed/` folder
- [ ] Update CHANGELOG
