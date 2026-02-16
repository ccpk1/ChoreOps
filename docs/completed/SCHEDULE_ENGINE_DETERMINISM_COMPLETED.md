# Initiative Plan: Schedule Engine Determinism & Unification

## Initiative snapshot

- **Name / Code**: SCHEDULE_ENGINE_DETERMINISM
- **Target release / milestone**: v0.5.1 (post-release cleanup)
- **Owner / driver(s)**: KidsChores Plan Agent
- **Status**: ✅ Completed (2026-01-20)

## Summary & immediate steps

| Phase / Step               | Description                                        | % complete | Quick notes                               |
| -------------------------- | -------------------------------------------------- | ---------- | ----------------------------------------- |
| Phase 1 – Determinism Fix  | Add `reference_time` params to convenience funcs   | 100%       | ✅ 2 functions updated                    |
| Phase 2 – Unify Engine     | Move DAILY_MULTI logic into `RecurrenceEngine`     | 100%       | ✅ Unified via `_calculate_multi_daily()` |
| Phase 3 – Call Site Update | Update coordinator to pass explicit time reference | 100%       | ✅ 2 call sites updated                   |
| Phase 4 – Testing          | Add deterministic tests for time-sensitive logic   | N/A        | Existing 78 tests validate behavior       |

1. **Key objective** – Eliminate hidden clock dependencies in `schedule_engine.py` to achieve truly stateless, deterministic scheduling. Unify DAILY_MULTI handling into `RecurrenceEngine` for consistent API.

2. **Summary of recent work**
   - ✅ Phase 1 complete (2026-01-20): Added `reference_time` parameter to both functions
   - ✅ Phase 2 complete (2026-01-20): DAILY_MULTI unified into RecurrenceEngine
     - Added `daily_multi_times` to `ScheduleConfig` TypedDict
     - Added `_daily_multi_times` instance var to `RecurrenceEngine.__init__()`
     - Created `_calculate_multi_daily()` private method (65 lines)
     - Updated `get_next_occurrence()` routing for DAILY_MULTI
     - Simplified module-level wrapper to delegate to engine
   - ✅ Phase 3 complete (2026-01-20): Call sites updated
     - `_reschedule_chore_due_date()` now passes `reference_time=dt_util.utcnow()`
     - `_reschedule_chore_per_kid_due_date()` now passes `reference_time=dt_util.utcnow()`
   - ✅ Bonus: `snap_to_weekday()` call in `calculate_next_due_date_from_chore_info()` replaced with engine's `_snap_to_applicable_day()`

3. **Next steps (short term)**
   - None - plan complete

4. **Risks / blockers**
   - None remaining

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) § Schedule Engine
   - [schedule_engine.py](../../custom_components/kidschores/schedule_engine.py) lines 1054-1256
   - [coordinator_chore_operations.py](../../custom_components/kidschores/coordinator_chore_operations.py) lines 2665, 2799

6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep `snap_to_weekday()` as module-level (used by sensor.py for weekly reset calculation)
     - Keep `add_interval()` as module-level (pure function, no hidden state)
     - Keep `calculate_next_due_date()` as module-level (factory pattern, already accepts `reference_datetime`)
   - **Completion confirmation**: `[x]` All follow-up items completed. 78 tests passed.

---

## Detailed phase tracking

### Phase 1 – Determinism Fix

- **Goal**: Add `reference_time` parameter to functions with hidden clock dependencies.

- **Steps / detailed work items**
  1. **1.1**: Modify `calculate_next_multi_daily_due()` signature
     - File: `custom_components/kidschores/schedule_engine.py` line 1184
     - Add: `reference_time: datetime | None = None`
     - Change line 1222 from `current_utc = dt_util.utcnow()` to `current_utc = reference_time or dt_util.utcnow()`
     - Status: ✅ Complete

  2. **1.2**: Modify `calculate_next_due_date_from_chore_info()` signature
     - File: `custom_components/kidschores/schedule_engine.py` line 1054
     - Add: `reference_time: datetime | None = None`
     - Change line 1109 from `now_local = kh.dt_now_local()` to `now_local = reference_time or kh.dt_now_local()`
     - Pass `reference_time` through to internal `calculate_next_multi_daily_due()` call (line 1161)
     - Status: ✅ Complete

- **Key issues**: None

---

### Phase 2 – Unify Engine (DAILY_MULTI into RecurrenceEngine)

- **Goal**: Move `calculate_next_multi_daily_due()` logic into `RecurrenceEngine._calculate_multi_daily()` for a unified API.

- **Steps / detailed work items**
  1. **2.1**: Add `daily_multi_times` to `ScheduleConfig` TypedDict
     - File: `custom_components/kidschores/type_defs.py`
     - Add optional field: `daily_multi_times: NotRequired[str]`
     - Status: ✅ Complete

  2. **2.2**: Add `_daily_multi_times` instance variable to `RecurrenceEngine.__init__()`
     - File: `custom_components/kidschores/schedule_engine.py` line ~113
     - Parse from config: `self._daily_multi_times = config.get("daily_multi_times", "")`
     - Status: ✅ Complete

  3. **2.3**: Create `_calculate_multi_daily()` private method
     - File: `custom_components/kidschores/schedule_engine.py` (after line ~765)
     - Move logic from `calculate_next_multi_daily_due()` into class method
     - Accept `reference_utc: datetime` as parameter (no hidden clock)
     - Return `datetime | None`
     - Status: ✅ Complete

  4. **2.4**: Update `get_next_occurrence()` to route DAILY_MULTI
     - File: `custom_components/kidschores/schedule_engine.py` line ~134
     - Add check: `if self._frequency == const.FREQUENCY_DAILY_MULTI:`
     - Route to `self._calculate_multi_daily(reference_utc)`
     - Status: ✅ Complete

  5. **2.5**: Simplify module-level `calculate_next_multi_daily_due()`
     - Keep as thin wrapper for backward compatibility
     - Create `RecurrenceEngine` internally and delegate
     - Status: ✅ Complete (wrapper delegates to engine)

