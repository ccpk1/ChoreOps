# Initiative snapshot

- **Name / Code**: Gamification Unified Target Tracking (Badges → Achievements/Challenges)
- **Target release / milestone**: v0.5.0-beta4 hardening (pre-release stabilization)
- **Owner / driver(s)**: KidsChores core maintainers (Gamification domain)
- **Status**: Complete (implemented, validated, approved for archive)

## Summary & immediate steps

| Phase / Step                                | Description                                                                    | % complete | Quick notes                                                                                   |
| ------------------------------------------- | ------------------------------------------------------------------------------ | ---------- | --------------------------------------------------------------------------------------------- |
| Phase 1 – Baseline & guardrails             | Freeze cumulative paths, define unified target contract                        | 100%       | Contracts and inventories captured; cumulative freeze guard added                             |
| Phase 2 – Non-cumulative badge hardening    | Fix/standardize periodic + daily + streak badge evaluation/state updates       | 100%       | Runtime context + idempotent progress writes now active                                       |
| Phase 3 – Achievement/challenge unification | Badge-first architecture hardening, then shared target evaluator/state updater | 100%       | Added source mappers + canonical evaluator wiring + manager lifecycle wrappers                 |
| Phase 4 – Tests, perf, rollout safety       | Expand deterministic tests + regression/perf coverage + migration check        | 100%       | Added manager integration + mapped target coverage + full validation gate pass                 |

1. **Key objective** – Make non-cumulative target tracking deterministic and reusable, then use the exact same core logic for achievements and challenges.
2. **Summary of recent work** – Completed Phase 3 achievement/challenge rewiring: added canonical source mappers, routed achievement/challenge evaluation through canonical engine path, and kept challenge lifecycle window ownership in manager wrappers.
3. **Next steps (short term)** – Owner review and release-prep handoff (no additional phase implementation blockers remain in this plan).
4. **Risks / blockers** – No active implementation blockers; continue cumulative behavior regression checks in follow-on work.
5. **Critical quality expectation** – Final outcome must show high standardization and organization across contracts, naming, and flow ownership; implementation must favor deterministic, auditable behavior over convenience shortcuts.
6. **References** –
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)

- [GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE0_DEEP_DIVE.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE0_DEEP_DIVE.md)
- [GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_IMPLEMENTATION_BLUEPRINT.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_IMPLEMENTATION_BLUEPRINT.md)
- [GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE3_BADGE_FIRST_ARCHITECTURE.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE3_BADGE_FIRST_ARCHITECTURE.md)
- [GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PERIODIC_TARGET_AUDIT.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PERIODIC_TARGET_AUDIT.md)

- **Overall plan progress**: 100% (4/4 phases complete)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Cumulative badge behavior in `_evaluate_cumulative_badge` is frozen for this initiative (no behavior refactor).
     - Unified logic will be implemented as: `Engine = pure criterion/daily status evaluation`, `Manager = idempotent progress mutation + award side effects`.
     - Achievements and challenges will use badge-style target mapping with lifecycle wrappers (achievement: non-resetting; challenge: date-window gated).
     - Rolling-window requirements should prefer persisted per-item progress fields over long-term daily history retention when equivalent.
  - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Baseline & guardrails

- **Goal**: Lock scope boundaries and define a single target-tracking contract before refactoring behavior.
- **Steps / detailed work items**
  - [x] Build a method inventory and ownership matrix for gamification evaluation and award processing:
    - Engine type-specific methods (example: cumulative-only state checks vs date-window checks)
    - Engine shared methods (daily criteria checks, threshold/progress math)
    - Manager shared side-effect methods (points/reward/bonus/penalty award manifest and dispatch)
    - Output artifact: classification table in this plan plus follow-up extraction candidates
  - [x] Capture current behavior matrix for non-cumulative targets in `engines/gamification_engine.py` (line hints: `evaluate_badge` ~176, `_evaluate_daily_completion` ~647, `_evaluate_streak` ~841, `_get_achievement_total` ~1062, `_get_challenge_total` ~1087).
  - [x] Inventory award-processing flow end-to-end and mark shared extraction points (line hints: manager `process_award_items` / `_build_badge_award_manifest` ~1738-1810, award application in `_apply_periodic_first_award`/`_apply_periodic_reaward` ~1345-1422 and achievement/challenge award methods ~332-470).
  - [x] Add a refactor guard doc block in `managers/gamification_manager.py` near `_evaluate_badge_for_kid` / `_evaluate_periodic_badge` / `_evaluate_cumulative_badge` (line hints: ~780/~941/~817) describing “cumulative immutable during this initiative.”
  - [x] Define a canonical target definition (typed) in `custom_components/choreops/type_defs.py` near `BadgeTarget` and `EvaluationContext` (line hints: ~233 and ~735) for reusable mapping across badge/achievement/challenge.
  - [x] Define canonical progress mutation fields in `type_defs.py` (`days_cycle_count`, `last_update_day`, streak/day counters) and specify idempotency rules for same-day re-evaluation.
  - [x] Validate whether schema migration is needed: if only existing fields are reused, **no schema bump**; if new persisted keys are introduced, add migration plan in coordinator/store migration path.
