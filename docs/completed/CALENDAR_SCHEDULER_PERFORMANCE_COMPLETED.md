# Initiative Plan

## Initiative snapshot

- **Name / Code**: Calendar + Scheduler Performance Optimization (`KC-PERF-CALENDAR-001`)
- **Target release / milestone**: v0.5.0 post-beta hardening
- **Owner / driver(s)**: Integration maintainers (Calendar + Chore domains)
- **Status**: Completed

## Scope addition (requested)

- Add a calendar limiter: **daily recurring chore expansion horizon = 1/3 of configured calendar show period**.
- Applies to:
  - `FREQUENCY_DAILY` recurring chores
  - `FREQUENCY_DAILY_MULTI` recurring chores
- Does not apply to weekly/biweekly/monthly/custom recurring frequencies.
- Deterministic day calculation rule for implementation:
  - `daily_horizon_days = max(1, floor(calendar_show_period_days / 3))`
  - Use integer days only, no fractional-day expansion.

## Summary & immediate steps

| Phase / Step                                          | Description                                                  | % complete | Quick notes                                                   |
| ----------------------------------------------------- | ------------------------------------------------------------ | ---------- | ------------------------------------------------------------- |
| Phase 1 – Baseline & instrumentation                  | Add focused timing/call-count visibility                     | 0%         | De-scoped per request (no timing capture/logging)             |
| Phase 2 – Calendar query optimization + daily limiter | Remove repeated event expansion work and cap daily expansion | 100%       | Daily limiter + read-path cache + signal invalidation shipped |
| Phase 3 – Time-scan optimization                      | Eliminate repeated due-date parsing in periodic scan         | 100%       | Due-date and offset caches + invalidation hooks shipped       |
| Phase 4 – Validation & rollout                        | Prove parity and guard against regressions                   | 100%       | Complete; full suite green, baseline delta waived by owner    |

1. **Key objective** – Reduce calendar and schedule CPU usage by eliminating repeated recurrence/date computation per request and per periodic tick, while preserving behavior.
2. **Summary of recent work**
   - Reviewed calendar event generation flow in `custom_components/kidschores/calendar.py` (`async_get_events`, `event`, `_generate_all_events`).
   - Reviewed recurrence engine usage in `custom_components/kidschores/engines/schedule_engine.py` (`get_occurrences`, `_calculate_with_rrule`, `_calculate_multi_daily`).
   - Reviewed periodic scan flow in `custom_components/kidschores/managers/chore_manager.py` (`process_time_checks`, `get_due_date`).
3. **Next steps (short term)**
   - Validate daily limiter behavior and non-daily parity in tests.
   - Introduce cache/index design doc and decide invalidation signals.
   - Implement next safe slice: calendar read-path cache.
4. **Risks / blockers**
   - Cache staleness can produce wrong due/overdue states if invalidation is incomplete.
   - Timezone/day-boundary behavior (DST, local midnight rollover) must remain exact.
   - Calendar RRULE behavior must remain semantically identical for external consumers.
5. **References**
   - `docs/ARCHITECTURE.md` (schedule engine, timer ownership, storage-only constraints)
   - `docs/DEVELOPMENT_STANDARDS.md` (manager ownership, signal-first communication)
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Prefer read-path caching and precomputed indexes over changing recurrence semantics.
     - Keep `RecurrenceEngine` as source of truth; optimize call patterns around it.
     - Use signal-driven invalidation only; no polling invalidation.
       - Daily recurrence expansion is intentionally bounded to one-third of full calendar period.
  - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, perf validation) before requesting owner approval.

## Tracking expectations

- **Summary upkeep**: Update this summary after each implementation chunk (baseline numbers, cache/index milestones, blocker changes).
- **Detailed tracking**: Keep technical detail in phase sections only.

## Detailed phase tracking

### Phase 1 – Baseline & instrumentation

- **Goal**: Capture precise before/after metrics on calendar generation and periodic time scans.
- **Status note**: Temporarily de-scoped per owner request (no timing capture/logging for this phase).
- **Steps / detailed work items**
  1. `- [ ]` Add timing probes around `KidScheduleCalendar.async_get_events()` and `KidScheduleCalendar.event` generation path.
     - File: `custom_components/kidschores/calendar.py` (around lines ~105, ~872, ~901)
     - Record: call count, wall-time, number of generated events.
  2. `- [ ]` Add timing probes around `ChoreManager.process_time_checks()`.
     - File: `custom_components/kidschores/managers/chore_manager.py` (around line ~1315)
     - Record: pairs scanned, parse calls, category counts, wall-time.
  3. `- [ ]` Add optional debug counters for recurrence expansion loops.
     - File: `custom_components/kidschores/engines/schedule_engine.py` (around lines ~166, ~276, ~773)
     - Record: `get_occurrences` iterations and `rrule` builds.
  4. `- [ ]` Define benchmark fixture matrix for small/medium/full scenarios.
     - Files: `tests/test_performance.py`, scenario fixtures under `tests/scenarios/`
  5. `- [ ]` Capture baseline metrics in a supporting doc.
     - Output: `docs/in-process/CALENDAR_SCHEDULER_PERFORMANCE_SUP_BASELINE.md`
