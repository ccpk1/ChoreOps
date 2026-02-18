# Supporting Doc: ChoreOps data model unification decision matrix

## Purpose

Provide a decision-ready comparison between Option 2 (Storage Adapter) and Option 3 (Full Unification) with explicit effort, risk, staffing, and execution pathways so product and architecture can choose intentionally.

## Decision scope

- In scope: backend model strategy for replacing the kid/parent split and shadow-link workaround.
- Out of scope: frontend naming polish, non-blocking UX enhancements, and unrelated technical debt.

## Candidate options

### Option 2 — Storage Adapter

- Storage migrates to unified records.
- Runtime adapter keeps existing `kids_data` and `parents_data` pathways intact temporarily.
- Logic refactor happens incrementally post-release.

### Option 3 — Full Unification now

- Replace split model end-to-end in one major implementation wave.
- Remove shadow-link pathway and dual-model branching.
- Managers, helpers, entities, services, and tests all move together.

## Weighted decision matrix

Scoring: 1 (worst) to 5 (best). Weights reflect current release constraints and reliability priorities.

| Criterion                      |  Weight | Option 2 score | Option 2 weighted | Option 3 score | Option 3 weighted | Notes                                               |
| ------------------------------ | ------: | -------------: | ----------------: | -------------: | ----------------: | --------------------------------------------------- |
| Time-to-ship                   |      25 |              4 |               100 |              2 |                50 | Option 2 reduces immediate rewrite scope            |
| Regression risk                |      25 |              4 |               100 |              2 |                50 | Option 3 touches nearly all behavior surfaces       |
| Long-term architecture quality |      20 |              3 |                60 |              5 |               100 | Option 3 is architecturally cleaner                 |
| Team cognitive load            |      10 |              4 |                40 |              2 |                20 | Option 3 requires parallel deep context             |
| Migration/rollback safety      |      10 |              4 |                40 |              2 |                20 | Option 2 isolates migration from full logic rewrite |
| Test rewrite burden            |      10 |              4 |                40 |              1 |                10 | Option 3 materially increases immediate test churn  |
| **Total**                      | **100** |                |           **380** |                |           **250** | Option 2 favored under current constraints          |

## What Option 3 actually takes

This is the concrete commitment if you choose to “bite the bullet now.”

### Required delivery shape

- Workstream A: data model and migration core
  - New unified record schema, migration, idempotency, rollback guardrails.
- Workstream B: business logic convergence
  - Manager and helper rewrites to capability-driven logic (no split branches).
- Workstream C: platform/entity convergence
  - Entity setup and behavior updates for sensors/buttons/select/calendar/datetime.
- Workstream D: testing and hardening
  - High-volume test updates, migration-path tests, and service/auth regression suites.

### Estimated implementation envelope (Option 3)

- Engineering time: ~40–50 hours for code-path refactor + migration core.
- Validation and stabilization: +20–30 hours likely (test updates, bug hunts, edge cases).
- Realistic calendar duration:
  - 1 senior maintainer alone: 2.5–4 weeks.
  - 2 maintainers in parallel: 1.5–2.5 weeks.

### Entry criteria before starting Option 3

- Term and schema contract frozen (no naming churn during implementation).
- Release flexibility accepted (explicitly tolerate schedule slip).
- Dedicated test update capacity identified up front.
- Stakeholder agreement on temporary feature freeze for unrelated work.

### Exit criteria for Option 3 done

- No writes to split storage keys remain.
- Shadow-link behavior removed or mapped to no-op compatibility path with deprecation note.
- All manager workflows run via unified record model.
- Full quality gates pass and migration-path tests pass from representative legacy fixtures.

## How to take on Option 3 safely (if chosen)

### Phase 0 (2–3 days) — de-risk sprint

- Build a short-lived proof branch with:
  - unified schema draft,
  - one manager converted fully,
  - one end-to-end workflow test migrated.
- Objective: validate complexity assumptions before full commitment.

Go/no-go checkpoint after Phase 0:

- Go to Option 3 only if:
  - converted manager diff is reviewable,
  - migration path is idempotent,
  - test rewrite pattern is repeatable.
- Otherwise pivot back to Option 2.

### Phase 1 — foundation

- Implement schema migration and compatibility harness.
- Add migration telemetry and backup checkpoints.

### Phase 2 — core rewrites

- Convert managers in dependency order:
  1. User manager
  2. Chore/reward managers
  3. Gamification/statistics/system helpers

### Phase 3 — entity/platform convergence

- Convert entity creation and authorization branching to unified capabilities.

### Phase 4 — test and release hardening

- Update integration tests in focused batches, then run full suite.

## If you stay with Option 2 now

Option 2 can still preserve a path to Option 3 without wasted work if these guardrails are enforced:

- Adapter layer has explicit expiration criteria and owners.
- New code is prohibited from adding fresh split-model assumptions.
- Every post-release feature touching user identity moves one subsystem from split to unified logic.
- A dated deprecation target for shadow-link logic is documented.

## Decision workshop template (for your active involvement)

Use this in a 45-minute decision meeting.

1. Confirm non-negotiables (10 min)
   - Is schedule certainty more important than architectural purity right now?
   - Is a 2–4 week dedicated refactor window acceptable?
2. Score criteria together (15 min)
   - Re-score the matrix weights as a team.
3. Capacity reality check (10 min)
   - Who does migration core, who does tests, who handles regressions?
4. Decide and lock execution mode (10 min)
   - Choose Option 2 or Option 3.
   - Capture entry/exit criteria and owner sign-off in the main initiative plan.

## Recommendation framing

- If your priority is reliable release velocity with controlled risk: choose Option 2 now, with strict anti-drift guardrails.
- If your priority is architectural reset now and you can absorb a schedule hit plus concentrated stabilization: choose Option 3, but only after a Phase 0 go/no-go spike.
