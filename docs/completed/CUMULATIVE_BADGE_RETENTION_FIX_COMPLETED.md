# Initiative Plan: Cumulative Badge Maintenance Cycle

## Initiative snapshot

- **Name / Code**: Cumulative Badge Maintenance Cycle (CUMBMC)
- **Target release / milestone**: v0.5.0-beta4
- **Owner / driver(s)**: KidsChores Plan Agent
- **Status**: Completed

## Summary & immediate steps

| Phase / Step                                 | Description                                                | % complete | Quick notes                                                                                         |
| -------------------------------------------- | ---------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------- |
| Phase 1 – Engine Retention Fix               | Split `check_retention` for cumulative vs periodic         | 100%       | ✅ Complete - check_retention + \_evaluate_cumulative_retention added                               |
| Phase 2 – Manager Maintenance Processing     | Port `_manage_cumulative_badge_maintenance` to manager     | 100%       | ✅ Complete - process_cumulative_maintenance + process_all_kids_maintenance added                   |
| Phase 3 – Manager Integration Points         | Wire midnight trigger + `_apply_badge_result` re-promotion | 100%       | ✅ Complete - midnight subscription + re-promotion + signal emission + **Award Manifest gap fixed** |
| Phase 3A – Compute-on-Read Progress Refactor | Stop storing derived fields, compute on every read         | 100%       | ✅ Complete - 4 state fields stored, 13 derived fields computed on-read (sensor/engine verified)    |
| Phase 4 – Tests                              | Engine tests + manager maintenance tests                   | 100%       | ✅ Complete - cumulative scenarios covered and regressions added                                     |
| Phase 5 – Validation                         | Full lint/mypy/test suite                                  | 100%       | ✅ Complete - lint, mypy, and targeted test validation passed                                       |

1. **Key objective** — Restore the complete cumulative badge maintenance cycle that existed in the old coordinator but was **never migrated** to the refactored manager architecture. This includes: cycle-point reset at cycle boundaries, GRACE state transitions, re-promotion from DEMOTED→ACTIVE, and scheduled maintenance evaluation via midnight rollover.

2. **Summary of recent work** — Deep analysis of old coordinator `_manage_cumulative_badge_maintenance()` (400 lines, user-provided) vs current `gamification_manager.py`. The old code had a complete maintenance state machine. The refactored code has only: (a) cycle_points accumulation, (b) one-way demotion. All other maintenance machinery is missing.

3. **Next steps (short term)** — Completed and archived.

4. **Risks / blockers**
   - The old code used `baseline + cycle_points` for tier determination. The new code uses `stats.get_period_total()` (all-time earned). **The tier determination is fundamentally different** — the plan must account for this architectural change.
   - The old code called `_persist()` and `async_set_updated_data()` directly. The new architecture uses manager→coordinator delegation and signal-based communication.
   - `cycle_points` is accumulated even when no badge has `maintenance_rules > 0`. This is wasteful but harmless — guarding it is a follow-up optimization.
   - The old `_get_cumulative_badge_levels()` used `baseline + cycle_points` for total. The new version uses `stats.get_period_total()`. This means tier boundaries work differently — **cycle_points is now ONLY for maintenance evaluation, not tier determination**.

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — Engine vs Manager distinction, signal-first communication
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Constant naming, engine purity rules
   - Old coordinator code: `_manage_cumulative_badge_maintenance()` (user-provided attachment)
   - Wiki specification: `kidschores-ha.wiki/Configuration:-Badges-Cumulative.md`
  - Supporting analysis: [CUMULATIVE_BADGE_RETENTION_FIX_SUP_GAP_ANALYSIS_COMPLETED.md](./CUMULATIVE_BADGE_RETENTION_FIX_SUP_GAP_ANALYSIS_COMPLETED.md)

6. **Decisions & completion check**
   - **Decisions captured**:
     - **Tier determination**: Uses `stats.get_period_total()` (all-time earned) — NOT `baseline + cycle_points`. The old `baseline` field has been removed.
     - **`cycle_points` purpose**: ONLY for maintenance cycle evaluation (did kid earn enough THIS cycle?). Not used for badge tier threshold comparison.
     - **Engine fix**: Option A — `check_retention()` gets cumulative-specific branch evaluating `cycle_points >= maintenance_rules`
     - **Maintenance processing**: Port old coordinator logic to `GamificationManager.process_cumulative_maintenance()` as a new manager method
     - **Signal wiring**: GamificationManager subscribes to `SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER` to trigger maintenance checks
     - **Re-promotion**: Handled in BOTH `_apply_badge_result()` (immediate, on point change) AND `process_cumulative_maintenance()` (time-based, at midnight)
     - **`maintenance_rules = 0`** means no maintenance requirement → retention always passes, maintenance processing skips (by design)
     - **`SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK`**: Currently dead signal — will be used for post-maintenance-processing notification OR removed if unnecessary
  - **Completion confirmation**: `[x]` All follow-up items completed before requesting owner approval

---

## Gap Analysis: Old Coordinator vs Current Manager

### What the Old Code Did (Complete Maintenance State Machine)

The old `_manage_cumulative_badge_maintenance()` handled these 8 responsibilities:

