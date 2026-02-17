## Top-10 Coverage Closure (Sensor-First, E2E)

Scope: close the highest-risk gaps in chore flows using tests that verify user-visible outcomes through chore status sensors, points sensors, and dashboard helper attributes.

Current focused coverage baseline:

- chore_manager.py: 74%
- chore_engine.py: 77%

### Priority ranking method

- Risk to user-visible behavior first (state drift, points drift, turn drift)
- Breadth of uncovered logic second (largest uncovered branches)
- Sensor-observable assertions required for every case

## Top 10 tests to add

1. Rotation auto-advance fallback ordering

- Target code: chore_manager.\_advance_rotation (large uncovered branch set)
- Test type: E2E workflow + midnight boundary trigger
- Assertions:
  - Turn holder changes in dashboard helper chore list for all kids
  - Exactly one kid shows claimable state, others show not_my_turn
  - No duplicate rotation advance effect after second midnight tick
- Candidate file: tests/test_rotation_fsm_states.py

2. Rotation manual reset + open cycle parity

- Target code: chore_manager.reset_rotation, set_rotation_turn, open_rotation_cycle
- Test type: service action + sensor verification
- Assertions:
  - Turn owner reflected in status sensors and helper attributes
  - Invalid/edge turn requests leave sensors unchanged (safety)
- Candidate file: tests/test_rotation_services.py

3. Independent undo_claim recovery path

- Target code: chore_manager.undo_claim
- Test type: claim -> undo -> re-claim -> approve
- Assertions:
  - Claimed to pending transition visible via chore status sensor
  - Pending claim count effects visible in claimability and helper list ordering
  - Points unchanged after undo; awarded once on final approval
- Candidate file: tests/test_workflow_chores.py

4. Due window + reminder state transitions at boundaries

- Target code: chore_manager.\_process_due_window, \_process_due_reminder
- Test type: freezer-driven boundary transitions
- Assertions:
  - Pending/in_due_window/due transitions reflected in dashboard helper state text
  - Reminder/due signals do not create state regression (no forced overdue)
- Candidate file: tests/test_chore_scheduling.py

5. Approval-period start reset invariants

- Target code: chore_manager.\_set_approval_period_start
- Test type: approval reset scenario with shared and independent chores
- Assertions:
  - Approval period start monotonic in helper attributes
  - Approval state is preserved/cleared exactly per reset type in sensor state
- Candidate file: tests/test_approval_reset_overdue_interaction.py

6. Data reset service end-to-end safety

- Target code: chore_manager.data_reset_chores
- Test type: service invocation across mixed chore types
- Assertions:
  - All chore status sensors return baseline pending/not_my_turn as configured
  - Points sensors and dashboard helper counts stay internally consistent
  - Rotation chores preserve valid turn semantics after reset
- Candidate file: tests/test_chore_services.py

7. Criteria transition action matrix (engine + manager lane parity)

- Target code: chore_engine.get_criteria_transition_actions, chore_manager.\_handle_criteria_transition
- Test type: matrix-driven workflow cases for independent/shared/shared_first
- Assertions:
  - Final user-visible state per kid matches expected matrix row
  - Shared-first blocking and release behavior visible in status sensors
- Candidate file: tests/test_chore_state_matrix.py

8. Global chore state aggregation edge cases

- Target code: chore_engine.compute_global_chore_state
- Test type: multi-kid mixed-state choreography
- Assertions:
  - Global state attribute on chore sensor aligns with helper rollup
  - Mixed states (approved + overdue + missed + waiting) produce deterministic global state
- Candidate file: tests/test_chore_state_matrix.py

9. Streak carryover and missed-gap calculation

- Target code: chore_engine.calculate_streak
- Test type: date progression with parent-lag approvals
- Assertions:
  - Current streak and missed streak attributes in sensors/helper align with expected schedule math
  - Late approval does not inflate streak incorrectly
- Candidate file: tests/test_workflow_chores.py

10. Approval-in-period boundary correctness

- Target code: chore_engine.is_approved_in_period, get_due_window_start
- Test type: tight boundary tests around period start/due window edges
- Assertions:
  - Approved/pending display state flips exactly at boundary timestamps
  - Dashboard helper chore entry state remains stable across reload/update cycle
- Candidate file: tests/test_chore_scheduling.py

## Best-in-class test contract (must-follow)

- Drive behavior via real workflow actions (button press/services/context), not direct state mutation except explicit scheduler setup hooks.
- Verify outcome through:
  - chore status sensors,
  - points sensors,
  - dashboard helper chore entries/attributes.
- Add paired parity where applicable:
  - approval-trigger lane vs periodic/midnight-trigger lane,
  - same scenario, same expected user-visible result.
- Include anti-regression assertions:
  - no duplicate event effect,
  - no stale overdue after reset+reschedule,
  - no hidden state drift after async_set_updated_data.

## Suggested execution order

1. Tests 1, 3, 6 (highest user-impact and largest manager gaps)
2. Tests 4, 5, 10 (boundary correctness and reset semantics)
3. Tests 7, 8, 9, 2 (matrix/depth completion and rotation service hardening)

## Expected outcome if completed

- chore_manager coverage trend: 74% -> low/mid 80s
- chore_engine coverage trend: 77% -> mid/high 80s
- Stronger confidence that UI-visible behavior remains correct across reset, boundary, and rotation edge cases.