- **Key issues**
  - Current logic mixes criterion evaluation and implicit state assumptions; same-day re-evaluation/undo paths can double-increment or reset unexpectedly.
  - Award side effects are split across badge/achievement/challenge pathways; a method inventory is required to avoid duplicating award dispatch rules.
  - `AchievementProgress` and `ChallengeProgress` structures differ from `KidBadgeProgress`, requiring a mapping layer decision before coding.

#### Phase 1 deliverable: method inventory and ownership matrix

| Domain  | Classification                | Methods                                                                     | Outcome                                       |
| ------- | ----------------------------- | --------------------------------------------------------------------------- | --------------------------------------------- |
| Engine  | Type-specific (keep isolated) | `evaluate_badge` cumulative path, `_evaluate_cumulative_points`             | Keep isolated (cumulative frozen)             |
| Engine  | Shared extraction candidates  | `_evaluate_daily_completion`, `_evaluate_streak`, threshold/reason assembly | Reuse in unified non-cumulative target core   |
| Engine  | Duplicate pipeline candidates | `evaluate_achievement`, `evaluate_challenge`                                | Unify via canonical target adapter in Phase 3 |
| Manager | Shared award processing       | `process_award_items`, `_build_badge_award_manifest`                        | Keep as canonical manifest path               |
| Manager | Duplicate side-effect path    | manual manifest assembly in `award_badge`                                   | Route to canonical helper in Phase 3          |

#### Phase 1 deliverable: non-cumulative behavior matrix (current-state baseline)

| Family                         | Engine input contract                                                      | Progress semantics                                          | Manager mutation owner                     |
| ------------------------------ | -------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------ |
| Points / chore_count           | `today_stats` + `current_badge_progress` counters                          | cycle counter + current day contribution                    | periodic badge apply path                  |
| Days completion variants       | `today_completion` / `today_completion_due` + `days_cycle_count`           | if today criteria met, conceptual +1 (manager persists)     | periodic badge apply path                  |
| Streak variants                | `today_stats.streak_yesterday` + completion snapshots + `days_cycle_count` | continue/start/reset streak based on today + yesterday gate | periodic badge apply path                  |
| Achievement total/daily/streak | `achievement_progress` + `today_stats` + total helpers                     | per-achievement counters/baseline logic                     | `_apply_achievement_result` + award method |
| Challenge total/daily          | `challenge_progress` + `today_stats` + date window                         | per-challenge count/daily min inside active window          | `_apply_challenge_result` + award method   |

#### Phase 1 deliverable: award-processing flow inventory

| Flow                             | Source methods                                                                  | Shared extraction point              | Phase 2/3 action                      |
| -------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------- |
| Badge automatic award/re-award   | `_apply_periodic_first_award`, `_apply_periodic_reaward`, `_apply_cumulative_*` | `_build_badge_award_manifest`        | Keep single builder contract          |
| Badge manual award               | `award_badge`                                                                   | currently partial duplicate logic    | Refactor to canonical manifest helper |
| Achievement/challenge completion | `award_achievement`, `award_challenge`, `_apply_*_result`                       | single-event ownership normalization | Remove duplicate emits in P0 package  |

#### Phase 1 deliverable: schema migration decision

- Decision: **No schema bump in Phase 1**.
- Rationale: Deliverables are guard comments, contract typings, and plan/inventory artifacts only.
- Forward rule: If later phases add persisted keys beyond existing progress structures, introduce migration via coordinator/store migration path and explicitly document schema/version update in this plan.

### Phase 2 – Non-cumulative badge hardening