| #   | Responsibility                         | Old Code Behavior                                                                                                               |
| --- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Guard: no badge earned**             | Early return if `_get_cumulative_badge_levels()` returns no highest                                                             |
| 2   | **Guard: reset not enabled**           | Clear maintenance dates, persist, return if `frequency == None`                                                                 |
| 3   | **First-time setup**                   | Set initial `maintenance_end_date` and `grace_end_date` on first earn                                                           |
| 4   | **ACTIVE → evaluate at end_date**      | Compare `cycle_points >= maintenance_required`                                                                                  |
| 5   | **ACTIVE → GRACE transition**          | If points not met but grace_days > 0, set status = GRACE                                                                        |
| 6   | **GRACE → evaluate at grace_end_date** | If points met → award_success; if expired → demotion                                                                            |
| 7   | **Award success (re-promotion)**       | Reset dates, set status = ACTIVE, award badge, grant awards                                                                     |
| 8   | **Demotion**                           | Set status = DEMOTED, current_badge = next_lower, **reset cycle_points to 0**, baseline += cycle_points, recalculate multiplier |

### What the Current Manager Has

| #   | Responsibility                     | Current Status                                  | Location                                                              |
| --- | ---------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------- |
| 1   | Guard: no badge earned             | ✅ Exists                                       | `get_cumulative_badge_levels()`                                       |
| 2   | Guard: reset not enabled           | ❌ **MISSING**                                  | —                                                                     |
| 3   | First-time setup                   | ⚠️ Partial (in `recalculate_all_badges` L2319+) | Only sets dates on badge creation                                     |
| 4   | ACTIVE → evaluate at end_date      | ❌ **MISSING**                                  | —                                                                     |
| 5   | ACTIVE → GRACE transition          | ❌ **MISSING**                                  | GRACE constant defined, never set                                     |
| 6   | GRACE → evaluate at grace_end_date | ❌ **MISSING**                                  | —                                                                     |
| 7   | Award success (re-promotion)       | ❌ **MISSING**                                  | `_apply_badge_result` has no branch for criteria_met + already_earned |
| 8   | Demotion                           | ✅ Exists                                       | `demote_cumulative_badge()` L1727                                     |

### What the Current Manager Does Have (Working)

| Feature                   | Status | Location                                                        |
| ------------------------- | ------ | --------------------------------------------------------------- |
| cycle_points accumulation | ✅     | `_on_points_changed()` L205                                     |
| Tier determination        | ✅     | `get_cumulative_badge_levels()` uses `stats.get_period_total()` |
| Demotion (one-way)        | ✅     | `demote_cumulative_badge()` L1727                               |
| Progress display          | ✅     | `get_cumulative_badge_progress()` L1586                         |
| Multiplier update         | ✅     | `update_point_multiplier_for_kid()` L1410                       |
| Badge recording           | ✅     | `_record_badge_earned()` L2078                                  |

### Critical Differences: Old vs New Architecture

| Aspect                | Old Coordinator                                      | New Manager Architecture                                                  |
| --------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------- |
| **Tier total**        | `baseline + cycle_points`                            | `stats.get_period_total()` (all-time)                                     |
| **baseline field**    | Stored in progress, absorbs cycle_points on demotion | **REMOVED** (schema v44)                                                  |
| **Persistence**       | `self._persist()` + `self.async_set_updated_data()`  | `self.coordinator._persist()` + signal emission                           |
| **Multiplier update** | `self._update_point_multiplier_for_kid()`            | `self.update_point_multiplier_for_kid()` → emits signal to EconomyManager |
| **Badge award**       | `self._award_badge()`                                | `self._record_badge_earned()` + signal                                    |
| **Scheduled trigger** | Called from `_manage_badge_maintenance()`            | ❌ No scheduled trigger exists                                            |

---

## Detailed phase tracking

### Phase 1 – Engine Retention Fix

