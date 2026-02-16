# Gamification unified target tracking: implementation blueprint

## Purpose

This document is the execution-ready implementation blueprint for the gamification refactor. It translates phase-0 findings into concrete work packages, sequencing, acceptance criteria, and validation gates required for Platinum-quality delivery.

Primary scope:

- Stabilize non-cumulative badge evaluation and progress tracking
- Unify achievement/challenge tracking logic with badge logic
- Consolidate award side-effect processing

Hard scope boundary:

- Do not change cumulative badge behavior/state-machine outcomes

Companion docs:

- [GAMIFICATION_UNIFIED_TARGET_TRACKING_IN-PROCESS.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_IN-PROCESS.md)
- [GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE0_DEEP_DIVE.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE0_DEEP_DIVE.md)

---

## Platinum quality targets for this initiative

### Engineering quality

- Zero mypy errors in updated modules
- No duplicated side-effect emission for same business event
- Single-source context contract between manager and engine
- Shared evaluation primitives used across badges/achievements/challenges
- No dead code left unresolved (removed or explicitly retained with rationale)

### Testing quality

- Deterministic tests for all identified failure modes (F1-F10)
- Cumulative regression parity maintained (no behavior changes)
- Coverage increase in engine/manager gamification paths
- Performance remains within current thresholds for stress scenario

### Documentation quality

- Updated architecture notes with explicit manager↔engine contract
- Findings-to-fix traceability table complete
- Completion check evidence attached (commands + outcomes)

---

## Findings-to-remediation traceability

| Finding                                          | Remediation package                                      | Priority |
| ------------------------------------------------ | -------------------------------------------------------- | -------- |
| F1 context missing keys for engine               | WP1 Context Contract + WP2 Badge Runtime Context Builder | P0       |
| F2 achievement/challenge progress shape mismatch | WP1 Context Contract + WP4 Unified Target Adapter        | P0       |
| F3 duplicate achievement/challenge emits         | WP5 Event Ownership Normalization                        | P0       |
| F4 evaluator duplication (achievement/challenge) | WP4 Unified Target Adapter + WP6 Engine Unification      | P1       |
| F5 award manifest duplication                    | WP3 Award Manifest Consolidation                         | P1       |
| F6 orphan `update_streak_progress`               | WP8 Dead Code Resolution                                 | P1       |
| F7 orphan `award_badge`                          | WP8 Dead Code Resolution                                 | P1       |
| F8 orphan `demote_cumulative_badge`              | WP8 Dead Code Resolution                                 | P2       |
| F9 orphan `_get_challenge_total`                 | WP8 Dead Code Resolution                                 | P2       |
| F10 manager over-breadth risk                    | Deferred to follow-up initiative (non-blocking)          | P3       |

---

## Work packages

## WP1 — Canonical evaluation context contract (P0)

### Goal

Define and enforce one context schema that manager always builds and engine always consumes.

### Files