- **Goal**: Make periodic/daily/streak badge tracking deterministic, efficient, and idempotent without touching cumulative behavior.
- **Steps / detailed work items**
  - [x] Implement a single daily-criteria evaluator in `engines/gamification_engine.py` (line hints: between `_evaluate_daily_completion` ~647 and `_evaluate_streak` ~841) returning normalized daily status inputs for both day-count and streak targets.
  - [x] Refactor badge daily/streak handlers to consume that shared evaluator and remove duplicate branch logic between daily and streak variants.
  - [x] Add manager-side idempotent progress updater in `managers/gamification_manager.py` used by non-cumulative badge paths (`_evaluate_periodic_badge` ~941 and result application area), keyed by `today_iso` + `last_update_day`.
  - [x] Ensure tracked-chore resolution is reused from existing helper (`get_badge_in_scope_chores_list`) and context build path (`_build_evaluation_context`) to avoid redundant loops.
  - [x] Add explicit non-goal protection comments + assertions/tests that cumulative methods (`_evaluate_cumulative_badge`, `_apply_cumulative_*`) remain behaviorally unchanged.
- **Key issues**
  - Current periodic evaluation can pass criterion checks without a fully explicit update-state contract.
  - Efficiency risk: repeated daily-scope chore scans per target type if context is not normalized once per evaluation cycle.
  - Known architecture miss to fix in this phase: non-cumulative badge evaluation may run without persisting progress updates into `kid.badge_progress`.

#### Phase 2B – Missed hardening follow-ups (captured after periodic target audit)

- **Goal**: Close remaining non-cumulative target hardening gaps discovered during post-Phase-2 audit before achievement/challenge rewiring expands shared logic surface area.
- **Steps / detailed work items**
  - [x] Remove runtime regeneration of chore `badge_refs` from `GamificationManager` startup/reference sync path and keep schema-44 migration cleanup as backward-compatibility-only behavior.
  - [x] Remove or downscope remaining `badge_refs` documentation/type hints (for example in `type_defs.py`) so docs align with runtime architecture.
  - [x] Add explicit manager-level tests for tracked-chore scope filtering:
    - empty `selected_chores` means all chores assigned to the kid are in scope
    - non-empty `selected_chores` is intersected with the kid-assigned chore set
    - mixed selected list (assigned + unassigned) only includes assigned chore IDs
  - [x] Add an explicit mapper guard for unknown periodic target types (avoid implicit defaulting to daily-completion semantics in mapping paths).
  - [x] Add explicit fail-fast or warning behavior in badge target mapper when `target_type` is unknown, and ensure this path is validated by dedicated tests.
  - [x] Add a single canonical target registry proposal (or implementation spike) that can drive:
    - engine handler routing
    - manager canonical mapping flags (`due-only`, `no-overdue`, `%/min-count`)
    - manager persistence bucket strategy
  - [x] Remove duplicated target-type branching by moving engine registry + manager mapper + manager persistence routing to one shared metadata table (single source of truth), with compatibility shims where needed.
  - [x] Add a naming-standard pass for canonical streak families to make completion-day streak semantics explicit and avoid confusion with true chore streak metrics.
  - [x] Add manager-level integration tests for pending-queue/event-driven paths (`chore_approved`, `chore_disapproved`, `chore_overdue`, midnight rollover) to verify end-to-end queueing → evaluation → persistence behavior (not only unit-level engine checks).
  - [x] Review and resolve award-count ownership inconsistency:
    - `update_badges_earned_for_kid` comments describe tenant-owned award count in periods
    - periodic re-award path directly mutates `DATA_KID_BADGES_EARNED_AWARD_COUNT`
    - choose one canonical ownership model and align comments + implementation.

#### Phase 2B implementation update (2026-02-18)

- Runtime `badge_refs` regeneration was removed from startup cascade (`_on_stats_ready` now signals readiness without rebuilding legacy references).
- Legacy `badge_refs` documentation was downscoped from type docs; migration cleanup remains as compatibility path.
- Canonical periodic target metadata registry now drives engine routing metadata, manager canonical mapping flags, and manager persistence bucket strategy from a single source.
- Unknown periodic target handling now warns explicitly and avoids implicit daily fallback semantics.
- Added manager-level test coverage for scope filtering behavior and pending-queue event-driven re-evaluation paths.
- Award count ownership comments were aligned with current manager-owned periodic re-award behavior.
- **Key issues**
  - Current architecture has a contradiction: migration removes legacy `badge_refs`, but runtime currently rebuilds `badge_refs` structures at startup/reference sync.
  - Target logic semantics are currently represented in multiple places (engine registry, manager mapper, manager persistence branches), creating future drift risk as achievement/challenge wrappers are added.
  - Existing tests verify broad periodic behavior, but scoped-filter edge coverage (assigned/intersection cases) is still shallow for this contract-critical path.
  - Unknown target handling currently risks implicit fallback semantics in mapper paths, which can hide configuration defects.
  - Award-count ownership semantics are not fully aligned between documented architecture comments and periodic re-award implementation behavior.