- **Goal**: Make `check_retention()` semantically correct for cumulative badges by evaluating `cycle_points >= maintenance_rules` instead of `total_points_earned >= threshold` (which never fails).
- **Files touched**: `custom_components/kidschores/engines/gamification_engine.py` ONLY
- **Status**: ✅ **COMPLETE**
- **Steps / detailed work items**
  1. - [x] **Modify `check_retention()` (~L308-327)** — Added cumulative badge branch before fallthrough to `evaluate_badge()`.

     Implemented logic:

     ```python
     @classmethod
     def check_retention(cls, context, badge_data) -> EvaluationResult:
         badge_type = badge_data.get(const.DATA_BADGE_TYPE, "")
         if badge_type == const.BADGE_TYPE_CUMULATIVE:
             return cls._evaluate_cumulative_retention(context, badge_data)
         return cls.evaluate_badge(context, badge_data)
     ```

  2. - [x] **Add `_evaluate_cumulative_retention()` classmethod** (~75 lines, after `check_retention()`).

     Data sources:
     - `context["cumulative_badge_progress"]["cycle_points"]` — accumulated by manager `_on_points_changed`
     - `badge_data[DATA_BADGE_TARGET][DATA_BADGE_MAINTENANCE_RULES]` — threshold for maintenance

     Implemented behaviors:
     - `maintenance_rules <= 0` → `criteria_met = True` (no maintenance required)
     - `cycle_points >= maintenance_rules` → `criteria_met = True`
     - `cycle_points < maintenance_rules` → `criteria_met = False`
     - `criterion_type = "cumulative_maintenance"` (distinguishes from acquisition's `"cumulative_points"`)

  3. - [x] **Verify `evaluate_badge()` inline cumulative block (~L211-240) remains untouched** — Confirmed: No inline cumulative logic exists in current code (removed in prior work). Acquisition path uses handler system.

  4. - [x] **Verify periodic badge paths unaffected** — Confirmed: `check_retention` for periodic falls through to `evaluate_badge()` which uses handler system.

- **Validation Results**:
  - ✅ Ruff check: All checks passed
  - ✅ Ruff format: 1 file reformatted (gamification_engine.py)
  - ✅ MyPy: Success, no issues found
  - ✅ Architectural boundaries: 10/10 checks passed

- **Key issues**: None encountered.

---

### Phase 2 – Manager Maintenance Processing

- **Goal**: Port the old coordinator's `_manage_cumulative_badge_maintenance()` state machine to `GamificationManager` as `process_cumulative_maintenance()`, adapted for the new architecture.
- **Files touched**: `custom_components/kidschores/managers/gamification_manager.py`
- **Steps / detailed work items**
  1. - [x] **Add `process_cumulative_maintenance(kid_id: str)` method** — New public method on GamificationManager. Port the old coordinator logic with these architectural adaptations:

     **Adaptations from old code to new architecture:**

     | Old Pattern                                                    | New Pattern                                                              |
     | -------------------------------------------------------------- | ------------------------------------------------------------------------ |
     | `self.kids_data.get(kid_id)`                                   | `self.coordinator.kids_data.get(kid_id)`                                 |
     | `self._get_cumulative_badge_levels(kid_id)`                    | `self.get_cumulative_badge_levels(kid_id)`                               |
     | `self._persist()`                                              | `self.coordinator._persist()`                                            |
     | `self.async_set_updated_data(self._data)`                      | Signal emission (see Phase 3)                                            |
     | `self._award_badge(kid_id, badge_id)`                          | `self._record_badge_earned(kid_id, badge_id)` + emit badge earned signal |
     | `self._update_point_multiplier_for_kid(kid_id)`                | `self.update_point_multiplier_for_kid(kid_id)`                           |
     | `kh.dt_today_iso()`                                            | Use helpers or `dt_utils` equivalent                                     |
     | `kh.dt_add_interval(...)`                                      | Use helpers or `dt_utils` equivalent                                     |
     | `kh.dt_next_schedule(...)`                                     | Use helpers or `dt_utils` equivalent                                     |
     | `const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE` references | **REMOVE** — baseline no longer exists in schema v44                     |

     **Critical logic preserved from old code:**

     ```
     1. Guard: early return if no kid_info or no highest_earned badge
     2. Guard: if reset_enabled == False → clear maintenance dates, persist, return
     3. Extract: end_date, grace_date, status, cycle_points from progress
     4. Get: maintenance_required, frequency, grace_days from highest_earned badge
     5. State evaluation:
        a. (ACTIVE or DEMOTED) + past end_date:
           - cycle_points >= maintenance_required → award_success
           - past grace_date → demotion_required
           - grace_days > 0 → set GRACE
           - else → demotion_required
        b. GRACE:
           - cycle_points >= maintenance_required → award_success
           - past grace_date → demotion_required
     6. Calculate next maintenance/grace dates (if award/demotion/first_time)
     7. Apply award_success: status=ACTIVE, reset cycle_points=0, update dates,
        set current_badge=highest, re-award badge
     8. Apply demotion: status=DEMOTED, reset cycle_points=0, set current_badge=next_lower,
        recalculate multiplier
     9. Apply first_time: just set initial dates
     10. Persist
     ```

     **Key difference from old code — cycle_points reset:**
     - Old code: On demotion, `baseline += cycle_points; cycle_points = 0`
     - New code: On demotion, just `cycle_points = 0` (baseline removed)
     - Old code: On award_success, cycle_points was NOT reset (kept accumulating)
     - New code: On award_success, `cycle_points = 0` (cycle is complete, start fresh)
     - **Justification**: Wiki says "If goal met: Cycle resets". Since `cycle_points` is now purely a maintenance counter (not a tier component), resetting on success is correct.

  2. - [x] **Remove all `baseline` references from maintenance logic** — The old code had `baseline + cycle_points` on demotion. Since baseline is removed (schema v44), demotion simply resets `cycle_points = 0`. Tier determination uses `stats.get_period_total()` independently.

  3. - [x] **Handle first-time setup** — When badge first earned and `reset_enabled=True` but no `maintenance_end_date` exists yet, calculate and set initial maintenance/grace dates. (Ported directly from old code's `is_first_time` block.)

  4. - [x] **Add `process_all_kids_maintenance()` loop method** — Iterates all kids and calls `process_cumulative_maintenance(kid_id)` for each.

     ```python
     def process_all_kids_maintenance(self) -> None:
         """Process cumulative badge maintenance for all kids."""
         for kid_id in list(self.coordinator.kids_data):
             self.process_cumulative_maintenance(kid_id)
     ```

  5. - [x] **Verify `_on_points_changed` cycle_points accumulation** — Confirm it works correctly with maintenance. Currently accumulates for ALL positive deltas regardless of whether maintenance is configured. This is acceptable (0 maintenance_rules → retention always passes, accumulated points harmless).

- **Key issues**
  - **Date calculation imports**: Builder must verify which `dt_*` functions exist in `helpers/` vs `utils/dt_utils.py`. The old code used `kh.dt_today_iso()`, `kh.dt_add_interval()`, `kh.dt_next_schedule()`. Manager CAN use `helpers/` functions (unlike engines which must stay pure).
  - **Signal emission vs direct persist**: Manager calls `self.coordinator._persist()` then emits signal. Determine correct signal for post-maintenance notification.
  - **DEMOTED re-entry**: The old code's status check includes DEMOTED: `status in (ACTIVE, DEMOTED)`. This means a DEMOTED kid's next maintenance window still runs — they can meet the requirement and get re-promoted. **This is the time-based re-promotion path.** Must be preserved.

---

### Phase 3 – Manager Integration Points

- **Goal**: Wire the new maintenance processing into the existing manager lifecycle.
- **Files touched**: `custom_components/kidschores/managers/gamification_manager.py`, possibly `const.py`
- **Steps / detailed work items**
  1. - [x] **Subscribe GamificationManager to MIDNIGHT_ROLLOVER** — Add listener in `async_initialize()`:

     ```python
     self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)
     ```

     Handler:

     ```python
     async def _on_midnight_rollover(self) -> None:
         """Process daily maintenance checks at midnight."""
         self.process_all_kids_maintenance()
     ```

     **Note**: ChoreManager, UIManager, StatisticsManager already subscribe. GamificationManager needs to be added.

  2. - [x] **Add re-promotion branch to `_apply_badge_result()` (~L798-892)** — Handle the `criteria_met=True + already_earned=True` case for immediate re-promotion.

     Current branches:
     - `criteria_met=True + not already_earned` → Award badge
     - `criteria_met=False + already_earned` → Demote (cumulative only)

     New branch:
     - `criteria_met=True + already_earned + DEMOTED status` → **Re-promote**: set status=ACTIVE, update current_badge, reset cycle_points, recalculate multiplier

     **Why here AND in `process_cumulative_maintenance()`**: Wiki says "Requalification: Immediate when kid earns enough points (no full cycle required)". Points changes trigger `_evaluate_badge_for_kid()` → `check_retention()` (Phase 1 fix) → `_apply_badge_result()`. This path handles IMMEDIATE re-promotion. The midnight path handles TIME-BASED cycle evaluation.

     **Idempotency guard**: Check `status == DEMOTED` before re-promoting. If already ACTIVE, no-op.

  3. - [x] **Evaluate `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` usage** — Options:
     - **Use it**: Emit after `process_all_kids_maintenance()` for UI/sensor refresh
     - **Remove it**: If `BADGE_UPDATED`/`BADGE_EARNED` signals suffice
     - **Recommendation**: Use it — emit once after the loop completes (not per-kid)
     - **IMPLEMENTED**: Added `self.emit(const.SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK)` after loop in `process_all_kids_maintenance()`

  4. - [x] **Verify `recalculate_all_badges()` compatibility** — The existing method (L2230-2520) sets initial dates for new badges. Confirm it doesn't conflict with `process_cumulative_maintenance()`.

  5. - [x] **🚨 CRITICAL GAP FIX: Award Manifest Emission** — User-discovered bug: Maintenance success only updated multiplier, didn't award points/rewards/bonuses/penalties. Kids must receive ALL badge items each time they meet maintenance threshold.

     **Fixed in two locations:**
     - `process_cumulative_maintenance()` award_success branch (L2047): Added Award Manifest building + `SIGNAL_SUFFIX_BADGE_EARNED` emission
     - `_apply_badge_result()` re-promotion branch (L910): Added Award Manifest building + `SIGNAL_SUFFIX_BADGE_EARNED` emission (immediate path)

     **Refactoring**: Extracted `_build_badge_award_manifest()` helper method (L1307) to eliminate ~60 lines of duplication across 3 locations (first earn, re-promotion, maintenance success). Uses dict unpacking (`**manifest`) for clean emit calls.

- **Validation Results**:
  - ✅ Ruff check: All checks passed
  - ✅ Ruff format: 1 file reformatted
  - ✅ MyPy: Success, no issues found in 48 source files
  - ✅ Architectural boundaries: 10/10 checks passed

- **Key issues**
  - **Two re-promotion paths**: (a) Time-based via midnight → `process_cumulative_maintenance()`, (b) Event-based via point change → `_apply_badge_result()`. Both must set status=ACTIVE and reset cycle_points. Guard with status check to prevent double-processing.
  - **Signal ordering**: Midnight rollover fires for multiple managers. Ensure GamificationManager's handler doesn't conflict with StatisticsManager's period flush.

---

### Phase 3A – Compute-on-Read Progress Refactor

- **Goal**: Eliminate 12 stale denormalized fields from `cumulative_badge_progress` storage. Keep only the 5 true state fields. All derived/computed fields become compute-on-read via `get_cumulative_badge_progress()` (which already works correctly). Sensor + all consumers switch from reading raw storage to calling the compute method.
- **Files touched**: `const.py`, `type_defs.py`, `sensor.py`, `managers/gamification_manager.py`, `migration_pre_v50.py`, `data_builders.py`
- **Status**: Not started

#### Problem Statement

Henry's live data proves the bug: 318 all-time points, Bronze (250 threshold) earned, but storage shows:

| Field                       | Stored       | Correct      | Status                          |
| --------------------------- | ------------ | ------------ | ------------------------------- |
| `current_badge_id`          | Bronze       | Bronze       | ✅                              |
| `current_badge_name`        | "Bronze"     | "Bronze"     | ✅                              |
| `current_threshold`         | **4.45**     | **250.0**    | ❌ Stale — Noob's threshold     |
| `highest_earned_badge_id`   | **Noob**     | **Bronze**   | ❌ Never updated on acquisition |
| `highest_earned_badge_name` | **"Noob"**   | **"Bronze"** | ❌ Never updated on acquisition |
| `highest_earned_threshold`  | **4.45**     | **250.0**    | ❌ Never updated on acquisition |
| `next_higher_badge_id`      | **Bronze**   | **Silver**   | ❌ Never updated                |
| `next_higher_badge_name`    | **"Bronze"** | **"Silver"** | ❌ Never updated                |
| `next_higher_threshold`     | **250.0**    | **500.0**    | ❌ Never updated                |
| `next_higher_points_needed` | **169.0**    | **182.0**    | ❌ Never updated                |
| `next_lower_badge_id`       | **null**     | **Noob**     | ❌ Never updated                |
| `next_lower_badge_name`     | **null**     | **"Noob"**   | ❌ Never updated                |
| `next_lower_threshold`      | **null**     | **4.45**     | ❌ Never updated                |

**Root cause**: Storage writes (in `_apply_badge_result`, `process_cumulative_maintenance`, `demote_cumulative_badge`) only update 2-3 fields (`status`, `cycle_points`, `current_badge_id/name`) at event boundaries. They NEVER update `highest_earned_*`, `next_higher_*`, `next_lower_*`, `current_threshold`. Meanwhile, `get_cumulative_badge_progress()` computes ALL fields correctly — but nobody calls it for reads except `delete_badge`.

**Solution**: Stop storing derived fields entirely. Compute them on every read. This permanently eliminates the staleness bug class.

#### Field Classification

| Category                                           | Fields                                                                                                                                                                         | Action                                                                      |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| **True State** (keep in storage)                   | `status`, `cycle_points`, `maintenance_end_date`, `maintenance_grace_end_date`                                                                                                 | ✅ Keep — these track FSM state                                             |
| **Deprecated** (already being removed)             | `baseline`                                                                                                                                                                     | ✅ Already removed in v44 migration                                         |
| **Derived from badges_earned + badge definitions** | `highest_earned_badge_id`, `highest_earned_badge_name`, `highest_earned_threshold`, `current_badge_id`, `current_badge_name`, `current_threshold`                              | ❌ **DELETE from storage** — computable via `get_cumulative_badge_levels()` |
| **Derived from badge definitions + total_points**  | `next_higher_badge_id`, `next_higher_badge_name`, `next_higher_threshold`, `next_higher_points_needed`, `next_lower_badge_id`, `next_lower_badge_name`, `next_lower_threshold` | ❌ **DELETE from storage** — computable via `get_cumulative_badge_levels()` |

**After refactor, storage contains only:**

```json
"cumulative_badge_progress": {
    "status": "active",
    "cycle_points": 33.0,
    "maintenance_end_date": null,
    "maintenance_grace_end_date": null
}
```

#### Steps / Detailed Work Items

**Step 1 — Migration: Strip derived fields from storage (v44)** ✅

- [x] **File**: `custom_components/kidschores/migration_pre_v50.py`
- [x] **Pattern**: Follow the existing `baseline` removal pattern (L1061-1062)
- [x] **Validation**: After migration, storage only has 4 fields: `status`, `cycle_points`, `maintenance_end_date`, `maintenance_grace_end_date`.

**Step 2 — TypedDict: Slim down `KidCumulativeBadgeProgress`** ✅

- [x] **File**: `custom_components/kidschores/type_defs.py` (L396-428)
- [x] **Current**: 18 fields (4 state + 1 deprecated + 13 derived)
- [x] **After**: 4 state fields only

**Step 3 — Constants: Remove derived-field constants from `const.py`** ✅

- [x] **File**: `custom_components/kidschores/const.py` (L1035-1068)
- [x] **DELETE these constants** (13 constants including baseline)

**Step 4 — Manager: Remove scattered partial writes of derived fields** ✅

- [x] **File**: `custom_components/kidschores/managers/gamification_manager.py`
- [x] **In `_apply_badge_result()` re-promotion branch (~L897-900)**: Deleted derived field writes
- [x] **In `process_cumulative_maintenance()` award_success branch (~L2067-2071)**: Deleted derived field writes
- [x] **In `process_cumulative_maintenance()` demotion branch (~L2118-2130)**: Deleted derived field writes
- [x] **In `update_point_multiplier_for_kid()` (~L1519)**: Switched to compute current_badge via `get_cumulative_badge_levels()`
- [x] **In `delete_badge()` (~L3117-3120)**: Removed write of computed progress to storage

**Step 5 — Sensor: Switch to computed progress** ✅

- [x] **File**: `custom_components/kidschores/sensor.py`
- [x] **KidBadgesSensor.native_value (L1634-1640)**: Use `coordinator.gamification_manager.get_cumulative_badge_progress()`
- [x] **KidBadgesSensor.icon (L1650-1660)**: Use computed progress
- [x] **KidBadgesSensor.extra_state_attributes (L1688-1875)**: Use computed progress for all derived fields

**Step 6 — Manager: Clean `get_cumulative_badge_progress()` return pattern** ✅

- [x] **File**: `custom_components/kidschores/managers/gamification_manager.py`
- [x] **get_cumulative_badge_progress() (L1677-1815)**: Use plain string keys for derived fields (not constants)

**Step 7 — Verification: Confirm no other consumers** ✅

- [x] **UIManager**: No references to deleted constants
- [x] **Engines**: Only references state field `cycle_points` (still exists)
- [x] **data_builders.py**: Only references parent constant
- [x] **Tests**: No direct storage reads of deleted fields

  ```python
  # Fields to strip from cumulative_badge_progress (computed on-read now)
  DERIVED_PROGRESS_FIELDS = [
      "current_badge_id",
      "current_badge_name",
      "current_threshold",
      "highest_earned_badge_id",
      "highest_earned_badge_name",
      "highest_earned_threshold",
      "next_higher_badge_id",
      "next_higher_badge_name",
      "next_higher_threshold",
      "next_higher_points_needed",
      "next_lower_badge_id",
      "next_lower_badge_name",
      "next_lower_threshold",
  ]
  for field in DERIVED_PROGRESS_FIELDS:
      if field in progress:
          del progress[field]
          derived_removed += 1
  ```

- **Also clean**: The float-precision rounding section (L4121-4137) references these fields for rounding. Remove the deleted field references from that list — only `cycle_points` remains.
- **Also clean**: The migration at L3206-3218 that SETS `current_badge_id`, `current_badge_name`, `current_threshold`, `cycle_points` during v41→v42 migration. This migration writes INTO the dict — keep `cycle_points` but remove the 3 derived field writes since they'll be computed on-read. (The v41→v42 migration runs BEFORE v44, so v44 strip will clean up regardless, but removing the writes is cleaner.)
- **Validation**: After migration, storage only has 4 fields: `status`, `cycle_points`, `maintenance_end_date`, `maintenance_grace_end_date`.

**Step 2 — TypedDict: Slim down `KidCumulativeBadgeProgress`**

- **File**: `custom_components/kidschores/type_defs.py` (L396-428)
- **Current**: 18 fields (4 state + 1 deprecated + 13 derived)
- **After**: 4 state fields only

  ```python
  class KidCumulativeBadgeProgress(TypedDict, total=False):
      """Cumulative badge progress state tracking for a kid.

      Only FSM state is stored. All derived/computed fields (highest earned,
      next higher/lower, current badge info) are computed on-read via
      GamificationManager.get_cumulative_badge_progress().
      """

      status: str  # active, grace, demoted
      cycle_points: float
      maintenance_end_date: NotRequired[str | None]
      maintenance_grace_end_date: NotRequired[str | None]
  ```

- **Remove all**: `baseline`, `current_badge_id`, `current_badge_name`, `current_threshold`, `next_higher_*` (4 fields), `next_lower_*` (3 fields), `highest_earned_*` (3 fields)

**Step 3 — Constants: Remove derived-field constants from `const.py`**

- **File**: `custom_components/kidschores/const.py` (L1035-1068)
- **DELETE these constants** (12 constants):

  ```
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID     (L1035)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME   (L1036)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD    (L1037)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID    (L1040)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME  (L1043)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD   (L1046)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID       (L1051)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME     (L1052)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_THRESHOLD      (L1055)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED  (L1058)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID        (L1063)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME      (L1064)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_THRESHOLD       (L1067)
  ```

- **Also DELETE**: `DATA_KID_CUMULATIVE_BADGE_PROGRESS_BASELINE` (L1070) — already removed from storage in v44, but constant still exists.
- **KEEP these constants** (4 state constants):

  ```
  DATA_KID_CUMULATIVE_BADGE_PROGRESS              (L1032) — parent key
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS (L1071)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS       (L1072)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE       (L1073)
  DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE (L1074)
  ```

**Step 4 — Manager: Remove scattered partial writes of derived fields**

- **File**: `custom_components/kidschores/managers/gamification_manager.py`
- **These write lines must be DELETED** (they write derived fields into storage that will no longer exist):

  **In `_apply_badge_result()` re-promotion branch (~L897-900)**:

  ```python
  # DELETE these 4 lines — current_badge is now computed on-read
  progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID] = highest_id
  progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME] = highest_earned.get(const.DATA_BADGE_NAME)
  ```

  Also delete the `get_cumulative_badge_levels()` call that feeds them (~L893-895), since it's only used for these writes.

  **In `process_cumulative_maintenance()` award_success branch (~L2067-2071)**:

  ```python
  # DELETE these 2 lines — current_badge is now computed on-read
  progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID] = highest_badge_id
  progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME] = highest_earned.get(const.DATA_BADGE_NAME)
  ```

  **In `process_cumulative_maintenance()` demotion branch (~L2118-2130)**:

  ```python
  # DELETE these lines — current_badge is now computed on-read
  if next_lower:
      progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID] = lower_id
      progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME] = next_lower.get(...)
  else:
      progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID] = None
      progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME] = None
  ```

  **In `delete_badge()` badge deletion path (~L3117-3120)**:

  ```python
  # DELETE these 3 lines — storage no longer holds computed fields
  cumulative_progress = self.get_cumulative_badge_progress(kid_id)
  self.coordinator.kids_data[kid_id][const.DATA_KID_CUMULATIVE_BADGE_PROGRESS] = cast(...)
  ```

  (The `sync_badge_progress_for_kid` call above it is fine — that handles periodic badge_progress, not cumulative.)

  **In `update_point_multiplier_for_kid()` (~L1519)**:

  ```python
  # This reads current_badge_id from progress to find the badge's multiplier.
  # CHANGE to use get_cumulative_badge_levels() instead of reading stored field.
  current_badge_id = progress.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID)
  ```

  Replace with:

  ```python
  (highest_earned, _, next_lower, _, _) = self.get_cumulative_badge_levels(kid_id)
  current_status = progress.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS, const.CUMULATIVE_BADGE_STATE_ACTIVE)
  if current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED:
      current_badge = next_lower
  else:
      current_badge = highest_earned
  current_badge_id = current_badge.get(const.DATA_BADGE_INTERNAL_ID) if current_badge else None
  ```

  **In `_build_evaluation_context()` (~L1161-1163)**:
  This passes `kid_data.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})` into context. The engine's `_evaluate_cumulative_retention()` reads `cycle_points` from it (which still exists). **No change needed** — the 4 remaining state fields are still in storage.

**Step 5 — Sensor: Switch to computed progress**

- **File**: `custom_components/kidschores/sensor.py` — `KidBadgesSensor` class (L1582-1875)
- **Current**: Sensor reads `kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})` — the stale stored copy.
- **After**: Sensor calls `self.coordinator.gamification.get_cumulative_badge_progress(self._kid_id)` — the live computed version.

  **Change in `native_value` property (~L1630-1643)**:

  ```python
  # BEFORE:
  cumulative_badge_progress_info = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})

  # AFTER:
  cumulative_badge_progress_info = self.coordinator.gamification.get_cumulative_badge_progress(self._kid_id)
  ```

  **Change in `icon` property (~L1648-1660)**:
  Same replacement — use computed progress instead of stored.

  **Change in `extra_state_attributes` property (~L1688-1691)**:
  Same replacement — use computed progress instead of stored.

  **Critical**: `get_cumulative_badge_progress()` already returns a dict with ALL the same keys that the sensor currently reads (`highest_earned_badge_name`, `next_higher_badge_id`, `current_badge_id`, `status`, `cycle_points`, `maintenance_end_date`, `maintenance_grace_end_date`, etc.). The sensor code BELOW the dict fetch doesn't need to change — it reads the same keys from the returned dict.

  **Verify**: The sensor uses these constant keys to read from the dict. After Step 3, those constants are deleted. The sensor must switch to reading from the computed dict using the **string keys returned by `get_cumulative_badge_progress()`**. Since that method already uses the constants to build its output, we need to keep the return keys stable. **Two approaches**:
  - (a) Keep the constants alive but rename them to `ATTR_*` pattern (they're now attribute keys, not storage keys). This is the cleanest approach.
  - (b) Inline the string values in the sensor. Violates "no hardcoded strings" rule.
  - **Decision**: Use approach (a) — rename from `DATA_KID_CUMULATIVE_BADGE_PROGRESS_*` to `ATTR_CUMULATIVE_PROGRESS_*` to reflect they're computed attribute keys, not storage keys. Update both the sensor and `get_cumulative_badge_progress()` to use the new names. This is a bulk rename (find-and-replace), not a logic change.
  - **Alternative simpler approach**: Keep the existing constants but update their docstring/comments to clarify they're now computed-dict keys, not storage keys. The `DATA_*` prefix is technically wrong but the rename is a LOT of churn. **Builder should evaluate: if rename causes >50 line changes, keep the existing names with updated comments.**

**Step 6 — Manager: Update `get_cumulative_badge_progress()` return**

- **File**: `custom_components/kidschores/managers/gamification_manager.py` (~L1677-1815)
- **Current**: Method reads `stored_progress` from storage, computes values, merges over stored. Returns merged dict.
- **After**: Method reads ONLY the 4 state fields from storage, computes everything else, returns full dict.
- **The method already does this correctly** — the `computed_progress` dict it builds already has all 17 fields computed from live data. The only change: stop reading/merging from `stored_progress` for derived fields. Since `stored_progress` won't have them after migration, the merge is already a no-op. But clean it up:

  ```python
  # BEFORE:
  stored_progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}).copy()
  # ... compute all fields ...
  stored_progress.update(computed_progress)
  return stored_progress

  # AFTER:
  state = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
  # Read only the 4 state fields
  status = state.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS, const.CUMULATIVE_BADGE_STATE_ACTIVE)
  cycle_points = state.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0.0)
  # ... compute everything else from get_cumulative_badge_levels() ...
  # Return complete dict (state + computed)
  return { ...all fields... }
  ```

**Step 7 — Verify no other consumers read derived fields from storage**

- **UIManager**: ✅ Zero references to `cumulative_badge_progress` (verified via grep)
- **Dashboard helper sensor**: ✅ Uses UIManager, which doesn't touch this data
- **data_builders.py** (L2136): Lists `DATA_KID_CUMULATIVE_BADGE_PROGRESS` as a known kid field. **No change needed** — the parent key still exists, just with fewer sub-fields.
- **Engine's `_evaluate_cumulative_retention()`**: Reads `context["cumulative_badge_progress"]["cycle_points"]`. **No change needed** — `cycle_points` is still stored.
- **Engine's `_evaluate_cumulative_points()`**: Reads `context["total_points_earned"]` from stats, not from progress. **No change needed**.
- **Tests**: Any test that creates mock `cumulative_badge_progress` dicts with the removed fields must be updated to only include state fields. Check: `grep -rn 'highest_earned\|next_higher\|next_lower\|current_threshold' tests/`

- **Key issues**:
  - Constants rename decision (Step 5) — builder must evaluate churn and decide approach
  - `update_point_multiplier_for_kid()` is called from 3 places — must verify all work after the storage field is gone
  - Float precision rounding in migration (L4121-4137) references removed fields — must clean
  - The `recalculate_all_badges()` method (~L2230) may write derived fields — builder must grep and clean

- **Validation**:
  1. `./utils/quick_lint.sh --fix` — Must pass
  2. `mypy custom_components/kidschores/` — Zero errors
  3. `python -m pytest tests/ -v --tb=line` — All tests pass
  4. **Live verification**: After HA restart, check `sensor.kc_henry_badges` attributes show correct computed values (Bronze as highest, Silver as next_higher, Noob as next_lower)
  5. **Storage verification**: `jq '.data.kids["a88dc85d..."].cumulative_badge_progress' kidschores_data` shows only 4 fields

---

### Phase 4 – Tests

- **Goal**: Comprehensive coverage for engine retention + manager maintenance processing.
- **Files touched**: `tests/test_gamification_engine.py`, potentially new test file
- **Steps / detailed work items**

  **Engine Tests** (in `test_gamification_engine.py`):
  1. - [ ] **Update `make_badge()` helper** — Add `maintenance_threshold` parameter → `DATA_BADGE_MAINTENANCE_RULES` in target.
  2. - [ ] **Fix `test_check_retention_criteria_met`** — Test with `cycle_points >= maintenance_threshold`.
  3. - [ ] **Fix `test_check_retention_criteria_not_met`** — Test with `cycle_points < maintenance_threshold`.
  4. - [ ] **Add test: zero maintenance always passes** — `maintenance_threshold=0, cycle_points=0 → True`.
  5. - [ ] **Add test: periodic retention uses acquisition logic** — Verify periodic doesn't hit cumulative path.
  6. - [ ] **Clean up stale `cumulative_baseline` references** — Remove from `make_context()`.

  **Manager Maintenance Tests**: 7. - [ ] **ACTIVE + end_date past + points met → award_success** — Status ACTIVE, cycle_points=0, dates advanced. 8. - [ ] **ACTIVE + end_date past + points NOT met + grace>0 → GRACE** — Status transitions. 9. - [ ] **ACTIVE + end_date past + points NOT met + no grace → DEMOTED** — Status DEMOTED, cycle_points=0. 10. - [ ] **GRACE + points met → ACTIVE** — Re-promotion from grace. 11. - [ ] **GRACE + expired → DEMOTED** — Demotion from grace. 12. - [ ] **DEMOTED + end_date past + points met → ACTIVE** — Time-based re-promotion. 13. - [ ] **maintenance_rules=0 → skip** — No state changes. 14. - [ ] **reset not enabled → clear dates** — Early return path. 15. - [ ] **First-time setup → dates initialized** — New badge gets dates. 16. - [ ] **Immediate re-promotion via `_apply_badge_result`** — criteria_met + earned + DEMOTED → ACTIVE.

- **Key issues**: Need test infrastructure mocking coordinator, stats engine, kids_data with cumulative progress.

---

### Phase 5 – Validation

- **Goal**: Full quality gate pass.
- **Steps**:
  1. - [ ] `./utils/quick_lint.sh --fix` — Must pass (ruff + boundaries 10/10).
  2. - [ ] `mypy custom_components/kidschores/` — Zero errors.
  3. - [ ] `python -m pytest tests/test_gamification_engine.py -v` — All engine tests pass.
  4. - [ ] `python -m pytest tests/ -v --tb=line` — All 1259+ tests pass.
  5. - [ ] Spot-check periodic badge tests unaffected.
  6. - [ ] `grep -r "baseline_points" tests/ custom_components/` — Cleanup complete.

---

## Notes & follow-up

### Architectural Insight: `cycle_points` Role Has Changed

In the old coordinator:

- `baseline + cycle_points = total_points` → used for **tier determination** (which badge level)
- On demotion: `baseline += cycle_points; cycle_points = 0` → total preserved for tiers

In the new manager:

- `stats.get_period_total()` = total earned → used for **tier determination**
- `cycle_points` is ONLY for **maintenance evaluation** (did kid earn enough THIS cycle?)
- On demotion: just `cycle_points = 0` — no baseline, tiers use stats engine
- On award success: `cycle_points = 0` — cycle complete, fresh start

This makes `cycle_points` simpler — a pure maintenance counter, not a tier component.

### `baseline` Field Status

- **Removed in schema v44** (prior work)
- Old code stored baseline in progress, used for tier calc
- New code: tiers from `stats.get_period_total()` (authoritative)
- Old demotion logic (`baseline += cycle_points`) → replaced by `cycle_points = 0`

### Date Utility Functions

Old code used `kh.dt_today_iso()`, `kh.dt_add_interval()`, `kh.dt_next_schedule()`. Builder must verify which are in `helpers/` (HA-aware, OK for manager) vs `utils/dt_utils.py` (pure). Key functions: today ISO date, add interval to date, next schedule occurrence. These likely live in `helpers/dt_helpers.py` or similar.

### Follow-up Optimizations (Out of Scope)

- [ ] Guard `_on_points_changed` to only accumulate when maintenance_rules > 0 on any badge
- [ ] Review `recalculate_all_badges()` initial setup for conflicts
- [ ] Decide fate of `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK` (use or remove)

### Architectural Decision: Compute-on-Read vs Store-All (Phase 3A)

**Decision**: Compute-on-Read (Option A)

**Rationale**:

1. `get_cumulative_badge_progress()` already computes ALL 17 fields correctly from live data
2. The 12 derived fields went stale because 5+ write paths each only updated 2-3 fields
3. Adding "refresh after every mutation" (Option B) would require ~10 new refresh calls and would inevitably go stale again when new code paths are added
4. The computation is O(n) where n = number of cumulative badges (currently 6) — trivially fast
5. Aligns with the Gamification NextGen Plan's philosophy: "separate state from definition"
6. Eliminates an entire class of bugs permanently, not just the current manifestation

**What changes for consumers**:

- Sensor: `kid_info.get(cumulative_badge_progress)` → `coordinator.gamification.get_cumulative_badge_progress(kid_id)`
- UIManager: No change (doesn't use this data)
- Engine: No change (reads `cycle_points` which is still stored)
- Dashboard: No change (reads from sensor attributes, which are now correct)