- [custom_components/kidschores/type_defs.py](../../custom_components/kidschores/type_defs.py)
- [custom_components/kidschores/managers/gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
- [custom_components/kidschores/engines/gamification_engine.py](../../custom_components/kidschores/engines/gamification_engine.py)

### Steps

- [ ] Add/normalize typed sub-structures in `EvaluationContext` for:
  - current item progress (`current_badge_progress`)
  - daily snapshots (`today_stats`, `today_completion`, `today_completion_due`)
  - normalized achievement/challenge progress maps
- [ ] Document required vs optional keys directly in type docs and engine docstring
- [ ] Add manager helper to create a complete base context + per-item runtime overlay
- [ ] Ensure all engine entrypoints receive the fully expected shape

### Acceptance criteria

- Every key read in engine has a deterministic manager source
- No context reads fall back to empty defaults for expected required keys
- Type definitions match runtime payload shapes exactly

### Tests

- Add explicit context-shape unit tests in [tests/test_gamification_engine.py](../../tests/test_gamification_engine.py)
- Add manager context-builder tests in a manager workflow test file (or new dedicated gamification manager test)

---

## WP2 — Non-cumulative badge runtime context builder (P0)

### Goal

Build per-badge runtime context before each badge evaluation.

### Files

- [custom_components/kidschores/managers/gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
- [custom_components/kidschores/managers/statistics_manager.py](../../custom_components/kidschores/managers/statistics_manager.py)

### Steps

- [ ] Add manager helper (for example `_build_badge_runtime_context`) that merges:
  - base evaluation context
  - `current_badge_progress` for current badge id
  - daily stats keys required by engine (`today_points`, `today_approved`, `total_earned`, `streak_yesterday`)
  - completion snapshots (`approved_count`, `total_count`, `has_overdue`) for both all and due-only
- [ ] Reuse existing tracked-chore helper when constructing completion snapshots
- [ ] Use this runtime context in `_evaluate_periodic_badge` and any non-cumulative badge path

### Acceptance criteria

- Badge evaluation inputs are complete and deterministic
- Re-evaluation on same day does not produce drift from missing context data

### Tests

- Add parameterized tests for each target family (`points`, `chore_count`, `days_*`, `streak_*`) with runtime context assertions

---

## WP3 — Shared award manifest consolidation (P1)

### Goal

Guarantee one manifest build path for badge award side effects.

### Files

- [custom_components/kidschores/managers/gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
- [custom_components/kidschores/type_defs.py](../../custom_components/kidschores/type_defs.py)

### Steps

- [ ] Keep `process_award_items` + `_build_badge_award_manifest` as canonical shared path
- [ ] Remove duplicated inline manifest assembly from manual award path and route through helper
- [ ] Define a single typed manifest shape and enforce for all badge emit sites
- [ ] Verify reward/economy listeners consume identical payload shape across all award origins

### Acceptance criteria

- All badge emit sites use one manifest builder
- No payload-shape divergence between automatic and manual award paths

### Tests

- Add unit tests for manifest builder edge cases (unknown ids, missing awards, empty lists)
- Add integration test proving reward/economy handlers fire once with expected fields

---

## WP4 — Unified target adapter for achievements/challenges (P0)

### Goal

Map achievement/challenge configuration to badge-like target definition and shared evaluator path.

### Files

- [custom_components/kidschores/managers/gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
- [custom_components/kidschores/type_defs.py](../../custom_components/kidschores/type_defs.py)
- [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py)

### Steps

- [ ] Introduce adapter methods:
  - achievement -> canonical target
  - challenge -> canonical target + active window guard
- [ ] Normalize progress shape before engine call
- [ ] Add adapter support for achievement badge-award-count targets (new target source)
- [ ] Keep lifecycle differences in manager wrappers:
  - achievements: permanent once awarded
  - challenges: only active inside start/end window

### Acceptance criteria

- Achievements/challenges use same criterion engine semantics as badges
- Progress tracking updates are consistent and idempotent
- Badge-award-count target supported for achievements

### Tests

- Add mapped-target tests for achievement/challenge parity against badge behavior
- Add date-window tests for challenges (before/inside/after window)

---

## WP5 — Event ownership normalization (P0)

### Goal

Ensure exactly one event emission for each award completion domain event.

### Files

- [custom_components/kidschores/managers/gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
- [custom_components/kidschores/managers/notification_manager.py](../../custom_components/kidschores/managers/notification_manager.py)
- [custom_components/kidschores/managers/economy_manager.py](../../custom_components/kidschores/managers/economy_manager.py)
- [custom_components/kidschores/type_defs.py](../../custom_components/kidschores/type_defs.py)

### Steps

- [ ] Select single owner emission point for achievement/challenge completion
- [ ] Remove duplicate emit call(s) from non-owner path
- [ ] Align event payload typing and field naming in type definitions and emission code
- [ ] Verify listeners remain functionally unchanged except duplicate suppression

### Acceptance criteria

- Each completion triggers one event emission
- Notifications and point deposits are not duplicated

### Tests

- Add regression tests for “exactly one notification” and “exactly one deposit” per achievement/challenge completion

---

## WP6 — Engine unification and cleanup (P1)

### Goal

Reduce evaluator duplication while preserving behavior.

### Files

- [custom_components/kidschores/engines/gamification_engine.py](../../custom_components/kidschores/engines/gamification_engine.py)

### Steps

- [ ] Extract shared mini-primitives for:
  - threshold/progress/reason assembly
  - daily minimum checks
  - total-with-baseline and total-without-baseline checks
- [ ] Refactor `evaluate_achievement` and `evaluate_challenge` to use shared internals
- [ ] Keep public entrypoint signatures stable

### Acceptance criteria

- No behavior regressions in existing tests
- Reduced duplicate branching and reason assembly code

### Tests

- Keep current test semantics; add targeted parity assertions for refactored branches

---

## WP7 — Idempotent progress mutation rules (P0)

### Goal

Prevent double increment / incorrect reset on re-evaluation and undo paths.

### Files

- [custom_components/kidschores/managers/gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
- [custom_components/kidschores/type_defs.py](../../custom_components/kidschores/type_defs.py)

### Steps

- [ ] Define one mutation policy keyed by `today_iso` + `last_update_day`
- [ ] Apply policy consistently for day-count and streak updates
- [ ] Ensure undo/disapproval/overdue transitions can reverse same-day increment safely

### Acceptance criteria

- Same-day repeated evaluation is idempotent
- Undo/regression paths do not corrupt counters

### Tests

- Add sequence tests: approve → evaluate → re-evaluate → undo → re-evaluate

---

## WP8 — Dead/orphan code resolution (P1/P2)

### Goal

Eliminate or explicitly retain uncertain methods with rationale.

### Candidate list

- [update_streak_progress](../../custom_components/kidschores/managers/gamification_manager.py#L481)
- [award_badge](../../custom_components/kidschores/managers/gamification_manager.py#L2840)
- [demote_cumulative_badge](../../custom_components/kidschores/managers/gamification_manager.py#L2371)
- [\_get_challenge_total](../../custom_components/kidschores/engines/gamification_engine.py#L1092)

### Steps

- [ ] For each candidate, decide:
  - remove (unreferenced + no external API contract)
  - retain (documented public API or upcoming use)
- [ ] If retained, add explicit docstring note: “external API / forward-use contract”
- [ ] If removed, add changelog/release note if user-facing API impact exists

### Acceptance criteria

- No ambiguous orphan methods remain undocumented
- Repository search confirms intended references

---

## WP9 — Cumulative freeze guardrails (P0)

### Goal

Guarantee cumulative behavior remains unchanged.

### Files

- [custom_components/kidschores/managers/gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py)
- [tests/test_badge_cumulative.py](../../tests/test_badge_cumulative.py)

### Steps

- [ ] Add explicit in-file refactor guard comments around cumulative state machine entrypoints
- [ ] Keep cumulative methods untouched except safe interface wiring if required
- [ ] Run cumulative test suite before and after each major refactor batch

### Acceptance criteria

- Cumulative tests remain green and unchanged in expectation

---

## WP10 — Test strategy and gates (P0)

### Targeted tests to add/update

- Engine:
  - [tests/test_gamification_engine.py](../../tests/test_gamification_engine.py)
- Manager / integration behavior:
  - [tests/test_gamification_shadow_comparison.py](../../tests/test_gamification_shadow_comparison.py)
  - new manager workflow tests (or extension of existing workflow suites)
- Cumulative regression:
  - [tests/test_badge_cumulative.py](../../tests/test_badge_cumulative.py)

### Mandatory validation commands (definition of done)

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/kidschores/`
- `python -m pytest tests/ -v --tb=line`

### Recommended additional checks

- `mypy tests/`
- `python -m pytest tests/test_performance_comprehensive.py -s --tb=short`

### Exit criteria

- All P0/P1 work packages complete
- No critical or high findings open
- Cumulative regression unchanged
- Full quality gates green

---

## Implementation sequencing

### Sequence A (stabilize correctness first)

1. WP1 (context contract)
2. WP2 (runtime context builder)
3. WP5 (event ownership)
4. WP7 (idempotent mutation)

### Sequence B (unify and optimize)

5. WP4 (target adapter)
6. WP3 (award manifest consolidation)
7. WP6 (engine cleanup)
8. WP8 (dead/orphan resolution)

### Sequence C (safety and release)

9. WP9 (cumulative freeze verification)
10. WP10 (full gates + documentation)

---

## Builder-ready task checklist

- [ ] Context contract table implemented and referenced in code comments
- [ ] Engine-required keys populated by manager for every evaluation call
- [ ] Achievement/challenge progress maps normalized before evaluation
- [ ] Duplicate emits removed (single owner per event)
- [ ] All badge award emits use canonical manifest helper
- [ ] Dead/orphan candidates resolved with explicit rationale
- [ ] Cumulative path unchanged and validated
- [ ] All quality gates pass

---

## Risk register and mitigations

| Risk                                              | Impact | Mitigation                                                  |
| ------------------------------------------------- | ------ | ----------------------------------------------------------- |
| Context contract changes alter badge outcomes     | High   | Ship contract tests first; compare before/after snapshots   |
| Event de-dup breaks downstream listeners          | High   | Add event-count assertions + listener integration tests     |
| Adapter mapping introduces semantics drift        | Medium | Add parity tests against current intended behavior examples |
| Dead-code removal breaks hidden service/API usage | Medium | Search call graph + service registration before removal     |
| Refactor touches cumulative paths accidentally    | High   | Freeze guardrails + cumulative suite at each checkpoint     |

---

## Documentation updates required at completion

- Update architecture notes in [docs/ARCHITECTURE.md](../ARCHITECTURE.md):
  - manager↔engine contract
  - event ownership model
  - shared target adapter model
- Update initiative summary in [GAMIFICATION_UNIFIED_TARGET_TRACKING_IN-PROCESS.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_IN-PROCESS.md)
- Mark deep-dive findings resolved in [GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE0_DEEP_DIVE.md](GAMIFICATION_UNIFIED_TARGET_TRACKING_SUP_PHASE0_DEEP_DIVE.md)
