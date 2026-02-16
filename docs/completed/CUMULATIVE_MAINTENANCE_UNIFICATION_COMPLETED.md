# Cumulative Badge Maintenance — Unified Evaluation Path

## Initiative snapshot

- **Name / Code**: Cumulative Maintenance Unification
- **Target release / milestone**: v0.5.0-beta4
- **Owner / driver(s)**: KidsChores team
- **Status**: Completed

## Summary & immediate steps

| Phase / Step                                  | Description                                                         | % complete | Quick notes                                                                                   |
| --------------------------------------------- | ------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------- |
| Phase 1 – Extend `_evaluate_cumulative_badge` | Add date awareness + demotion + grace to unified method             | 100%       | ✅ Complete - 3 new helpers, state machine unified, validation passed                         |
| Phase 2 – Midnight becomes "mark all pending" | Simplify midnight handler + delete `process_cumulative_maintenance` | 100%       | ✅ Complete - ~266 lines deleted, midnight calls `recalculate_all_badges()`, constant removed |
| Phase 3 – Engine cleanup                      | Remove or refine `check_cumulative_maintenance` engine method       | 100%       | ✅ Complete - ~64 line method deleted, tests removed, manager does inline comparison          |
| Phase 4 – Tests                               | Update/create tests for unified path                                | 100%       | ✅ Complete - unified-path tests updated and passing                                           |

1. **Key objective** – Merge the two independent cumulative badge state machines (real-time `_evaluate_cumulative_badge` and midnight `process_cumulative_maintenance`) into a single date-aware evaluation path. The unified method runs identically regardless of trigger (point change, chore approval, midnight rollover).

2. **Summary of recent work**
   - Separated cumulative vs periodic badge evaluation into dedicated methods (`_evaluate_cumulative_badge`, `_evaluate_periodic_badge`)
   - Collapsed engine wrappers (`check_acquisition` → `evaluate_badge`, inlined `_evaluate_cumulative_retention` into `check_cumulative_maintenance`)
   - Identified the dual-path problem: real-time path ignores dates and can't demote; midnight path duplicates cycle_points check with its own state machine

3. **Next steps (short term)**
    - Completed and archived.

4. **Risks / blockers**
   - `get_cumulative_badge_levels()` is used by midnight path to find the _highest earned_ badge. The real-time path evaluates _each badge individually_. The unified path must evaluate per-badge but only act on the highest-earned for maintenance/demotion decisions.
   - `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` is emitted by `process_all_kids_maintenance()` but has zero listeners. Safe to remove, but verify no dashboard/UI code expects it.
   - Grace state transition must be idempotent — repeated evaluations during grace period must not re-enter grace or reset grace_end date.

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — Data model, cumulative badge progress structure
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Manager write ownership, signal patterns
    - [CUMULATIVE_BADGE_RETENTION_FIX_COMPLETED.md](CUMULATIVE_BADGE_RETENTION_FIX_COMPLETED.md) — Prior work that created the dual-path problem
    - [CUMULATIVE_BADGE_RETENTION_FIX_SUP_GAP_ANALYSIS_COMPLETED.md](CUMULATIVE_BADGE_RETENTION_FIX_SUP_GAP_ANALYSIS_COMPLETED.md) — Gap analysis including dead signals

6. **Decisions & completion check**
   - **Decision 1**: The unified `_evaluate_cumulative_badge` already-earned branch will own ALL state transitions (ACTIVE ↔ GRACE ↔ DEMOTED). Midnight rollover becomes a trigger, not a separate state machine.
   - **Decision 2**: `process_cumulative_maintenance()` and `process_all_kids_maintenance()` will be deleted entirely (not preserved as wrappers).
   - **Decision 3**: `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` will be removed (zero listeners).
    - **Completion confirmation**: `[x]` All follow-up items completed before requesting owner approval.

---

## The Problem

Two independent state machines evaluate cumulative badge maintenance:

### Path A: Real-time (`_evaluate_cumulative_badge`, line ~808)

- **Triggered by**: point changes, chore approvals, bonus/penalty events (via debounce)
- **Can**: Award first-time badge, re-promote DEMOTED → ACTIVE
- **Cannot**: Demote, enter GRACE, check dates
- **Bug**: Checks `cycle_points >= threshold` but ignores `maintenance_end_date` entirely. Can re-promote a kid mid-cycle before the maintenance period ends.

### Path B: Midnight (`process_cumulative_maintenance`, line ~2218)

- **Triggered by**: `_on_midnight_rollover` signal → `process_all_kids_maintenance()`
- **Can**: Award, demote, enter GRACE, check dates
- **Cannot**: Run except at midnight
- **Problem**: Duplicates the cycle_points check with its own independent state machine (~250 lines)

### What goes wrong

1. **Re-promotion without date guard**: Kid gets demoted at midnight. Earns 5 points. Real-time path sees `cycle_points >= threshold` and immediately re-promotes — even though the _new_ maintenance period just started today and hasn't ended yet. The re-promotion should only happen when the maintenance period ends and the kid has met requirements.