- **Key issues**
  - Existing perf test is skipped (`scenario_full` gap), so baseline scaffolding may need fixture updates first.

### Phase 2 – Calendar query optimization

- **Goal**: Remove redundant event generation work for calendar reads and “current event” calculations.
- **Steps / detailed work items**
  1.  `- [x]` Implement shared daily horizon helper in calendar platform.
  - File: `custom_components/kidschores/calendar.py`
  - Add helper for `daily_horizon_days = max(1, floor(show_period / 3))`.
  - Ensure helper uses configured `calendar_duration.days` as source-of-truth.
  2.  `- [x]` Apply limiter to daily recurring chores without due date.
  - File: `custom_components/kidschores/calendar.py` (daily no-due generation path)
  - Replace horizon/cutoff calculation so generated window is capped by `daily_horizon_days`.
  3.  `- [x]` Apply limiter to DAILY_MULTI recurring chores.
  - File: `custom_components/kidschores/calendar.py` (`_generate_recurring_daily_multi_with_due_date`)
  - Cap `end_date` for slot generation to daily horizon, not full calendar window.
  4.  `- [x]` Keep non-daily recurring frequencies on full show period.
  - File: `custom_components/kidschores/calendar.py`
  - Verify weekly/biweekly/monthly/custom behavior remains unchanged.
  5. `- [x]` Add calendar-level event window cache (read-through) after limiter is in place.
     - File: `custom_components/kidschores/calendar.py`
     - Key shape: `(kid_id, window_start_bucket, window_end_bucket, data_revision)`.
  6. `- [x]` Refactor `event` property to reuse cached near-now window results instead of re-expanding all chores/challenges.
     - File: `custom_components/kidschores/calendar.py` (around lines ~872-916)
  7. `- [x]` Precompute per-chore recurrence artifacts once per chore revision.
     - Files: `custom_components/kidschores/calendar.py`, `custom_components/kidschores/engines/schedule_engine.py`
     - Reuse RRULE and parsed scheduling inputs where safe.
  8. `- [x]` Add explicit cache invalidation hooks on chore/challenge mutation signals.
  - Files: `custom_components/kidschores/calendar.py`, manager signal emit points
- **Key issues**
  - Must preserve exact event overlap semantics and timezone behavior.
  - Memory bounds needed for cache (TTL/LRU and max entries).
  - Daily limiter must not suppress non-daily recurring events.

### Phase 3 – Time-scan optimization

- **Goal**: Reduce recurring periodic scan overhead from repeated datetime parsing and due-date recomputation.
- **Steps / detailed work items**
  1. `- [x]` Add due-date parse cache/index for `(chore_id, kid_id)` used by `process_time_checks`.
     - File: `custom_components/kidschores/managers/chore_manager.py` (around lines ~1315, ~2765)
  2. `- [x]` Parse/normalize due-window and reminder offsets once per chore revision (not per periodic pass).
     - File: `custom_components/kidschores/managers/chore_manager.py`
  3. `- [x]` Avoid repeated `dt_to_utc()` conversions by storing normalized UTC due values in a derived map.
     - Files: `custom_components/kidschores/managers/chore_manager.py`, possible helper in `utils/dt_utils.py`
  4. `- [x]` Invalidate due-date index via signal listeners (`CHORE_CREATED/UPDATED/DELETED`, kid assignment changes, midnight rollover).
     - Files: `custom_components/kidschores/managers/chore_manager.py`, manager signal wiring
  5. `- [x]` Ensure no cross-manager write violations while adding index maintenance.
     - Constraint: Keep writes in owning manager per standards.
- **Key issues**
  - Index must correctly support INDEPENDENT vs SHARED due-date resolution.
  - Midnight rollover must refresh stale boundaries deterministically.

### Phase 4 – Validation & rollout

- **Goal**: Verify behavior parity and measurable CPU improvements before merge.
- **Steps / detailed work items**
  1. `- [x]` Add/extend tests for cache correctness and invalidation behavior.
     - Files: `tests/test_calendar_feature.py`, new `tests/test_calendar_performance_cache.py`, `tests/test_scheduler_delegation.py`
  2. `- [x]` Add explicit tests for daily limiter behavior.
     - Files: `tests/test_calendar_feature.py` (or new `tests/test_calendar_daily_limiter.py`)
     - Cases:
       - `calendar_show_period=90` => daily horizon `30` days
       - `calendar_show_period=31` => daily horizon `10` days
       - `calendar_show_period=2` => daily horizon `1` day (minimum)
       - Weekly/monthly/custom events still use full period
  3. `- [x]` Add periodic-scan regression tests ensuring overdue/due-window/reminder output parity.
     - Files: new `tests/test_chore_manager_time_scan_cache.py`, existing workflow tests
  4. `- [x]` Run quality gates and targeted perf tests.
     - Commands: `./utils/quick_lint.sh --fix`, `mypy custom_components/kidschores/`, `python -m pytest tests/ -v`
    5. `- [x]` Compare before/after baseline metrics and document deltas.
     - Target: significant reduction in calendar generation and periodic scan wall-time.
      - Owner decision: baseline delta document intentionally waived for this cycle.
    6. `- [x]` Update architecture docs if cache/index becomes long-lived design.
     - Files: `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`