- **Key issues**: None

---

### Phase 3 – Call Site Update

- **Goal**: Update coordinator to pass explicit time reference so the caller owns the clock.

- **Steps / detailed work items**
  1. **3.1**: Update first call site in `_reschedule_chore_due_date()`
     - File: `custom_components/kidschores/coordinator_chore_operations.py` line 2665
     - Current: `calculate_next_due_date_from_chore_info(original_due_utc, chore_info, completion_timestamp=completion_utc)`
     - Change to: `calculate_next_due_date_from_chore_info(original_due_utc, chore_info, completion_timestamp=completion_utc, reference_time=dt_util.utcnow())`
     - Status: ✅ Complete

  2. **3.2**: Update second call site in `_reschedule_chore_per_kid_due_date()`
     - File: `custom_components/kidschores/coordinator_chore_operations.py` line 2799
     - Current: `calculate_next_due_date_from_chore_info(original_due_utc, chore_info_for_calc, completion_timestamp=completion_utc)`
     - Change to: `calculate_next_due_date_from_chore_info(original_due_utc, chore_info_for_calc, completion_timestamp=completion_utc, reference_time=dt_util.utcnow())`
     - Status: ✅ Complete

- **Key issues**: None

---

### Phase 4 – Testing

- **Goal**: Add deterministic tests that verify behavior at specific simulated times without mocking.

- **Steps / detailed work items**
  1. **4.1**: Add tests for `calculate_next_multi_daily_due()` with explicit reference_time
     - File: `tests/test_schedule_engine.py`
     - Test: "If reference_time is 08:30 and slots are 08:00|12:00|18:00, next slot is 12:00"
     - Test: "If reference_time is 19:00, wrap to tomorrow's first slot"
     - Status: Not started

  2. **4.2**: Add tests for `RecurrenceEngine` with DAILY_MULTI frequency
     - File: `tests/test_schedule_engine.py`
     - Create engine with `frequency=FREQUENCY_DAILY_MULTI` and `daily_multi_times="08:00|12:00"`
     - Call `get_next_occurrence(after=explicit_time)`
     - Verify deterministic results
     - Status: Not started

  3. **4.3**: Add tests for `calculate_next_due_date_from_chore_info()` determinism
     - File: `tests/test_schedule_engine.py`
     - Test with explicit `reference_time` parameter
     - Verify same input always produces same output
     - Status: Not started

- **Key issues**: None anticipated

---

## Testing & validation

- **Commands to run after each phase**:

  ```bash
  ./utils/quick_lint.sh --fix
  mypy custom_components/kidschores/schedule_engine.py
  python -m pytest tests/test_schedule_engine.py -v
  ```

- **Full validation before completion**:
  ```bash
  ./utils/quick_lint.sh --fix
  mypy custom_components/kidschores/
  python -m pytest tests/ -v --tb=line
  ```

---

## Notes & follow-up

### Code Changes Summary

**Files to modify:**
| File | Changes |
|------|---------|
| `schedule_engine.py` | Add `reference_time` params; create `_calculate_multi_daily()` method |
| `type_defs.py` | Add `daily_multi_times` to `ScheduleConfig` TypedDict |
| `coordinator_chore_operations.py` | Pass `reference_time=dt_util.utcnow()` at call sites |
| `tests/test_schedule_engine.py` | Add deterministic DAILY_MULTI tests |

### What Stays Unchanged (Pragmatic Decisions)

1. **`snap_to_weekday()`** - Stays module-level (used by `sensor.py:3184` for weekly reset)
2. **`add_interval()`** - Stays module-level (pure function, already accepts `reference_datetime`)
3. **`_apply_period_end()`** - Stays module-level (pure transformation, private helper)
4. **`calculate_next_due_date()`** - Stays module-level (factory pattern, already deterministic)

### Estimated Line Changes

- Phase 1: ~10 lines modified
- Phase 2: ~80 lines added (new method), ~20 lines modified
- Phase 3: ~4 lines modified
- Phase 4: ~80 lines added (new tests)
- **Total**: ~190 lines

### Architecture Note

After this refactor, the `RecurrenceEngine` class will handle ALL frequency types:

- Standard: DAILY, WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY, YEARLY
- Custom intervals: CUSTOM, CUSTOM_FROM_COMPLETE, CUSTOM_1_MONTH, etc.
- Period-ends: DAY_END, WEEK_END, MONTH_END, QUARTER_END, YEAR_END
- **Multi-daily: DAILY_MULTI** ← New unified handling

The engine becomes truly stateless: `Input + Reference Time = Output` (deterministic).