2. **Split brain**: Two methods modify the same `cumulative_badge_progress` dict with overlapping fields (`status`, `cycle_points`, dates) but different logic. A race condition is waiting to happen if midnight fires while a debounced evaluation is pending.

3. **Maintenance duplication**: Both paths call `_calculate_maintenance_dates()`, `update_point_multiplier_for_kid()`, emit `SIGNAL_SUFFIX_BADGE_EARNED`, and write to `cumulative_badge_progress`. All duplicated.

---

## Detailed phase tracking

### Phase 1 – Extend `_evaluate_cumulative_badge` with full state machine

- **Goal**: Make `_evaluate_cumulative_badge` the ONE place that handles all cumulative badge state transitions for an already-earned badge. The method must be date-aware, handle grace, and handle demotion.

- **Steps / detailed work items**
  1. - [x] **Restructure the already-earned branch** in `_evaluate_cumulative_badge` (line ~848-857)
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Currently: calls `check_cumulative_maintenance()` engine → if met, re-promote; if not met, do nothing
     - New logic (replaces lines 848-857):

       ```
       # 1. Is maintenance enabled?
       if not self._badge_maintenance_enabled(badge_data):
           return  # No maintenance = always ACTIVE, nothing to evaluate

       # 2. Read dates and status from cumulative_badge_progress
       progress = kid_data.get(DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
       status = progress.get(STATUS, ACTIVE)
       end_date = progress.get(MAINTENANCE_END_DATE)
       grace_end = progress.get(MAINTENANCE_GRACE_END_DATE)
       cycle_points = progress.get(CYCLE_POINTS, 0.0)
       maintenance_threshold = badge target maintenance_rules
       today = dt_today_iso()

       # 3. First-time dates (badge earned but dates not yet initialized)
       if not end_date:
           → _apply_cumulative_init_maintenance_dates(kid_id, badge_id, badge_data)
           return

       # 4. Maintenance period still open (today < end_date)
       if today < end_date:
           return  # Just accumulate points, no state change yet

       # 5. Maintenance period ended (today >= end_date)
       if cycle_points >= maintenance_threshold:
           → _apply_cumulative_maintenance_met(kid_id, badge_id, badge_data)
           return  # Re-promote (or confirm ACTIVE), reset cycle, advance dates

       # 6. Not met — check grace
       if status == GRACE:
           if today >= grace_end:
               → _apply_cumulative_demotion(kid_id, badge_id, badge_data)
           # else: still in grace, do nothing
           return

       # 7. Not met, not in grace — enter grace or demote immediately
       grace_days = badge reset_schedule grace_period_days
       if grace_days > 0:
           → _apply_cumulative_enter_grace(kid_id, badge_id, badge_data, end_date, grace_days)
       else:
           → _apply_cumulative_demotion(kid_id, badge_id, badge_data)
       ```

  2. - [x] **Create `_apply_cumulative_init_maintenance_dates()`** — new helper method
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Purpose: Set initial maintenance dates for a badge that was just earned but has no dates yet
     - Logic: Call `_calculate_maintenance_dates()`, write to progress, persist
     - Extracted from: `process_cumulative_maintenance` first-time branch (line ~2460-2469)

  3. - [x] **Create `_apply_cumulative_enter_grace()`** — new helper method
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Purpose: Transition status to GRACE, set grace_end date
     - Logic: Set status=GRACE, calculate grace_end from end_date + grace_days, persist
     - Extracted from: `process_cumulative_maintenance` grace entry branch (line ~2365-2390)

  4. - [x] **Create `_apply_cumulative_demotion()`** — new helper method
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Purpose: Demote badge (status=DEMOTED, reset cycle, recalc multiplier, advance dates)
     - Logic: Set status=DEMOTED, cycle_points=0, advance dates, call `update_point_multiplier_for_kid()`, emit `SIGNAL_SUFFIX_BADGE_UPDATED`
     - Extracted from: `process_cumulative_maintenance` demotion branch (line ~2416-2455)

  5. - [x] **Update `_apply_cumulative_maintenance_met()`** — existing method (line ~962)
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Current: Only acts if status == DEMOTED (re-promote guard)
     - Change: Also handle status == ACTIVE or GRACE when maintenance_met (cycle reset, date advance, re-emit rewards). Remove the "only if DEMOTED" guard — maintenance-met means "confirm ACTIVE + reset cycle" regardless of current status.
     - Keep: data corruption repair for DEMOTED-when-maintenance-disabled

  6. - [x] **Add highest-badge guard in `_evaluate_cumulative_badge` already-earned branch**
     - **REQUIRED**: Maintenance/demotion/grace ONLY applies to the highest-earned cumulative badge. Lower-tier earned badges are always ACTIVE with no maintenance evaluation.
     - At the top of the already-earned branch, call `get_cumulative_badge_levels(kid_id)` and compare:
       ```python
       highest_earned, _, _, _, _ = self.get_cumulative_badge_levels(kid_id)
       highest_badge_id = (
           highest_earned.get(const.DATA_BADGE_INTERNAL_ID) if highest_earned else None
       )
       if badge_id != highest_badge_id:
           return  # Only evaluate maintenance for the highest-earned badge
       ```
     - This keeps the single loop in `_evaluate_kid()` intact. Lower-tier badges still get acquisition checked (the `not already_earned` branch), but once earned, their maintenance is skipped.