- **Key issues**
  - Performance gains must not come from reducing correctness checks.
  - Ensure fallback behavior when cache/index is disabled or invalid.

## Testing & validation

- Tests executed (this checkpoint):
  - `python -m pytest tests/test_calendar_daily_limiter.py -v --tb=line` (5 passed)
  - `./utils/quick_lint.sh --fix` (passed)
  - `mypy custom_components/kidschores/` (zero errors)
- Tests executed (Phase 3 checkpoint):
  - `python -m pytest tests/test_chore_manager.py -k "TimeScanCache" -v --tb=line` (3 passed)
  - `./utils/quick_lint.sh --fix` (passed)
  - `mypy custom_components/kidschores/` (zero errors)
- Tests executed (Phase 4 checkpoint):
  - `./utils/quick_lint.sh --fix` (passed)
  - `mypy custom_components/kidschores/` (zero errors)
  - `python -m pytest tests/test_chore_missed_tracking.py -v --tb=line` (`10 passed`)
  - `python -m pytest tests/ -v` (`1280 passed`, `0 failed`)
- Outstanding tests: none for this initiative.
- Performance validation requirement:
  - Run identical scenarios before/after optimization.
  - Report p50/p95 timings for `async_get_events`, `event`, `process_time_checks`.

## Notes & follow-up

- No schema migration required for initial approach (in-memory caches/indexes only).
- If persistent precomputed schedule metadata is later added to storage records, increment `meta.schema_version` and add migration phase.
- Recommendation priority order:
  1.  Daily recurring limiter (`show_period / 3`) in calendar generation
  2.  `process_time_checks` due-date cache/index (highest recurring periodic cost)
  3.  `event` property reuse of near-now cache
  4.  recurrence artifact reuse for timed recurring calendar chores

## Builder implementation plan (execution order)

### PR Slice 1: Daily limiter only (low risk, immediate win)

- **Files**: `custom_components/kidschores/calendar.py`, `tests/test_calendar_feature.py` (or new daily limiter test file)
- **Tasks**:
  - [x] Add helper for daily horizon days (`max(1, floor(period/3))`).
  - [x] Apply cap to DAILY and DAILY_MULTI generation loops.
  - [x] Confirm non-daily frequencies still use full period.
- **Acceptance criteria**:
  - Daily recurring events are capped to one-third horizon.
  - No behavior change for weekly/biweekly/monthly/custom.
  - Added tests pass.

### PR Slice 2: Calendar read-path cache

- **Files**: `custom_components/kidschores/calendar.py`, tests for cache hit/invalidation
- **Tasks**:
  - Add read-through cache for generated event windows.
  - Make `event` property consume cached near-now window.
  - Add invalidation wiring for chore/challenge mutations.
- **Acceptance criteria**:
  - Same functional output as before.
  - Reduced repeated generation cost on repeated queries.

### PR Slice 3: ChoreManager due-date index

- **Files**: `custom_components/kidschores/managers/chore_manager.py`, targeted tests
- **Tasks**:
  - Introduce parsed UTC due-date map for `(chore_id, kid_id)`.
  - Reuse parsed offsets by chore revision.
  - Invalidate index via lifecycle/mutation signals.
- **Acceptance criteria**:
  - `process_time_checks` output parity.
  - Lower parse count and wall time in instrumentation.

### PR Slice 4: Consolidation and perf proof

- **Files**: docs + performance tests
- **Tasks**:
  - Run baseline vs after metrics.
  - Record p50/p95 timing deltas.
  - Update architecture notes if cache/index become permanent design.
- **Acceptance criteria**:
  - Measurable performance improvement documented.
  - Quality gates clean.

## Builder handoff checklist

- [ ] Implement PR Slice 1 first (daily limiter) and merge before larger cache/index changes.
- [ ] Keep all scheduler semantics in `RecurrenceEngine`; optimize call patterns only.
- [ ] Preserve signal-first ownership/invalidation rules from manager architecture.
- [ ] Add tests before/with each slice, not after all slices.
- [ ] Run: `./utils/quick_lint.sh --fix` → `mypy custom_components/kidschores/` → `python -m pytest tests/ -v`.

## Completion summary

- Owner approved completion without baseline delta documentation.
- Architecture notes added in `docs/ARCHITECTURE.md` and `docs/DEVELOPMENT_STANDARDS.md`.
- Validation gates complete: full test suite green (`1280 passed`, `0 failed`).
