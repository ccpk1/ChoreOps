# Gamification unified target tracking - supporting audit

- **Initiative**: GAMIFICATION_UNIFIED_TARGET_TRACKING
- **Focus**: Periodic badge target behavior validation + standardization opportunities
- **Date**: 2026-02-18
- **Status**: Complete (analysis artifact)

## Scope and questions answered

1. Confirm no badge target uses true chore streak metrics.
2. Validate tracked-chore filtering behavior for daily/periodic badges.
3. Determine whether `badge_refs` is removed, still needed, or accidentally reintroduced.
4. Identify concrete opportunities/gaps to make target methods more common, standardized, and reusable for achievements/challenges.

---

## 1) Badge streak targets vs true chore streaks

### Finding
Periodic/daily badge streak targets do **not** use chore-level streak metrics (`streak_tally`, `longest_streak`, etc.).

### Evidence chain

- Streak badge target handlers are routed via the badge target registry in [custom_components/choreops/engines/gamification_engine.py](custom_components/choreops/engines/gamification_engine.py#L97-L167).
- Core streak logic is implemented in [custom_components/choreops/engines/gamification_engine.py](custom_components/choreops/engines/gamification_engine.py#L690-L856).
- That logic consumes normalized `daily_status` from `_resolve_daily_status` in [custom_components/choreops/engines/gamification_engine.py](custom_components/choreops/engines/gamification_engine.py#L1013-L1053).
- `_resolve_daily_status` reads:
  - `current_badge_progress.days_cycle_count`
  - `current_badge_progress.last_update_day`
  - `today_stats.streak_yesterday`
- `today_stats.streak_yesterday` is derived in StatisticsManager from badge progress fields (not chore streak fields) in [custom_components/choreops/managers/statistics_manager.py](custom_components/choreops/managers/statistics_manager.py#L2155-L2169).
- A direct search shows no references to chore streak counters inside gamification badge evaluator paths (`gamification_engine.py`, `gamification_manager.py`).

### Conclusion
The current badge “streak” target family is a **badge-local consecutive-day completion streak**, not a true chore streak metric. This matches your understanding.

---

## 2) Tracked-chore filtering validation (selected vs all)

### Expected behavior
- No selected chores -> all chores in scope (assigned to the kid).
- Selected chores provided -> only selected chores that are assigned to the kid.

### Evidence chain

- Tracked chore support is only enabled for daily/periodic badge types in [custom_components/choreops/const.py](custom_components/choreops/const.py#L4213).
- Target schema and selection fields are built through flow helpers/options flow in:
  - [custom_components/choreops/helpers/flow_helpers.py](custom_components/choreops/helpers/flow_helpers.py#L1490-L1563)
  - [custom_components/choreops/options_flow.py](custom_components/choreops/options_flow.py#L2406-L2665)
- In-scope chore resolution is centralized in [custom_components/choreops/managers/gamification_manager.py](custom_components/choreops/managers/gamification_manager.py#L2545-L2581):
  - If selected list exists -> intersection with kid-assigned chores.
  - If selected list empty -> full kid-assigned chore list.
  - If badge type has no tracked-chores component -> empty list.
- Canonical mapping/runtime evaluation uses this helper (no alternate path):
  - mapper path in [custom_components/choreops/managers/gamification_manager.py](custom_components/choreops/managers/gamification_manager.py#L1188-L1191)
  - runtime context path in [custom_components/choreops/managers/gamification_manager.py](custom_components/choreops/managers/gamification_manager.py#L1322-L1325)

### Current confidence
- Implementation path is clean and deterministic.
- Existing tests cover all-scope normalization and general periodic behavior in [tests/test_badge_target_types.py](../../tests/test_badge_target_types.py#L405-L447).

### Gap
There is still room for explicit tests that assert exact intersection behavior when:
- a selected chore is not assigned to the kid,
- mixed selected chores (some assigned, some unassigned),
- empty selected list with dynamic chore additions/removals.

---

## 3) `badge_refs` status (removed vs regenerated)

### Finding
`badge_refs` is currently in a contradictory state:
- Schema 44 migration removes it as legacy/redundant.
- Runtime startup path rebuilds it.
- No active read paths depend on it.

### Evidence chain

- Schema 44 migration explicitly removes legacy `kid_chore_data.*.badge_refs` in [custom_components/choreops/migration_pre_v50.py](custom_components/choreops/migration_pre_v50.py#L1401-L1470), with coverage in [tests/test_migration_hardening.py](../../tests/test_migration_hardening.py#L479-L505).
- Startup cascade calls `update_chore_badge_references_for_kid()` in [custom_components/choreops/managers/gamification_manager.py](custom_components/choreops/managers/gamification_manager.py#L216-L224).
- That method rewrites `badge_refs` on every kid chore entry in [custom_components/choreops/managers/gamification_manager.py](custom_components/choreops/managers/gamification_manager.py#L2870-L2923).
- Search results show `DATA_KID_CHORE_DATA_BADGE_REFS` usage only in:
  - constant definition,
  - migration cleanup,
  - regeneration method (write path),
  - legacy migration bootstrap path.
  There are no functional read-sites.

### Conclusion
`badge_refs` appears to be a legacy denormalized cache that should be fully retired, but runtime still repopulates it. This should be resolved to avoid churn/confusion.

---

## 4) Opportunities and gaps to standardize target methods for achievement/challenge reuse

## Priority 1 (high value, low risk)

1. **Create a single canonical target registry table**
   - Replace distributed mapping logic across:
     - engine handler registry,
     - manager `_map_badge_to_canonical_target`,
     - manager `_persist_periodic_badge_progress` target branches.
   - Registry should hold: raw target type -> canonical type, due-only flag, no-overdue flag, percent/min-count, persistence bucket strategy.
   - Benefit: eliminates drift risk and makes achievement/challenge wrappers declarative.

2. **Fully retire `badge_refs` path**
   - Remove runtime regeneration call and method.
   - Remove stale references from type docs/constants if not needed elsewhere.
   - Keep migration cleanup for backward compatibility.
   - Benefit: aligns implementation with schema 44 intent, reduces storage churn.

3. **Add explicit filter-behavior tests**
   - Add manager-level tests for in-scope chore intersection and empty-list-all behavior.
   - Add tests for assignment changes and reevaluation correctness.

## Priority 2 (pre-unification hardening)

4. **Normalize naming to reduce streak ambiguity**
   - Current “streak” can be interpreted as true chore streak.
   - Prefer canonical naming indicating completion-day streak semantics (for example `completion_streak_*`).
   - Keep raw target types stable for compatibility; rename canonical/internal method names.

5. **Split persistence strategy from source type**
   - Move mutator branching from raw badge target constants to canonical target families.
   - Keep a narrow source wrapper (badge/achievement/challenge) that supplies lifecycle constraints.

6. **Add manager integration coverage for pending queue + event triggers**
   - Cover `chore_approved`, `chore_disapproved`, `chore_overdue`, and midnight rollover event chain through debounce queue to evaluation/persist/award.

## Priority 3 (alignment/documentation)

7. **Update architecture notes for canonical contract**
   - Explicitly document:
     - badge-local streak vs chore streak distinction,
     - canonical target registry ownership,
     - source wrappers vs shared evaluator/mutator responsibilities.

8. **Add invariants checklist for future source onboarding**
   - Any new source must implement only:
     - mapper,
     - lifecycle wrapper,
     - optional schema/builder validation.
   - Must not duplicate criterion math or progress mutation logic.

---

## Recommended next sequence

1. Remove `badge_refs` regeneration path (keep migration cleanup).
2. Introduce canonical target registry and refactor mapper/persistence to consume it.
3. Add missing manager integration + scoped-filter tests.
4. Proceed with achievement/challenge wrapper migration on top of stabilized canonical contracts.

---

## Quick decision log

- Badge streak targets are badge-local completion streaks, not chore streak metrics.
- Tracked-chore filtering logic is implemented as expected; test depth can be improved.
- `badge_refs` is currently inconsistent with migration intent and should be retired.
- The highest-impact standardization move is a single canonical target registry shared by evaluation/mapping/persistence paths.