- **Key issues**
  - The engine's `check_cumulative_maintenance()` may become unnecessary if all date/threshold logic moves to the manager. Addressed in Phase 3.
  - `_apply_cumulative_maintenance_met` currently resets `cycle_points = 0` on re-promotion. This is correct for the unified path too (new cycle starts).
  - Idempotency: If evaluation fires twice after end_date with the same cycle_points, both calls must produce the same outcome (not double-demote or double-award).
  - `get_cumulative_badge_levels()` is an O(n) scan of cumulative badges. Called once per kid per evaluation cycle — acceptable performance.

### Phase 2 – Midnight becomes "mark all pending"

- **Goal**: Remove the separate midnight state machine. Midnight rollover simply marks all kids for re-evaluation via the standard debounced path.

- **Steps / detailed work items**
  1. - [x] **Simplify `_on_midnight_rollover()`** (line ~307)
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Change from: `self.process_all_kids_maintenance()`
     - Change to: `self.recalculate_all_badges()`
     - This marks all kids pending → debounce fires → `_evaluate_kid()` → `_evaluate_cumulative_badge()` (now date-aware)

  2. - [x] **Delete `process_cumulative_maintenance()`** (lines ~2218-2470, ~252 lines)
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Entire method removed — logic now lives in `_evaluate_cumulative_badge` + apply helpers

  3. - [x] **Delete `process_all_kids_maintenance()`** (lines ~2472-2485, ~14 lines)
     - File: `custom_components/kidschores/managers/gamification_manager.py`
     - Was just a loop calling `process_cumulative_maintenance()` + dead signal emit

  4. - [x] **Remove `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK`**
     - File: `custom_components/kidschores/const.py` (line ~226)
     - Zero listeners confirmed. Remove constant definition.
     - Also remove references in documentation files if desired (non-blocking).

  5. - [x] **Update `recalculate_all_badges()` if needed** (line ~327)
     - Currently marks all kids pending. After midnight rollover calls it, the debounced `_evaluate_kid()` will run the full badge evaluation including the new maintenance logic.
     - Verify: does `recalculate_all_badges()` also need to emit `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` replacement? No — `_evaluate_cumulative_badge` already emits `BADGE_EARNED` or `BADGE_UPDATED` per-kid. UI sensors listen to those.

