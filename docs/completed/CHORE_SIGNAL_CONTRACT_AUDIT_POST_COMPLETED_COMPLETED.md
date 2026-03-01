# Initiative plan

## Initiative snapshot

- **Name / Code**: Post-implementation chore signal contract audit / `CHORE_SIGNAL_CONTRACT_AUDIT_POST_COMPLETED`
- **Target release / milestone**: Immediately after completed-display initiative validation
- **Owner / driver(s)**: ChoreOps maintainers (Architecture + QA)
- **Status**: Complete and archived (Phases 1-4 delivered)

## Summary

| Phase / Step                  | Description                                                | % complete | Quick notes                                                          |
| ----------------------------- | ---------------------------------------------------------- | ---------- | -------------------------------------------------------------------- |
| Phase 1 – Baseline capture    | Capture current signal semantics and per-assignee outcomes | 100%       | Baseline artifact completed with emit/persist/actor-non-actor matrix |
| Phase 2 – Contract definition | Define explicit post-settle actor/non-actor contracts      | 100%       | Contract matrix published with branch clauses and invariants         |
| Phase 3 – Validation design   | Define test matrix and sentinel coverage strategy          | 100%       | Sentinel matrix, guardrails, and pass/fail rubric documented         |
| Phase 4 – Change proposal     | Propose follow-up enhancements (if needed)                 | 100%       | Prioritized backlog and builder split proposal published             |

## Completion check

- [x] Baseline documented
- [x] Contract matrix approved
- [x] Validation strategy approved
- [x] Enhancement proposal approved

## Decisions captured

- Keep signal semantics stable by default; prioritize tests-first hardening.
- Treat S2/S3/S4/S9/S10 as mandatory sentinel additions before any behavioral
  signal-contract change.
- Split follow-up work into two Builder initiatives:
  - `CHORE_SIGNAL_CONTRACT_HARDENING_TESTS` (go)
  - `CHORE_SIGNAL_CONTRACT_SEMANTIC_REFINEMENTS` (deferred, explicit approval)

## Archived artifacts

- `docs/completed/CHORE_SIGNAL_CONTRACT_AUDIT_POST_COMPLETED_SUP_PHASE1_BASELINE.md`
- `docs/completed/CHORE_SIGNAL_CONTRACT_AUDIT_POST_COMPLETED_SUP_PHASE2_CONTRACT_MATRIX.md`
- `docs/completed/CHORE_SIGNAL_CONTRACT_AUDIT_POST_COMPLETED_SUP_PHASE3_VALIDATION_STRATEGY.md`
- `docs/completed/CHORE_SIGNAL_CONTRACT_AUDIT_POST_COMPLETED_SUP_PHASE4_CHANGE_PROPOSAL.md`

## References

- `docs/completed/CHORE_STATUS_COMPLETED_ALIAS_SENSOR_ONLY_COMPLETED.md`
- `docs/ARCHITECTURE.md`
- `docs/in-process/CHORE_STATUS_COMPLETED_ALIAS_SENSOR_ONLY_SUP_SIGNAL_UI_LOCKSTEP.md`
- `custom_components/choreops/managers/chore_manager.py`
- `custom_components/choreops/sensor.py`
- `tests/test_workflow_chores.py`
- `tests/test_rotation_fsm_states.py`
