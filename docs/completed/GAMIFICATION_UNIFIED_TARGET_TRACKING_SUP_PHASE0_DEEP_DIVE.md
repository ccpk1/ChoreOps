# Phase 0 deep dive: gamification manager + engine

## Scope

- Files reviewed:
  - [custom_components/choreops/managers/gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py)
  - [custom_components/choreops/engines/gamification_engine.py](../../custom_components/choreops/engines/gamification_engine.py)
- Goal: identify orphan/dead code, duplicate logic, data-shape drift, and refactor opportunities for unified tracking.
- Constraint: cumulative behavior remains frozen for this initiative.

## Executive summary

- High-risk correctness gaps were found in manager↔engine context plumbing and achievement/challenge tracking shape.
- Duplicate event emission exists for achievement/challenge award paths and can trigger duplicate notifications.
- Several methods are strong dead/orphan candidates and should be explicitly classified before refactor.
- Award manifest building is partially duplicated and should be centralized as shared cross-goal award processing.

## Method inventory classification

### A) Type-specific (keep isolated)

- Cumulative badge state machine and maintenance transitions:
  - [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L809-L1312)
- Cumulative tier/progress selection helpers:
  - [get_cumulative_badge_levels](../../custom_components/choreops/managers/gamification_manager.py#L1862)
  - [get_cumulative_badge_progress](../../custom_components/choreops/managers/gamification_manager.py#L2211)
- Engine cumulative criterion:
  - [\_evaluate_cumulative_points](../../custom_components/choreops/engines/gamification_engine.py#L517)

### B) Shared evaluation core candidates

- Badge criterion routing + registry:
  - [evaluate_badge](../../custom_components/choreops/engines/gamification_engine.py#L174)
  - [\_register_handlers](../../custom_components/choreops/engines/gamification_engine.py#L103)
- Common daily/streak predicate families:
  - [\_evaluate_daily_completion](../../custom_components/choreops/engines/gamification_engine.py#L647)
  - [\_evaluate_streak](../../custom_components/choreops/engines/gamification_engine.py#L841)
- Achievement/challenge evaluators with near-identical structure:
  - [evaluate_achievement](../../custom_components/choreops/engines/gamification_engine.py#L273)
  - [evaluate_challenge](../../custom_components/choreops/engines/gamification_engine.py#L361)

### C) Shared award-processing candidates

- Award item parsing + manifest build:
  - [process_award_items](../../custom_components/choreops/managers/gamification_manager.py#L1738)
  - [\_build_badge_award_manifest](../../custom_components/choreops/managers/gamification_manager.py#L1776)
- Repeated emit blocks for badge award paths:
  - [periodic/cumulative emit sites](../../custom_components/choreops/managers/gamification_manager.py#L1056-L1416)
  - [manual award path](../../custom_components/choreops/managers/gamification_manager.py#L2840-L2893)

## Findings matrix (phase-0)

| ID  | Severity | Category               | Finding                                                                                                                                                                         | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Why it matters                                                                                             | Phase-0 action                                                             |
| --- | -------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| F1  | Critical | Data-shape drift       | Engine expects per-badge context keys (`current_badge_progress`, `today_stats`, `today_completion`, `today_completion_due`), but manager context builder does not populate them | Engine reads: [gamification_engine.py](../../custom_components/choreops/engines/gamification_engine.py#L492-L694); manager builder: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L1572-L1648)                                                                                                                                                                                                         | Non-cumulative criteria can evaluate against default zeros, creating false negatives and unstable behavior | Add explicit context-population inventory + contract table before refactor |
| F2  | Critical | Data-shape drift       | Achievement/challenge tracking object shape mismatch between manager-built context and engine reads                                                                             | Manager sets `achievement_progress[ach_id] = ach_progress[kid_id]`: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L1609-L1621); engine reads nested `.get(achievement_id, {}).get(kid_id)`: [gamification_engine.py](../../custom_components/choreops/engines/gamification_engine.py#L297-L301), [gamification_engine.py](../../custom_components/choreops/engines/gamification_engine.py#L420-L424) | Progress/baseline/streak tracking can be silently ignored                                                  | Normalize context schema and add strict typed adapter step                 |
| F3  | High     | Duplicate side effects | Achievement/challenge events are emitted twice in one award path                                                                                                                | Emit in `award_achievement`/`award_challenge`: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L415-L473); emitted again in `_apply_achievement_result`/`_apply_challenge_result`: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L1489-L1561)                                                                                                              | Notification handlers react to each emit, so duplicate user notifications are likely                       | Consolidate to single emit source and document ownership                   |
| F4  | High     | Duplicate logic        | Achievement/challenge evaluators duplicate flow (date gate/type branch/progress/reason/result assembly)                                                                         | [evaluate_achievement](../../custom_components/choreops/engines/gamification_engine.py#L273-L358), [evaluate_challenge](../../custom_components/choreops/engines/gamification_engine.py#L361-L468)                                                                                                                                                                                                                                                   | Increases drift risk and blocks unification to badge-like targets                                          | Introduce common evaluator skeleton + type mapping layer                   |
| F5  | Medium   | Duplicate logic        | Badge award manifest construction duplicated between helper and manual award path                                                                                               | Helper: [\_build_badge_award_manifest](../../custom_components/choreops/managers/gamification_manager.py#L1776); manual duplicate logic: [award_badge](../../custom_components/choreops/managers/gamification_manager.py#L2870-L2893)                                                                                                                                                                                                                | Inconsistent future changes likely (fields, defaults)                                                      | Route all manifest creation through single helper                          |
| F6  | Medium   | Dead/orphan candidate  | `update_streak_progress` appears unreferenced                                                                                                                                   | Definition: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L481); repository usage scan found no calls                                                                                                                                                                                                                                                                                                    | Maintenance burden and confusion against new streak logic                                                  | Mark for deprecation/removal decision in phase-0 inventory                 |
| F7  | Medium   | Dead/orphan candidate  | `award_badge` appears unreferenced by services/workflows                                                                                                                        | Definition only: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L2840)                                                                                                                                                                                                                                                                                                                                    | Public API surface without caller guarantees                                                               | Confirm intended external use; remove or wire explicit call site           |
| F8  | Medium   | Dead/orphan candidate  | `demote_cumulative_badge` appears unreferenced                                                                                                                                  | Definition only: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L2371)                                                                                                                                                                                                                                                                                                                                    | Extra path can diverge from unified cumulative state machine                                               | Keep or remove based on service/API contract                               |
| F9  | Medium   | Dead/orphan candidate  | `_get_challenge_total` is effectively unused by active challenge evaluation                                                                                                     | Defined: [gamification_engine.py](../../custom_components/choreops/engines/gamification_engine.py#L1092), but challenge evaluation uses tracking count directly                                                                                                                                                                                                                                                                                        | Legacy helper increases cognitive load                                                                     | Remove or repurpose in unified target mapping                              |
| F10 | Medium   | Cohesion               | Manager owns both orchestration and large CRUD/reset surfaces                                                                                                                   | CRUD + reset sections in [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L3259-L4024)                                                                                                                                                                                                                                                                                                                      | Harder to reason about evaluation correctness during refactor                                              | Keep out-of-scope for phase-0 changes, but document split candidate        |

## Dead/orphan candidate short list

- Strong candidates (no confirmed caller in current repo):
  - [update_streak_progress](../../custom_components/choreops/managers/gamification_manager.py#L481)
  - [award_badge](../../custom_components/choreops/managers/gamification_manager.py#L2840)
  - [demote_cumulative_badge](../../custom_components/choreops/managers/gamification_manager.py#L2371)
  - [\_get_challenge_total](../../custom_components/choreops/engines/gamification_engine.py#L1092)

## Duplication hotspots to target first

1. Achievement/challenge result pipeline duplication:
   - Manager apply methods: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L1461-L1566)
   - Engine evaluators: [gamification_engine.py](../../custom_components/choreops/engines/gamification_engine.py#L273-L468)
2. Badge award payload duplication:
   - Manifest helper + manual path split: [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L1776-L1807), [gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L2870-L2893)
3. Daily vs streak variant wrappers (many thin wrappers):
   - [gamification_engine.py](../../custom_components/choreops/engines/gamification_engine.py#L743-L983)

## Phase-0 decisions to lock before implementation

- Define canonical evaluation context schema and adapter responsibilities (manager must populate all engine-required keys).
- Define single event emission owner for achievement/challenge award completion.
- Define which dead/orphan candidates are removed vs retained as explicit public API.
- Define shared award manifest contract for badge/achievement/challenge parity.

## Immediate next artifacts

- Add a phase-0 method inventory table into the main initiative plan with statuses: keep/type-specific, unify/shared, deprecate/remove.
- Add a test gap matrix specifically for the F1/F2/F3 issues before behavior refactor.