- **Key issues**
  - Midnight rollover currently calls `process_all_kids_maintenance()` synchronously (it's `def`, not `async def`). `recalculate_all_badges()` is also sync (just marks pending). The debounced evaluation is async and runs later. This is correct behavior — no change needed.
  - Other callers: `process_all_kids_maintenance()` is only called from `_on_midnight_rollover` (confirmed by grep). Safe to delete.

### Phase 3 – Engine cleanup

- **Goal**: Decide what to do with `GamificationEngine.check_cumulative_maintenance()` now that the manager handles all date/state logic.

- **Steps / detailed work items**
  1. - [x] **Evaluate whether `check_cumulative_maintenance()` is still needed**
     - File: `custom_components/kidschores/engines/gamification_engine.py` (line ~275)
     - Currently: pure comparison of `cycle_points >= maintenance_threshold`
     - After Phase 1: the manager reads `cycle_points` and `maintenance_threshold` directly and compares them itself (lines added in Phase 1, step 1, bullet 5)
     - **If manager does the comparison inline**: Delete `check_cumulative_maintenance()` from engine (it's a 1-line comparison wrapped in 40 lines of result-building)
     - **If keeping engine as reusable evaluator**: Keep it, but the manager already knows the answer before calling it (since manager has the date context). Keeping it adds no value.
     - **Recommended**: Delete. The engine's value is in complex multi-target evaluation (which `evaluate_badge` does). A single `>=` comparison doesn't warrant an engine method.
     - **DECISION**: Deleted. Manager does inline comparison in unified state machine.

  2. - [x] **If deleting**: Update tests in `tests/test_gamification_engine.py`
     - Remove `TestAcquisitionAndMaintenance` class tests for `check_cumulative_maintenance` (lines ~555-572)
     - Removed entire test class (only tested deleted method)

  3. - [x] **If deleting**: Update engine class docstring and imports
     - File: `custom_components/kidschores/engines/gamification_engine.py`
     - Remove from public API documentation at top of class
     - No import changes expected (method is a classmethod on the same class)

- **Key issues**
  - `dry_run_badge()` (line ~1393) currently only calls `evaluate_badge()`, not `check_cumulative_maintenance()`. No impact from deletion.
  - `get_cumulative_badge_levels()` doesn't call any engine methods. No impact.

### Phase 4 – Tests

- **Goal**: Ensure unified path is fully tested with date-based scenarios.

- **Steps / detailed work items**
  1. - [ ] **Create integration tests for the unified cumulative maintenance flow**
     - File: `tests/test_cumulative_maintenance_unified.py` (new)
     - Test scenarios:
       - **First-time award**: kid earns badge → dates initialized → status=ACTIVE
       - **Mid-cycle evaluation**: today < end_date, cycle_points accumulate → no state change
       - **Maintenance met at period end**: today >= end_date, cycle_points >= threshold → ACTIVE confirmed, cycle reset, dates advanced, Award Manifest emitted
       - **Grace entry**: today >= end_date, cycle_points < threshold, grace_days > 0 → status=GRACE, grace_end calculated
       - **Grace met**: status=GRACE, cycle_points >= threshold → re-promote to ACTIVE
       - **Grace expired**: status=GRACE, today >= grace_end, cycle_points < threshold → DEMOTED
       - **Immediate demotion**: today >= end_date, cycle_points < threshold, grace_days=0 → DEMOTED immediately
       - **Re-promotion after demotion**: DEMOTED, new cycle ends, cycle_points >= threshold → ACTIVE
       - **Idempotency**: two evaluations with same state produce same result
       - **Midnight trigger**: midnight rollover → all kids evaluated → same state machine runs

  2. - [ ] **Update existing engine tests**
     - File: `tests/test_gamification_engine.py`
     - If `check_cumulative_maintenance` deleted: remove tests at lines ~555-572
     - Ensure `evaluate_badge` tests for cumulative acquisition still pass

  3. - [ ] **Verify no test imports `process_cumulative_maintenance` or `process_all_kids_maintenance`**
     - Grep tests/ for these method names
     - If found, refactor to use the new unified path (trigger via `_mark_pending` / `_evaluate_kid`)

  4. - [ ] **Run full quality gates**
     ```bash
     ./utils/quick_lint.sh --fix
     mypy custom_components/kidschores/
     python -m pytest tests/ -v --tb=line
     ```

- **Key issues**
  - Use `scenario_medium` test fixtures (per `AGENT_TESTING_USAGE_GUIDE.md`)
  - Mock `dt_today_iso()` to control date for time-based assertions
  - Prefer service-based tests where possible, but direct manager method tests are acceptable for internal logic

---

## Data flow after unification

```
Any trigger (point change, chore approval, midnight rollover, manual recalc)
    │
    ▼
_mark_pending(kid_id) → debounce 2s → _evaluate_pending_kids()
    │
    ▼
_evaluate_kid(kid_id)
    │
    ├── for each badge: _evaluate_badge_for_kid()
    │       │
    │       ├── CUMULATIVE → _evaluate_cumulative_badge()
    │       │       │
    │       │       ├── NOT earned → evaluate_badge() → first award?
    │       │       │       → _apply_cumulative_first_award()
    │       │       │
    │       │       └── EARNED → date-aware state machine:
    │       │               ├── No maintenance → return
    │       │               ├── No dates yet → _apply_cumulative_init_maintenance_dates()
    │       │               ├── today < end_date → return (accumulate)
    │       │               ├── cycle_points >= threshold → _apply_cumulative_maintenance_met()
    │       │               ├── In GRACE + expired → _apply_cumulative_demotion()
    │       │               ├── grace_days > 0 → _apply_cumulative_enter_grace()
    │       │               └── grace_days == 0 → _apply_cumulative_demotion()
    │       │
    │       └── PERIODIC → _evaluate_periodic_badge()
    │
    ├── for each achievement: _evaluate_achievement_for_kid()
    └── for each challenge: _evaluate_challenge_for_kid()
```

**Midnight rollover changes from**:

```
_on_midnight_rollover()
    → process_all_kids_maintenance()
        → for each kid: process_cumulative_maintenance(kid_id)  ← 250-line state machine
```

**To**:

```
_on_midnight_rollover()
    → recalculate_all_badges()
        → for each kid: _mark_pending(kid_id) → debounce → _evaluate_kid()
```

---

## Methods deleted

| Method                                              | Lines                   | Reason                                                                |
| --------------------------------------------------- | ----------------------- | --------------------------------------------------------------------- |
| `process_cumulative_maintenance()`                  | ~2218-2470 (~252 lines) | Replaced by unified `_evaluate_cumulative_badge`                      |
| `process_all_kids_maintenance()`                    | ~2472-2485 (~14 lines)  | Was loop + dead signal; midnight now calls `recalculate_all_badges()` |
| `GamificationEngine.check_cumulative_maintenance()` | ~275-335 (~60 lines)    | Single comparison doesn't warrant engine method                       |

## Methods added

| Method                                       | Purpose                                                   |
| -------------------------------------------- | --------------------------------------------------------- |
| `_apply_cumulative_init_maintenance_dates()` | Set initial dates for newly earned badge with maintenance |
| `_apply_cumulative_enter_grace()`            | Transition ACTIVE/DEMOTED → GRACE                         |
| `_apply_cumulative_demotion()`               | Transition → DEMOTED, recalc multiplier, emit signal      |

## Methods modified

| Method                                | Change                                                                     |
| ------------------------------------- | -------------------------------------------------------------------------- |
| `_evaluate_cumulative_badge()`        | Already-earned branch becomes full date-aware state machine                |
| `_apply_cumulative_maintenance_met()` | Remove "only if DEMOTED" guard; handle any status → ACTIVE + cycle reset   |
| `_on_midnight_rollover()`             | Change from `process_all_kids_maintenance()` to `recalculate_all_badges()` |

## Constants removed

| Constant                                | File                 | Reason                      |
| --------------------------------------- | -------------------- | --------------------------- |
| `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` | `const.py` line ~226 | Zero listeners, dead signal |

---

## Testing & validation

- `tests/test_gamification_engine.py` — update after engine method removal
- `tests/test_cumulative_maintenance_unified.py` — new test file with 9+ scenarios
- Run: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/ && python -m pytest tests/ -v --tb=line`

## Notes & follow-up

- The `get_cumulative_badge_levels()` method continues to serve UI/dashboard helper and multiplier calculation. Not affected by this change.
- `_calculate_maintenance_dates()` is shared by both first-award and maintenance-met paths. No change needed.
- This work supersedes the dual-path design documented in `CUMULATIVE_BADGE_RETENTION_FIX_COMPLETED.md` Phase 2.
- Future: If periodic badges gain reset/maintenance support, the same unified pattern should be followed (no separate midnight path).

---

## APPENDIX: Builder Implementation Specification

This section provides exact code-level detail for each change. The builder should implement these in phase order.

### A1. Exact constants reference

```python
# States (const.py)
const.CUMULATIVE_BADGE_STATE_ACTIVE    # "active"
const.CUMULATIVE_BADGE_STATE_GRACE     # "grace"
const.CUMULATIVE_BADGE_STATE_DEMOTED   # "demoted"

# Progress keys (const.py) — stored in kid_data[DATA_KID_CUMULATIVE_BADGE_PROGRESS]
const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS            # "cycle_points"
const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS                   # "status"
const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE     # "maintenance_end_date"
const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE  # "maintenance_grace_end_date"

# Badge definition keys (const.py) — from badge_data
const.DATA_BADGE_TARGET                                # "target" (dict)
const.DATA_BADGE_MAINTENANCE_RULES                     # "maintenance_rules" (float threshold, inside target)
const.DATA_BADGE_RESET_SCHEDULE                        # "reset_schedule" (dict)
const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY    # "recurring_frequency"
const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS      # "grace_period_days"
const.DATA_BADGE_INTERNAL_ID                           # "internal_id"

# Signals
const.SIGNAL_SUFFIX_BADGE_EARNED                       # emit on maintenance-met (Award Manifest)
const.SIGNAL_SUFFIX_BADGE_UPDATED                      # emit on demotion
const.SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK            # DELETE THIS (line ~226 in const.py)
```

### A2. Replace `_evaluate_cumulative_badge` already-earned branch

**File**: `custom_components/kidschores/managers/gamification_manager.py`
**Location**: Lines ~808-857 (the entire method)
**Replace with**:

```python
async def _evaluate_cumulative_badge(
    self,
    kid_id: str,
    badge_id: str,
    badge_data: BadgeData,
    context: EvaluationContext,
) -> None:
    """Evaluate cumulative badge — unified state machine.

    Handles ALL state transitions for cumulative badges:
    - NOT earned → acquisition check (total_points vs threshold)
    - EARNED → date-aware maintenance state machine:
      - No maintenance enabled → always ACTIVE, skip
      - No dates yet → initialize maintenance dates
      - Period still open (today < end_date) → skip (accumulate points)
      - Period ended + maintenance met → confirm ACTIVE, reset cycle, advance dates
      - Period ended + not met + grace available → enter GRACE
      - Period ended + not met + no grace (or grace expired) → DEMOTED
      - In GRACE + met → re-promote to ACTIVE
      - In GRACE + expired → DEMOTED

    CRITICAL: Maintenance ONLY evaluated for the highest-earned cumulative badge.
    Lower-tier earned badges are always ACTIVE — their maintenance is never checked.

    Args:
        kid_id: Kid's internal ID
        badge_id: Badge internal ID
        badge_data: Badge definition
        context: Evaluation context
    """
    kid_data = self.coordinator.kids_data.get(kid_id)
    if not kid_data:
        return

    badges_earned = kid_data.get(const.DATA_KID_BADGES_EARNED, {})
    already_earned = badge_id in badges_earned

    if not already_earned:
        # First-time acquisition: check lifetime points via engine
        badge_dict = cast("dict[str, Any]", badge_data)
        result = GamificationEngine.evaluate_badge(context, badge_dict)
        if result.get("criteria_met", False):
            await self._apply_cumulative_first_award(
                kid_id, badge_id, badge_data, result
            )
        return

    # ── ALREADY EARNED: maintenance state machine ──

    # Guard: only evaluate maintenance for the highest-earned cumulative badge
    highest_earned, _, _, _, _ = self.get_cumulative_badge_levels(kid_id)
    highest_badge_id = (
        highest_earned.get(const.DATA_BADGE_INTERNAL_ID) if highest_earned else None
    )
    if badge_id != highest_badge_id:
        return  # Lower-tier badge — always ACTIVE, skip maintenance

    # Guard: maintenance must be enabled (has frequency + threshold)
    if not self._badge_maintenance_enabled(badge_data):
        return  # No maintenance = always ACTIVE

    # Read maintenance state from cumulative_badge_progress
    progress = kid_data.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
    progress_dict = cast("dict[str, Any]", progress)
    status = progress_dict.get(
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
        const.CUMULATIVE_BADGE_STATE_ACTIVE,
    )
    end_date_str: str | None = progress_dict.get(
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
    )
    grace_end_str: str | None = progress_dict.get(
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
    )
    cycle_points = float(
        progress_dict.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0.0
        )
    )

    # Get maintenance threshold from badge target
    target = badge_data.get(const.DATA_BADGE_TARGET, {})
    maintenance_threshold = float(
        target.get(const.DATA_BADGE_MAINTENANCE_RULES, 0)
    )

    today_iso = dt_today_iso()

    # 1. First-time dates (badge earned but no maintenance dates yet)
    if not end_date_str:
        self._apply_cumulative_init_maintenance_dates(
            kid_id, badge_id, badge_data, progress_dict
        )
        return

    # 2. Maintenance period still open — just accumulate points, no action
    if today_iso < end_date_str:
        return

    # 3. Period ended (today >= end_date) — evaluate
    met = cycle_points >= maintenance_threshold

    if met:
        # Maintenance met: confirm ACTIVE, reset cycle, advance dates, emit rewards
        await self._apply_cumulative_maintenance_met(
            kid_id, badge_id, badge_data
        )
        return

    # 4. Not met — check current state for grace/demotion
    if status == const.CUMULATIVE_BADGE_STATE_GRACE:
        # In grace period — check if grace expired
        if grace_end_str and today_iso >= grace_end_str:
            self._apply_cumulative_demotion(
                kid_id, badge_id, badge_data, progress_dict,
                cycle_points, maintenance_threshold,
            )
        # else: still within grace window, do nothing
        return

    # 5. Not in grace — enter grace or demote immediately
    reset_schedule = badge_data.get(const.DATA_BADGE_RESET_SCHEDULE, {})
    grace_days = int(
        reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS, 0
        )
    )

    if grace_days > 0:
        self._apply_cumulative_enter_grace(
            kid_id, badge_id, badge_data, progress_dict,
            end_date_str, grace_days,
        )
    else:
        self._apply_cumulative_demotion(
            kid_id, badge_id, badge_data, progress_dict,
            cycle_points, maintenance_threshold,
        )