### Phase 3 – Achievement/challenge unification

- **Goal**: Finalize badge-first architecture, naming, and shared method contracts so achievement/challenge unification becomes a thin, low-risk wrapper migration.
- **Steps / detailed work items**
  - [x] Capture a badge-first deep-dive reference (`GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE3_BADGE_FIRST_ARCHITECTURE.md`) with current method catalog, efficiency opportunities, traps, and layer ownership boundaries.
  - [x] Add manager/engine re-organization blueprint into implementation checklist with explicit method ownership split:
    - engine: pure canonical evaluation and normalized criterion handlers
    - manager: idempotent progress mutation, lifecycle wrappers, award/event dispatch
  - [x] Add standardized naming matrix and migration map (existing method -> target method/owner) for consistency and future extensibility.
  - [x] Define badge-first hardening gates that must pass before achievement/challenge rewiring:
    - shared mapper + status resolver + progress mutator + award-dispatch adapter
    - badge-focused tests/regression gates must pass first
  - [x] Harden and validate badge-first shared methods before achievement/challenge rewiring (implementation).
  - [x] Introduce mapper functions in `managers/gamification_manager.py` to convert `AchievementData` and `ChallengeData` into canonical target definitions (line hints: around `_evaluate_achievement_for_kid` ~1410 and `_evaluate_challenge_for_kid` ~1485).
  - [x] Route `_evaluate_achievement_for_kid` and `_evaluate_challenge_for_kid` through the same core evaluator path used by non-cumulative badges (engine + manager state updater), replacing direct bespoke type branches (line hints: manager ~1410-1565; engine `evaluate_achievement` ~273 and `evaluate_challenge` ~361).
  - [x] Keep lifecycle wrappers in manager:
    - achievement: no reset window, permanent once awarded.
    - challenge: active only within `start_date`/`end_date`.
  - [x] Add achievement-specific extension for badge award count tracking using earned badge data (`badges_earned[badge_id].award_count`) with explicit mapping constant(s) in `const.py` (line hints: earned-badge constants ~920-929).
  - [x] Align data construction/validation compatibility in `data_builders.py` and `helpers/flow_helpers.py` only if new target option(s) or fields are exposed (line hints: `build_achievement` ~2275, `build_challenge` ~2579, achievement/challenge schemas in flow helpers ~2556/~2704).
- **Key issues**
  - Achievement/challenge code changes are explicitly blocked until badge-first architecture hardening tasks and gates are complete.
  - Existing gamification method naming is partially inconsistent across evaluation, mutation, and side-effect operations; a standardized naming map is required before broad refactors.
  - Existing achievement/challenge types (`daily_minimum`, `chore_streak`, `chore_total`, `total_within_window`) do not currently map 1:1 to badge target names without a translation layer.
  - Badge award count tracking for achievements introduces a new source type that needs strict typing and migration decision.

#### Phase 3 planning deliverable: manager/engine re-organization blueprint

| Layer   | Responsibility                                                               | Allowed operations                                                              | Forbidden operations                                        |
| ------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Engine  | Canonical criterion evaluation and deterministic progress computation        | Evaluate canonical targets, produce `EvaluationResult`/`CriterionResult`        | Persistence, event emission, coordinator writes             |
| Manager | Orchestration, idempotent progress mutation, lifecycle control, side effects | Build runtime context, persist progress state, emit award and lifecycle signals | Embedding duplicated criterion math already owned by engine |

#### Phase 3 planning deliverable: standardized naming and migration map

