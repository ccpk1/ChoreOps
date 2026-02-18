# Supporting Doc: ChoreOps data model unification critical review

## Purpose

Identify high-leverage opportunities and hidden failure modes in the Option 3 plan, then define concrete mitigation checkpoints for execution.

## Scope assessed

- Main plan: [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md](CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md)
- Integration surfaces reviewed:
  - authorization and parent checks
  - shadow-link workflows
  - migration and startup integrity path
  - manager/platform entity creation pathways
  - tests and fixtures touching kid/parent semantics

## Biggest opportunities

### 1) Replace role labels with capability contracts

- Opportunity: avoid future confusion by modeling permissions as capabilities (`can_approve`, `can_manage`, `can_be_assigned`) rather than persona labels.
- Value: clean support for hybrid users and less coupling between UI labels and backend logic.

### 2) Keep migration mechanically simple

- Opportunity: kid-first rename keeps nested progress/history untouched and reduces transform risk.
- Value: lower migration complexity and fewer data-loss paths.

### 3) Centralize auth decisions early

- Opportunity: consolidate checks now in auth helpers and manager entrypoints.
- Value: prevents permission drift where one service uses old parent semantics and another uses new capability semantics.

### 4) Introduce compatibility contract tests before broad refactor

- Opportunity: write targeted migration + authorization parity tests first.
- Value: catches regressions while refactor is still small.

## Critical traps and mitigations

### Trap A: Capability inference from assignment links

- Risk: deriving approver status from assignment relationships causes unstable permissions and accidental privilege changes.
- Mitigation:
  - Persist `can_approve` and `can_manage` explicitly.
  - Add test: assignment changes must not alter approval capability.

### Trap B: `ha_user_id` and capability source ambiguity

- Risk: mixing Home Assistant `user.is_admin` runtime checks with stored capability checks creates contradictory behavior.
- Mitigation:
  - Define strict precedence contract:
    1) HA admin runtime override,
    2) stored capabilities,
    3) deny.
  - Apply uniformly in auth helpers and service handlers.

### Trap C: ID collision during parent merge

- Risk: kid and parent IDs are generated independently today; collisions are unlikely but must be handled deterministically.
- Mitigation:
  - During standalone parent creation in `users`, detect existing key collisions.
  - If collision exists, generate a new ID and record a migration remap log entry.

### Trap D: Partial migration persistence

- Risk: writing migrated data before all transforms succeed can leave storage in inconsistent intermediate state.
- Mitigation:
  - Build transformed structure in memory first, validate invariants, persist once.
  - Keep startup recovery backup before migration write.

### Trap E: Hidden API breakage in service/event payloads

- Risk: changing variable names to `user_id` while service payloads/events still expect legacy key names can break automations.
- Mitigation:
  - Keep external service schemas stable for one compatibility window.
  - Add payload alias layer and deprecation warnings before hard removal.

### Trap F: Entity registry and unique ID churn

- Risk: broad renames can accidentally change unique_id composition and orphan entities.
- Mitigation:
  - Preserve unique_id shape where possible.
  - If changes are required, add explicit registry migration routine and targeted tests.

### Trap G: Notification action payload drift

- Risk: notification action handlers parse encoded payloads with legacy semantics (`kid_id` segment); incompatible updates break mobile approval actions.
- Mitigation:
  - Support both payload forms during transition.
  - Add focused tests for chore/reward approve/disapprove action parsing.

### Trap H: Test migration underestimation

- Risk: semantic rename (`kid`→`user`) can trigger large fixture/helper churn not captured by unit test counts.
- Mitigation:
  - Migrate tests in staged batches (helpers first, migration tests second, workflow suites third).
  - Run full suite at each stage boundary, not just at the end.

## Additional gaps to add to the main plan

- Add explicit phase task: service schema compatibility window and deprecation schedule.
- Add explicit phase task: unique_id/entity-registry stability review.
- Add explicit phase task: notification action payload compatibility tests.
- Add explicit phase task: ID collision policy during merge.

## Suggested execution gates

### Gate 1 (end of Phase 1)

- Constants and capability contract frozen.
- Authorization precedence documented and approved.

### Gate 2 (end of Phase 2)

- Migration idempotency proven by repeated startup test.
- No data-loss on representative fixtures (kids-only, parents-only, mixed shadow setups).

### Gate 3 (mid Phase 3)

- Auth helper and service handlers fully moved to capabilities.
- Shadow-link logic disabled or compatibility-shimmed with tests.

### Gate 4 (release gate)

- Full quality gates pass.
- Migration-path and compatibility tests pass.
- Release notes include behavior and schema migration guidance.

## Decision quality scorecard (current plan readiness)

| Area | Status | Confidence | Notes |
| --- | --- | --- | --- |
| Strategy clarity | Strong | High | Option 3 choice and migration method are clear |
| Role model clarity | Improved | Medium-high | Needs strict auth precedence codification |
| Migration safety | Good | Medium | Needs collision policy + one-write atomic pattern tests |
| API compatibility | Incomplete | Medium-low | Needs explicit compatibility/deprecation step |
| Test readiness | Good | Medium | Sequencing is defined, workload still large |

## Recommended immediate additions before implementation starts

1. Lock auth precedence contract in architecture docs.
2. Add merge collision policy and event/schema compatibility tasks to phase checklist.
3. Create first PR scope as “constants + migration harness + parity tests only” before full rename wave.