```

### A3. New method: `_apply_cumulative_init_maintenance_dates`

**File**: `custom_components/kidschores/managers/gamification_manager.py`
**Location**: Add in the "CUMULATIVE BADGE OPERATIONS" section, after `_apply_cumulative_first_award`
**Purpose**: Set initial maintenance dates for a badge that was earned but has no dates yet

```python
def _apply_cumulative_init_maintenance_dates(
    self,
    kid_id: str,
    badge_id: str,
    badge_data: BadgeData,
    progress_dict: dict[str, Any],
) -> None:
    """Initialize maintenance dates for a newly earned cumulative badge.

    Called when a badge is earned but has no maintenance_end_date yet.
    Sets the first maintenance window dates and persists.

    Args:
        kid_id: Kid's internal ID
        badge_id: Badge internal ID
        badge_data: Badge definition
        progress_dict: Mutable reference to cumulative_badge_progress
    """
    end_date, grace_end = self._calculate_maintenance_dates(badge_data)
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE] = (
        end_date
    )
    progress_dict[
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
    ] = grace_end
    self.coordinator._persist_and_update()

    kid_name = self.coordinator.kids_data.get(kid_id, {}).get(
        const.DATA_KID_NAME, kid_id
    )
    const.LOGGER.debug(
        "Initialized maintenance dates for kid '%s' badge '%s': "
        "end=%s, grace_end=%s",
        kid_name,
        badge_data.get(const.DATA_BADGE_NAME, badge_id),
        end_date,
        grace_end,
    )