| Current method                                            | Target method/path                                                            | Owner after migration | Notes                                                                           |
| --------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------- | ------------------------------------------------------------------------------- |
| `_build_badge_runtime_context`                            | `build_target_runtime_context`                                                | Manager               | Shared context builder used by badge-first, then achievement/challenge wrappers |
| `_persist_periodic_badge_progress`                        | `persist_target_progress_state`                                               | Manager               | Shared idempotent mutator keyed by `today_iso` + `last_update_day`              |
| `evaluate_badge` (non-cumulative branch)                  | `evaluate_canonical_target` (called by badge wrapper)                         | Engine                | Keep cumulative branch isolated                                                 |
| `_evaluate_daily_completion` / `_evaluate_streak`         | `evaluate_daily_target` / `evaluate_streak_target` (shared internal handlers) | Engine                | Shared handler families for all mapped target sources                           |
| `_apply_periodic_first_award` / `_apply_periodic_reaward` | `apply_target_award_effects` + badge lifecycle wrapper                        | Manager               | Retain badge-specific award_count semantics                                     |
| `_evaluate_achievement_for_kid`                           | `evaluate_achievement_for_kid` (thin wrapper + mapper)                        | Manager               | No direct bespoke criterion branches after migration                            |
| `_evaluate_challenge_for_kid`                             | `evaluate_challenge_for_kid` (thin wrapper + mapper)                          | Manager               | Date-window lifecycle remains wrapper-owned                                     |

#### Phase 3 planning deliverable: badge-first acceptance gates (pre-implementation)

- Gate A: shared mapper/status/mutator interfaces are defined and reviewed before rewiring source wrappers.
- Gate B: badge path remains deterministic for same-day re-evaluation, status transitions, and cycle boundaries.
- Gate C: cumulative badge behavior remains unchanged and is protected by targeted regression suite.
- Gate D: achievement/challenge rewiring starts only after badge-first gates pass.

#### Phase 3 implementation update: badge-first shared method slice

- Implemented in `managers/gamification_manager.py`:
  - `_map_badge_to_canonical_target`
  - `_resolve_target_status_transition`
  - `_apply_target_award_effects`
  - periodic flow wiring in `_evaluate_periodic_badge` to use the shared methods
- Progress mutation path now uses shared status transition resolver and includes due-streak target variants in the persisted day/streak bucket handling.
- Validation evidence:
  - `python -m pytest tests/test_gamification_engine.py tests/test_badge_target_types.py tests/test_badge_cumulative.py -q` → `66 passed`
  - `./utils/quick_lint.sh --fix` → Ruff + MyPy + boundary checks all passed
- Scope lock preserved: no achievement/challenge rewiring performed in this slice.

#### Phase 3 implementation update: Step 2 shared runtime context path

- Implemented in `managers/gamification_manager.py`:
  - periodic flow now calls `_build_target_runtime_context(...)` instead of `_build_badge_runtime_context(...)`
  - shared runtime context builder consumes `canonical_target` and reuses `tracked_chore_ids` from mapper output
- Efficiency gain: removes duplicate in-scope chore resolution inside one periodic evaluation pass.
- Validation evidence:
  - `python -m pytest tests/test_gamification_engine.py tests/test_badge_target_types.py tests/test_badge_cumulative.py -q` → `66 passed`
  - `./utils/quick_lint.sh --fix` → Ruff + MyPy + boundary checks all passed
- Scope lock preserved: no achievement/challenge rewiring performed in this step.

#### Phase 3 implementation update: Step 3 shared progress mutator interface

- Implemented in `managers/gamification_manager.py`:
  - added `_persist_target_progress_state(...)` as shared non-cumulative target mutator interface
  - periodic flow now uses shared mutator interface from `_evaluate_periodic_badge(...)`
  - kept `_persist_periodic_badge_progress(...)` as a backward-compatible wrapper path for existing direct callers/tests
- Behavior safety:
  - no periodic badge award/criteria behavior changes intended
  - canonical target `source_raw_type` is used when available, with safe fallback to badge target data for compatibility
- Validation evidence:
  - `python -m pytest tests/test_gamification_engine.py tests/test_badge_target_types.py tests/test_badge_cumulative.py -q` → `66 passed`
  - `./utils/quick_lint.sh --fix` → Ruff + MyPy + boundary checks all passed
- Scope lock preserved: no achievement/challenge rewiring performed in this step.

#### Phase 3 implementation update: Step 4 achievement/challenge canonical rewiring

- Implemented canonical source mappers in `managers/gamification_manager.py`:
  - `_map_achievement_to_canonical_target(...)`
  - `_map_challenge_to_canonical_target(...)`
- Added shared source runtime-context builder:
  - `_build_source_runtime_context(...)` with scoped stats hydration and typed progress injection.
- Routed achievement/challenge manager evaluation through canonical engine path:
  - `_evaluate_achievement_for_kid(...)` now maps + evaluates canonical targets
  - `_evaluate_challenge_for_kid(...)` now maps + evaluates canonical targets
- Added manager lifecycle wrapper enforcement for challenges:
  - challenge evaluation returns early outside active `start_date`/`end_date` window.
