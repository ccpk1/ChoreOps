# Initiative plan

## Initiative snapshot

- **Name / Code**: Post-implementation chore signal contract audit / `CHORE_SIGNAL_CONTRACT_AUDIT_POST_COMPLETED`
- **Target release / milestone**: Immediately after completed-display initiative validation
- **Owner / driver(s)**: ChoreOps maintainers (Architecture + QA)
- **Status**: Not started (deferred)

## Summary & immediate steps

| Phase / Step                  | Description                                                | % complete | Quick notes                        |
| ----------------------------- | ---------------------------------------------------------- | ---------- | ---------------------------------- |
| Phase 1 – Baseline capture    | Capture current signal semantics and per-assignee outcomes | 0%         | Read-only audit first              |
| Phase 2 – Contract definition | Define explicit post-settle actor/non-actor contracts      | 0%         | No behavior changes yet            |
| Phase 3 – Validation design   | Define test matrix and sentinel coverage strategy          | 0%         | Protect existing quality depth     |
| Phase 4 – Change proposal     | Propose follow-up enhancements (if needed)                 | 0%         | Separate implementation initiative |

1. **Objective** – Audit and formalize signal-to-visible-state contracts after minimal completed-display rollout.
2. **Constraint** – No implementation coupling with completed-display initiative.

## Scope boundaries

### In scope

- Signal semantics documentation and per-assignee post-settle contract definition.
- Test-matrix design for lifecycle/advisory signals.
- Gap analysis and prioritized enhancement proposals.

### Out of scope

- Any immediate implementation changes in this audit plan.
- Any retroactive expansion of minimal completed-display initiative.

## Detailed phase tracking

### Phase 1 – Baseline capture

- [ ] Capture emit sources, persist boundaries, and consumer assumptions for all chore signal families.
- [ ] Capture actor/non-actor state outcomes for shared-first and rotation branches.
- [ ] Capture advisory temporal signal semantics (`due_window`, `due_reminder`).

### Phase 2 – Contract definition

- [ ] Define strict/lifecycle/advisory contract categories with explicit per-assignee expected state/capability sets.
- [ ] Define acceptable post-settle state sets for each signal family.
- [ ] Define non-negotiable invariants and known intentional exceptions.

### Phase 3 – Validation design

- [ ] Build canonical scenario matrix with sentinel test requirements.
- [ ] Define anti-dilution guardrails for test updates.
- [ ] Define pass/fail rubric for contract conformance.

### Phase 4 – Change proposal

- [ ] Produce enhancement backlog with risk/benefit and sequencing recommendations.
- [ ] Propose implementation split (small, auditable increments).
- [ ] Prepare handoff to builder initiative for approved enhancements.

## Completion check

- [ ] Baseline documented
- [ ] Contract matrix approved
- [ ] Validation strategy approved
- [ ] Enhancement proposal approved