```

### A4. New method: `_apply_cumulative_enter_grace`

**File**: `custom_components/kidschores/managers/gamification_manager.py`
**Location**: Add after `_apply_cumulative_init_maintenance_dates`
**Purpose**: Transition from ACTIVE/DEMOTED → GRACE state

```python
def _apply_cumulative_enter_grace(
    self,
    kid_id: str,
    badge_id: str,
    badge_data: BadgeData,
    progress_dict: dict[str, Any],
    end_date_str: str,
    grace_days: int,
) -> None:
    """Enter grace period for cumulative badge maintenance.

    Transitions status to GRACE and calculates grace_end date from
    the maintenance end_date + grace_days.

    Args:
        kid_id: Kid's internal ID
        badge_id: Badge internal ID
        badge_data: Badge definition
        progress_dict: Mutable reference to cumulative_badge_progress
        end_date_str: The maintenance end date (ISO string) grace starts from
        grace_days: Number of grace days
    """
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
        const.CUMULATIVE_BADGE_STATE_GRACE
    )
    grace_end = dt_add_interval(
        end_date_str,
        interval_unit=const.TIME_UNIT_DAYS,
        delta=grace_days,
        return_type=const.HELPER_RETURN_ISO_DATE,
    )
    progress_dict[
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
    ] = str(grace_end) if grace_end else None
    self.coordinator._persist_and_update()

    kid_name = self.coordinator.kids_data.get(kid_id, {}).get(
        const.DATA_KID_NAME, kid_id
    )
    const.LOGGER.info(
        "Kid '%s' entered grace period for badge '%s' "
        "(grace ends: %s)",
        kid_name,
        badge_data.get(const.DATA_BADGE_NAME, badge_id),
        grace_end,
    )