- Added canonical evaluator support in `engines/gamification_engine.py`:
  - `evaluate_canonical_target(...)`
  - `_evaluate_canonical_target_criterion(...)`
- Added achievement badge-award-count extension support:
  - constants and source mapping in `const.py`
  - canonical path reads `badges_earned[badge_id].award_count` when configured.
- Compatibility note:
  - no new options/config flow fields were exposed, so no builder/flow schema changes were required in this step.
- Validation evidence:
  - `python -m pytest tests/test_gamification_engine.py tests/test_workflow_gamification_pending_queue.py -q` → `39 passed`
  - `./utils/quick_lint.sh --fix` → Ruff + MyPy + boundary checks passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` → success

#### Phase 3 planning deliverable: extensibility contract

For future gamification sources, required additions must be limited to:

- one source mapper (`map_<source>_to_canonical_target`)
- one source lifecycle wrapper (`apply_<source>_result`)
- optional source-specific validation additions in builder/flow schema

No new source type should duplicate criterion handlers or progress mutation logic.

### Phase 4 – Tests, perf, rollout safety

- **Goal**: Prove correctness and regressions for non-cumulative refactor + unified achievement/challenge tracking while preserving cumulative behavior.
- **Steps / detailed work items**
  - [x] Add schema-44 migration cleanup for legacy `kid_chore_data.*.badge_refs` in `migration_pre_v50.py` and regression coverage in `tests/test_migration_hardening.py`.
  - [x] Expand unit tests in `tests/test_gamification_engine.py` for normalized daily evaluator, streak continuation/break, idempotent same-day re-evaluation, and tracked-chore/no-overdue variants.
  - [x] Add non-cumulative runtime regression tests in `tests/test_badge_target_types.py` for all-scope tracking normalization, rollover/start-date correctness, precision/day-marker persistence, status transitions, and current-cycle re-award guard.
  - [x] Add manager integration tests (new or existing workflow file, e.g., `tests/test_workflow_*.py`) covering pending queue + event-driven re-evaluation (`chore_approved`, `chore_disapproved`, `chore_overdue`, midnight rollover).
  - [x] Add dedicated tests for achievement/challenge mapped targets and lifecycle differences; include badge-award-count achievement case.
  - [x] Keep cumulative suite as regression gate (`tests/test_badge_cumulative.py`) and verify no expected behavior changes.
  - [x] Run and record validation sequence:
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/ -v --tb=line`
- **Key issues**
  - Existing `tests/test_badge_target_types.py` is mostly create/config coverage; deeper state-machine regression tests are needed for confidence.
  - Shadow-comparison tests may need updates to compare mapped achievement/challenge behavior against intended new canonical semantics.

## Testing & validation

- **Targeted suites (during implementation)**:
  - `tests/test_gamification_engine.py`
  - `tests/test_badge_target_types.py`
  - `tests/test_gamification_shadow_comparison.py`
  - `tests/test_badge_cumulative.py` (regression-protection gate)
- **Latest run notes**:
  - `tests/test_gamification_engine.py`: ✅ targeted suite passed after idempotency + due-only/no-overdue additions
  - `tests/test_badge_target_types.py`: ✅ 16 passed
  - `tests/test_badge_cumulative.py`: ✅ 15 passed (rerun after non-cumulative fixes)
  - `python -m pytest tests/test_gamification_engine.py tests/test_workflow_gamification_pending_queue.py -q`: ✅ `39 passed`
  - `python -m pytest tests/test_workflow_gamification_pending_queue.py -q`: ✅ `7 passed`
  - `python -m pytest tests/ -v --tb=line`: ✅ `1439 passed, 2 skipped, 2 deselected`
  - `./utils/quick_lint.sh --fix`: ✅ Ruff + MyPy + boundary checks passed
- **Full validation gates before completion**:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- **Performance checkpoint**:
  - `python -m pytest tests/test_performance_comprehensive.py -s --tb=short`

## Notes & follow-up

- **Scope lock**: Cumulative badge logic is explicitly excluded from behavior changes in this initiative.
- **Data-retention strategy**: Prefer per-kid/per-item progress counters for rolling evaluations to avoid retaining full daily history solely for gamification logic.
- **Potential follow-on**: After this initiative, consider a dedicated “target DSL” for all gamification objects to reduce future divergence.
- **Completion artifacts expected**:
  - Architecture note update in `docs/ARCHITECTURE.md` (gamification unified evaluator/state-update contract).
  - If new persisted keys are added, migration note and schema/version update documentation.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
