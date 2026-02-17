# Supporting Document: Gap Analysis — Cumulative Badge Maintenance

**Parent Plan**: [CUMULATIVE_BADGE_RETENTION_FIX_COMPLETED.md](./CUMULATIVE_BADGE_RETENTION_FIX_COMPLETED.md)
**Purpose**: Detailed current-state audit of all cumulative badge maintenance code
**Status**: Completed

---

## 1. Current Code Inventory

### 1.1 `_on_points_changed()` — gamification_manager.py ~L170-215

**What it does**: When a non-gamification `points_changed` event fires with a **positive** delta, increments `cycle_points` in cumulative badge progress.

- **Reads**: `DATA_KID_CUMULATIVE_BADGE_PROGRESS`, `cycle_points`
- **Writes**: `cycle_points` (in-memory only, does NOT call `_persist()`)
- **Guards**: Only positive deltas, excludes gamification sources
- **Missing guard**: Accumulates for ALL positive deltas regardless of whether ANY badge has `maintenance_rules > 0`
- **No references to**: GRACE, DEMOTED, re-promotion, maintenance_rules, reset_schedule

### 1.2 `recalculate_all_badges()` — gamification_manager.py ~L308, L2230-2520

**What it does**: Iterates all kids, marks them for debounced re-evaluation. The full loop (L2230-2520) creates/syncs badge progress entries.

- **Maintenance-related**: Handles `reset_schedule` at L2319+ for **initial setup only** — calculates initial maintenance_end_date and grace_end_date when creating new progress entries
- **Does NOT**: Evaluate whether end_date has passed, rotate cycles, check grace period, transition states
- **Does NOT**: Process maintenance windows at runtime

### 1.3 `_evaluate_badge_for_kid()` — gamification_manager.py ~L763-795

**What it does**: For a kid+badge pair, routes to `check_acquisition()` (not earned) or `check_retention()` (already earned), then passes result to `_apply_badge_result()`.

- **No references to**: cycle_points, maintenance_rules, GRACE, dates
- **Role**: Pure routing — delegates to engine, passes result to applicator

### 1.4 `_apply_badge_result()` — gamification_manager.py ~L798-892

**What it does**: Applies evaluation result. Current logic matrix:

| criteria_met | already_earned | Action                                                               |
| :----------: | :------------: | -------------------------------------------------------------------- |
|      ✅      |       ❌       | **Award badge** (calls `_record_badge_earned`, emits `BADGE_EARNED`) |
|      ❌      |       ✅       | **Demote** (cumulative only → calls `demote_cumulative_badge`)       |
|      ✅      |       ✅       | ⚠️ **NO BRANCH — falls through silently** (re-promotion missing)     |
|      ❌      |       ❌       | No action (correct — nothing to do)                                  |

- **Critical gap**: The `criteria_met=True + already_earned=True` case has no handler. A demoted kid who regains enough points is never re-promoted.

### 1.5 `_build_evaluation_context()` — gamification_manager.py ~L1042-1118

**What it does**: Builds the `EvaluationContext` dict passed to the engine. Includes `cumulative_badge_progress` (cycle_points, status) and `total_points_earned` from stats engine.