```

### A5. New method: `_apply_cumulative_demotion`

**File**: `custom_components/kidschores/managers/gamification_manager.py`
**Location**: Add after `_apply_cumulative_enter_grace`
**Purpose**: Demote badge, recalculate multiplier, advance dates for next cycle

```python
def _apply_cumulative_demotion(
    self,
    kid_id: str,
    badge_id: str,
    badge_data: BadgeData,
    progress_dict: dict[str, Any],
    cycle_points: float,
    maintenance_threshold: float,
) -> None:
    """Demote cumulative badge — maintenance not met.

    Sets status to DEMOTED, resets cycle_points, advances maintenance dates
    for next evaluation cycle, recalculates point multiplier, and emits
    BADGE_UPDATED signal.

    Args:
        kid_id: Kid's internal ID
        badge_id: Badge internal ID
        badge_data: Badge definition
        progress_dict: Mutable reference to cumulative_badge_progress
        cycle_points: Points earned this cycle (for logging)
        maintenance_threshold: Required threshold (for logging)
    """
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
        const.CUMULATIVE_BADGE_STATE_DEMOTED
    )
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 0.0

    # Advance dates for next cycle (so demotion evaluation starts fresh)
    end_date, grace_end = self._calculate_maintenance_dates(badge_data)
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE] = (
        end_date
    )
    progress_dict[
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
    ] = grace_end

    # Recalculate multiplier (uses next-lower badge)
    self.update_point_multiplier_for_kid(kid_id)

    self.coordinator._persist_and_update()

    kid_name = self.coordinator.kids_data.get(kid_id, {}).get(
        const.DATA_KID_NAME, kid_id
    )
    const.LOGGER.info(
        "Kid '%s' demoted from badge '%s' — "
        "maintenance not met (cycle_points=%.1f, required=%.1f)",
        kid_name,
        badge_data.get(const.DATA_BADGE_NAME, badge_id),
        cycle_points,
        maintenance_threshold,
    )

    self.emit(
        const.SIGNAL_SUFFIX_BADGE_UPDATED,
        kid_id=kid_id,
        badge_id=badge_id,
        status="demoted",
        badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
    )
