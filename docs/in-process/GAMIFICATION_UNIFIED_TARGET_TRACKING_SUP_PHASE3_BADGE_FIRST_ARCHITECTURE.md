# Gamification unified target tracking – Phase 3 badge-first architecture deep dive

## Purpose

Provide a badge-first architecture reference that hardens shared target-evaluation and progress-mutation patterns before any achievement/challenge rewiring.

## Scope guardrails

- Do not change cumulative badge behavior in this phase.
- Do not implement achievement/challenge evaluator rewiring until badge-first hardening and validation gates pass.
- Keep engine pure (evaluation only) and manager stateful (mutation + side effects only).

## Current method catalog and ownership

### Engine (`engines/gamification_engine.py`)

- Public evaluators: `evaluate_badge`, `evaluate_achievement`, `evaluate_challenge`
- Non-cumulative criterion core: `_evaluate_points`, `_evaluate_points_from_chores`, `_evaluate_chore_count`, `_evaluate_daily_completion`, `_evaluate_streak`
- Cumulative isolated path: `_evaluate_cumulative_points`
- Shared helpers: `_resolve_daily_status`, `_make_result`, `_make_criterion_result`, `_get_achievement_total`, `_get_challenge_total`

### Manager (`managers/gamification_manager.py`)

- Event/queue orchestration: `_on_*` handlers, `_mark_pending`, `_schedule_evaluation`, `_evaluate_pending_kids`, `_evaluate_kid`
- Badge routing and runtime: `_evaluate_badge_for_kid`, `_evaluate_periodic_badge`, `_build_badge_runtime_context`, `_persist_periodic_badge_progress`
- Cumulative state machine: `_evaluate_cumulative_badge`, `_apply_cumulative_*`, `_badge_maintenance_enabled`
- Award and side effects: `_apply_periodic_first_award`, `_apply_periodic_reaward`, `_apply_achievement_result`, `_apply_challenge_result`, `process_award_items`, `_build_badge_award_manifest`
- Achievement/challenge wrappers: `_evaluate_achievement_for_kid`, `_evaluate_challenge_for_kid`
- Shared context: `_build_evaluation_context`

## Re-organization target model

### Layer boundaries

- Engine layer (pure):
  - Input: canonical target definition + normalized runtime context
  - Output: evaluation result + criterion results
  - No persistence, no event emission, no coordinator writes

- Manager layer (stateful):
  - Input: evaluation result + source item metadata
  - Output: idempotent progress writes + award dispatch + signals
  - Owns lifecycle wrappers and gating rules

### Canonical flow (badge-first)

1. Build base evaluation context (`_build_evaluation_context`)
2. Build source runtime context (badge scoped chores/stats)
3. Map source object to `CanonicalTargetDefinition`
4. Evaluate through shared non-cumulative engine path
5. Persist via shared idempotent manager mutator
6. Run source-specific lifecycle wrapper
7. Dispatch awards/events through manifest-compatible helpers

## Efficiency opportunities to leverage

- Reuse one normalized daily-status resolver for daily and streak families (already present; preserve and expand).
- Cache badge scoped chore list and stats once per kid+badge evaluation pass.
- Replace duplicate status transitions with one status resolver policy function.
- Consolidate progress writes into a shared canonical updater keyed by `today_iso` + `last_update_day`.
- Keep award manifest parsing in one place and route all source types through manifest-compatible adapters.
- Avoid repeated dictionary traversal by passing explicit current progress blocks into evaluator context.

## Traps to avoid

- Mixing evaluation decisions with persistence mutations in the same method.
- Re-introducing duplicate status semantics (`earned` vs `active_cycle` vs `in_progress`) across source types.
- Allowing same-day re-evaluation to double-increment day/streak counters.
- Spreading award-item parsing across badge/achievement/challenge code paths.
- Unfreezing cumulative behavior accidentally while refactoring shared code.

## Standardized naming blueprint

### Method prefix taxonomy

- `map_*_to_canonical_target` for source-to-canonical mappers
- `evaluate_*` for pure engine evaluation entrypoints
- `resolve_*` for deterministic policy or status decision helpers
- `persist_*` for manager write operations
- `apply_*` for manager side-effect wrappers (awards/signals)
- `build_*_context` for runtime/context assembly

### Suggested method naming alignment

- Keep existing stable names where possible.
- Introduce badge-first shared methods with explicit source in name:
  - `map_badge_to_canonical_target`
  - `persist_target_progress_state`
  - `apply_target_award_effects`
  - `resolve_target_status_transition`
- Achievement/challenge methods should become thin wrappers once badge path is hardened:
  - `map_achievement_to_canonical_target`
  - `map_challenge_to_canonical_target`

## Badge-first execution plan before achievement/challenge changes

1. Finalize shared badge canonical mapper and status resolver.
2. Extract shared progress-mutation function for non-cumulative badge targets.
3. Normalize award dispatch interface for badge path (manifest-compatible).
4. Validate with badge-focused integration and regression suites.
5. Freeze badge architecture contract and naming map.
6. Only then route achievement/challenge wrappers through the shared core.

## Required quality gates before achievement/challenge rewiring

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/`
- Badge-focused tests:
  - `tests/test_gamification_engine.py`
  - `tests/test_badge_target_types.py`
  - `tests/test_badge_cumulative.py`
  - manager event/queue integration coverage

## Extensibility outcome target

If this plan is followed, adding a new gamification object type should require:

- one mapper (`map_<source>_to_canonical_target`)
- one lifecycle wrapper (`apply_<source>_result`)
- zero duplicate criterion logic
- zero duplicate progress mutation logic
- no changes to cumulative badge state machine