- **Does NOT include**: maintenance_end_date, grace_end_date in context (these aren't needed by the engine — the manager handles date logic)
- **All-time points source**: `self.coordinator.stats.get_period_total()` ✅

### 1.6 `get_cumulative_badge_levels()` — gamification_manager.py ~L1303-1407

**What it does**: Returns 5-tuple: (highest_earned, next_higher, next_lower, baseline_deprecated, cycle_points). Uses `stats.get_period_total()` for tier determination.

- **baseline**: Returns hardcoded `0.0` (deprecated)
- **Tier total**: `stats.get_period_total()` (correct — all-time earned from stats engine)
- **No references to**: maintenance_rules, reset_schedule, GRACE, DEMOTED, dates

### 1.7 `update_point_multiplier_for_kid()` — gamification_manager.py ~L1410-1450

**What it does**: Reads `current_badge_id` from progress, looks up multiplier from badge awards, emits `SIGNAL_SUFFIX_MULTIPLIER_CHANGED` for EconomyManager.

- **Working correctly**: Called by `demote_cumulative_badge()` and badge award paths
- **Will be called by**: `process_cumulative_maintenance()` (Phase 2) for re-promotion

### 1.8 `get_cumulative_badge_progress()` — gamification_manager.py ~L1586-1724

**What it does**: Builds and returns the full display dict for cumulative badge progress. Read-only (returns dict, doesn't mutate storage).

- **Handles DEMOTED**: If status=DEMOTED, switches current_badge to next_lower
- **References ACTIVE**: As fallback default
- **Does NOT reference**: GRACE (missing from display logic too)
- **All-time source**: `stats.get_period_total()` ✅

### 1.9 `demote_cumulative_badge()` — gamification_manager.py ~L1727-1773

**What it does**: Sets status to DEMOTED, recalculates multiplier, persists.

- **Guard**: Only writes if `status != DEMOTED` (avoids re-demotion)
- **Does NOT reset**: cycle_points (the old code DID reset cycle_points on demotion)
- **Calls**: `self.coordinator._persist()` ✅
- **Called from**: `_apply_badge_result()` only

### 1.10 `_record_badge_earned()` — gamification_manager.py ~L2078-2119

**What it does**: Records that kid earned a badge (appends to earned_by list, updates badges_earned dict).

- **Does NOT touch**: cycle_points, status, maintenance dates
- **Working correctly**: Will be reused by maintenance award path

---

## 2. Engine State

### 2.1 `check_acquisition()` — gamification_engine.py ~L286-305

Delegates to `evaluate_badge()` → standard threshold check. Works correctly for cumulative (inline block at L211-240 compares `total_points_earned >= threshold`).

### 2.2 `check_retention()` — gamification_engine.py ~L308-327

**THE BUG**: Delegates to `evaluate_badge()` — **identical to acquisition**. Comment says "Badge maintenance logic in Manager handles grace periods". But the manager maintenance method **doesn't exist**. Result: retention always passes for cumulative badges because `total_points_earned` only grows.

### 2.3 `evaluate_badge()` inline cumulative block — gamification_engine.py ~L211-240

Works correctly for **acquisition**: compares `total_points_earned >= threshold`. But this is the wrong comparison for **retention** (should compare `cycle_points >= maintenance_rules`).

---

## 3. Dead Infrastructure

### 3.1 `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK`

- **Defined**: const.py ~L1904 value `"badge_maintenance_check"`
- **Emitted by**: NOBODY
- **Listened by**: NOBODY
- **Status**: Dead signal — scaffolded but never wired

### 3.2 `CUMULATIVE_BADGE_STATE_GRACE`

- **Defined**: const.py ~L1905 value `"grace"`
- **Written by**: NOBODY
- **Read by**: Only as display text in sensor/progress methods
- **Status**: Dead constant — the GRACE state transition was never implemented

### 3.3 Midnight Rollover → GamificationManager

- **Midnight rollover signal**: Exists, used by ChoreManager, UIManager, StatisticsManager
- **GamificationManager**: Does NOT subscribe to midnight rollover
- **Impact**: No scheduled maintenance evaluation occurs. Dates in progress are purely decorative.

---

## 4. All-Time Points Sourcing — Verified Correct

All 3 locations use `self.coordinator.stats.get_period_total()`:

| Location                          | Line   | Purpose                                          |
| --------------------------------- | ------ | ------------------------------------------------ |
| `_build_evaluation_context()`     | ~L1062 | Sets `total_points_earned` in evaluation context |
| `get_cumulative_badge_levels()`   | ~L1327 | Determines which tier badges are earned          |
| `get_cumulative_badge_progress()` | ~L1611 | Populates progress display dict                  |

**No location** uses the old `baseline + cycle_points` formula for tier determination. ✅

---

## 5. Constants Reference

| Constant                                                        | Location        | Value                          | Status                           |
| --------------------------------------------------------------- | --------------- | ------------------------------ | -------------------------------- |
| `DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS`               | const.py ~L1071 | `"cycle_points"`               | ✅ Used                          |
| `DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS`                     | const.py ~L1072 | `"status"`                     | ✅ Used                          |
| `DATA_BADGE_MAINTENANCE_RULES`                                  | const.py ~L1589 | `"maintenance_rules"`          | ✅ Stored, never read at runtime |
| `DEFAULT_BADGE_MAINTENANCE_THRESHOLD`                           | const.py ~L1718 | `0`                            | ✅ Used as default               |
| `CUMULATIVE_BADGE_STATE_ACTIVE`                                 | const.py ~L1904 | `"active"`                     | ✅ Used                          |
| `CUMULATIVE_BADGE_STATE_GRACE`                                  | const.py ~L1905 | `"grace"`                      | ❌ Dead                          |
| `CUMULATIVE_BADGE_STATE_DEMOTED`                                | const.py ~L1906 | `"demoted"`                    | ✅ Used                          |
| `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK`                         | const.py        | `"badge_maintenance_check"`    | ❌ Dead                          |
| `DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE`       | const.py        | `"maintenance_end_date"`       | ⚠️ Stored, never evaluated       |
| `DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE` | const.py        | `"maintenance_grace_end_date"` | ⚠️ Stored, never evaluated       |

---

## 6. Summary: What Must Be Built

| Gap                                               | Severity    | Where to Build                          |
| ------------------------------------------------- | ----------- | --------------------------------------- |
| Engine: `check_retention()` for cumulative        | 🔴 Critical | Engine (Phase 1)                        |
| Manager: Maintenance processing method            | 🔴 Critical | Manager (Phase 2)                       |
| Manager: cycle_points reset at cycle boundary     | 🔴 Critical | Manager (Phase 2)                       |
| Manager: GRACE state transition                   | 🟡 Medium   | Manager (Phase 2)                       |
| Manager: Re-promotion DEMOTED→ACTIVE (time-based) | 🔴 Critical | Manager (Phase 2)                       |
| Manager: Re-promotion DEMOTED→ACTIVE (immediate)  | 🔴 Critical | Manager `_apply_badge_result` (Phase 3) |
| Manager: Midnight rollover subscription           | 🔴 Critical | Manager (Phase 3)                       |
| Manager: First-time date initialization           | 🟡 Medium   | Manager (Phase 2)                       |
| Wire `SIGNAL_SUFFIX_BADGE_MAINTENANCE_CHECK`      | 🟢 Low      | Phase 3                                 |
| Display: GRACE status in progress sensor          | 🟢 Low      | Already handled if status is set        |