```

### A6. Modify `_apply_cumulative_maintenance_met` (existing, line ~962)

**Change**: Remove the "only act if DEMOTED" guard. When maintenance is met at period end, the method should:

1. Set status=ACTIVE (regardless of current status — could be ACTIVE, GRACE, or DEMOTED)
2. Reset cycle_points=0
3. Advance maintenance dates
4. Recalculate multiplier (restores full strength if was demoted)
5. Update badges_earned tracking (calls `update_badges_earned_for_kid`)
6. Emit BADGE_EARNED signal with Award Manifest

**KEEP**: The data-corruption repair block (lines ~993-1004) for DEMOTED-when-maintenance-disabled.

**Replace entire method body** with logic that mirrors the `process_cumulative_maintenance` award_success branch (lines ~2385-2419 in the old midnight method). Key difference: no need to look up `highest_earned` — we already have `badge_data` as a parameter.

```python
async def _apply_cumulative_maintenance_met(
    self,
    kid_id: str,
    badge_id: str,
    badge_data: BadgeData,
) -> None:
    """Handle cumulative badge maintenance met — confirm ACTIVE, reset cycle.

    Called when maintenance period has ended AND cycle_points >= threshold.
    Applies regardless of current status (ACTIVE, GRACE, or DEMOTED).

    Actions:
    1. Set status = ACTIVE
    2. Reset cycle_points = 0
    3. Advance maintenance dates for next cycle
    4. Recalculate point multiplier (restores full if was DEMOTED)
    5. Update badges_earned tracking
    6. Emit BADGE_EARNED signal with Award Manifest

    Args:
        kid_id: Kid's internal ID
        badge_id: Badge internal ID
        badge_data: Badge definition
    """
    kid_data = self.coordinator.kids_data.get(kid_id)
    if not kid_data:
        return

    progress = kid_data.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
    progress_dict = cast("dict[str, Any]", progress)

    # Set ACTIVE, reset cycle
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
        const.CUMULATIVE_BADGE_STATE_ACTIVE
    )
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 0.0

    # Advance maintenance dates for next cycle
    end_date, grace_end = self._calculate_maintenance_dates(badge_data)
    progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE] = (
        end_date
    )
    progress_dict[
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
    ] = grace_end

    # Update badge tracking (period stats)
    self.update_badges_earned_for_kid(kid_id, badge_id)

    # Recalculate multiplier (restore full strength if was DEMOTED)
    self.update_point_multiplier_for_kid(kid_id)

    # Persist changes
    self.coordinator._persist_and_update()

    kid_name = eh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
    const.LOGGER.info(
        "Kid '%s' maintained badge '%s' — "
        "cycle reset, next maintenance: %s",
        kid_name,
        badge_data.get(const.DATA_BADGE_NAME, badge_id),
        end_date,
    )

    # Build and emit Award Manifest
    manifest = self._build_badge_award_manifest(badge_data)
    self.emit(
        const.SIGNAL_SUFFIX_BADGE_EARNED,
        kid_id=kid_id,
        badge_id=badge_id,
        kid_name=kid_name,
        badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
        **manifest,
    )
```

### A7. Simplify `_on_midnight_rollover` (line ~307)

**Replace**:

```python
self.process_all_kids_maintenance()
```

**With**:

```python
self.recalculate_all_badges()
```

The existing `recalculate_all_badges()` method marks all kids pending → debounce → `_evaluate_kid()` → unified `_evaluate_cumulative_badge()` handles everything.

### A8. Delete these methods entirely

1. **`process_cumulative_maintenance()`** — lines ~2218-2470 (~252 lines)
2. **`process_all_kids_maintenance()`** — lines ~2472-2485 (~14 lines)
3. **`GamificationEngine.check_cumulative_maintenance()`** — lines ~275-335 in `engines/gamification_engine.py` (~60 lines)

### A9. Delete constant

- **`SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK`** — line ~226 in `const.py`

### A10. Update engine docstring

In `engines/gamification_engine.py`, update the class-level docstring to remove `check_cumulative_maintenance` from the public API list. The engine's public API becomes just `evaluate_badge()`, `evaluate_achievement()`, `evaluate_challenge()`.

### A11. Update tests

1. **Delete** `test_cumulative_maintenance_criteria_met` and `test_cumulative_maintenance_criteria_not_met` in `tests/test_gamification_engine.py` (lines ~555-572) — they test the deleted engine method
2. **Grep** tests/ for `process_cumulative_maintenance`, `process_all_kids_maintenance`, `check_cumulative_maintenance` — update/remove any references
3. **New tests** (in `tests/test_cumulative_maintenance_unified.py` or added to existing test file):
   - Test the 9 scenarios listed in Phase 4, step 1
   - Mock `dt_today_iso()` via `patch("custom_components.kidschores.managers.gamification_manager.dt_today_iso")`
   - Use `scenario_medium` fixtures

### A12. Imports check

In `gamification_manager.py`, verify that `dt_today_iso` and `dt_add_interval` are imported from `utils.dt_utils`. The existing `_evaluate_cumulative_badge` doesn't currently use them — the new version will. Check the import block at the top of the file. Also verify `const.TIME_UNIT_DAYS` and `const.HELPER_RETURN_ISO_DATE` are available (they should be — used by `_calculate_maintenance_dates` already).

### A13. Execution order for builder

1. Phase 1 steps 1-6 (modify `_evaluate_cumulative_badge`, add 3 new methods, modify `_apply_cumulative_maintenance_met`, add guard)
2. Phase 2 steps 1-5 (simplify midnight, delete old methods, delete constant)
3. Phase 3 steps 1-3 (delete engine method, update docstring)
4. Run `./utils/quick_lint.sh --fix` — fix any lint issues
5. Run `mypy custom_components/kidschores/` — fix any type issues
6. Phase 4 steps 1-4 (update/create tests, run full suite)
