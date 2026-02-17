# Test Scenarios: Chore Timer Refactor

Supporting document for [CHORE_TIMER_REFACTOR_IN-PROCESS.md](CHORE_TIMER_REFACTOR_IN-PROCESS.md)

## Test Matrix Overview

The 4 configuration dimensions create a large matrix. This document defines the **valid** combinations and expected behaviors.

### Dimension Summary

| Dimension               | Options                                                                                   | Count |
| ----------------------- | ----------------------------------------------------------------------------------------- | ----- |
| approval_reset_type     | AT_MIDNIGHT_ONCE, AT_MIDNIGHT_MULTI, AT_DUE_DATE_ONCE, AT_DUE_DATE_MULTI, UPON_COMPLETION | 5     |
| overdue_handling        | AT_DUE_DATE, NEVER_OVERDUE, CLEAR_AT_APPROVAL_RESET, CLEAR_IMMEDIATE_ON_LATE              | 4     |
| pending_claims_handling | HOLD, CLEAR, AUTO_APPROVE                                                                 | 3     |
| completion_criteria     | INDEPENDENT, SHARED, SHARED_FIRST                                                         | 3     |

**Total theoretical combinations**: 5 × 4 × 3 × 3 = 180

**Practical test scenarios**: ~25 (many combinations have identical behavior)

---

## Scenario Group 1: Approval Reset Type Scoping

### Scenario 1.1: Midnight trigger with AT*MIDNIGHT*\* chores

```yaml
name: "Midnight processes midnight-scoped chores"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: APPROVED
    expected_action: reset_and_reschedule
  - approval_reset_type: AT_DUE_DATE_ONCE
    state: APPROVED
    expected_action: skip # Not in scope for midnight
  - approval_reset_type: UPON_COMPLETION
    state: APPROVED
    expected_action: skip # Never timer-driven
```

### Scenario 1.2: Due date trigger with AT*DUE_DATE*\* chores

```yaml
name: "Due date trigger processes due-date-scoped chores"
trigger: due_date
chores:
  - approval_reset_type: AT_DUE_DATE_ONCE
    state: APPROVED
    expected_action: reset_and_reschedule
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: APPROVED
    expected_action: skip # Not in scope for due_date
```

### Scenario 1.3: UPON_COMPLETION never timer-triggered

```yaml
name: "UPON_COMPLETION chores skip timer processing"
trigger: midnight
chores:
  - approval_reset_type: UPON_COMPLETION
    state: APPROVED
    expected_action: skip
trigger: due_date
chores:
  - approval_reset_type: UPON_COMPLETION
    state: APPROVED
    expected_action: skip
```

---

## Scenario Group 2: State-Based Processing

### Scenario 2.1: PENDING state always skipped

```yaml
name: "PENDING chores skip processing"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: PENDING
    expected_action: skip # Future due date or nothing to do
```

### Scenario 2.2: APPROVED state triggers reset

```yaml
name: "APPROVED chores reset and reschedule"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: APPROVED
    has_due_date: true
    expected_action: reset_and_reschedule
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: APPROVED
    has_due_date: false # Daily without due date
    expected_action: reset_only # No due date to move
```

---

## Scenario Group 3: CLAIMED State with Pending Claims Handling

### Scenario 3.1: CLAIMED with HOLD

```yaml
name: "CLAIMED + HOLD preserves claim"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: CLAIMED
    pending_claims_handling: HOLD
    expected_action: hold # Skip, preserve claim
```

### Scenario 3.2: CLAIMED with CLEAR

```yaml
name: "CLAIMED + CLEAR discards and resets"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: CLAIMED
    pending_claims_handling: CLEAR
    expected_action: reset_and_reschedule # Discard claim, reset
```

### Scenario 3.3: CLAIMED with AUTO_APPROVE

```yaml
name: "CLAIMED + AUTO_APPROVE approves first then resets"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: CLAIMED
    pending_claims_handling: AUTO_APPROVE
    expected_action: auto_approve_then_reset
    expected_sequence:
      - approve_claim
      - reset_and_reschedule
```

---

## Scenario Group 4: OVERDUE State with Overdue Handling

### Scenario 4.1: OVERDUE with AT_DUE_DATE (hold until complete)

```yaml
name: "OVERDUE + AT_DUE_DATE holds until manually completed"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: OVERDUE
    overdue_handling: AT_DUE_DATE
    expected_action: hold # Stay overdue until user completes
```

### Scenario 4.2: OVERDUE with CLEAR_AT_APPROVAL_RESET

```yaml
name: "OVERDUE + CLEAR_AT_RESET clears at boundary"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: OVERDUE
    overdue_handling: CLEAR_AT_APPROVAL_RESET
    expected_action: reset_and_reschedule # Clear overdue, reset
```

### Scenario 4.3: OVERDUE with CLEAR_IMMEDIATE_ON_LATE

```yaml
name: "OVERDUE + CLEAR_IMMEDIATE already handled"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: OVERDUE # Shouldn't actually be OVERDUE with this setting
    overdue_handling: CLEAR_IMMEDIATE_ON_LATE
    expected_action: skip # Already cleared when due passed
```

### Scenario 4.4: OVERDUE with NEVER_OVERDUE

```yaml
name: "NEVER_OVERDUE chores can't be in OVERDUE state"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    state: OVERDUE # Invalid state for this setting
    overdue_handling: NEVER_OVERDUE
    expected_action: skip # Won't happen in practice
```

---

## Scenario Group 5: Completion Criteria Routing

### Scenario 5.1: INDEPENDENT processes per-kid

```yaml
name: "INDEPENDENT chores process each kid separately"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    completion_criteria: INDEPENDENT
    assigned_kids: [kid_1, kid_2]
    kid_states:
      kid_1: APPROVED
      kid_2: PENDING
    expected_actions:
      kid_1: reset_and_reschedule
      kid_2: skip # Still PENDING
```

### Scenario 5.2: SHARED processes chore-level

```yaml
name: "SHARED chores process at chore level"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    completion_criteria: SHARED
    state: APPROVED # Chore-level state
    assigned_kids: [kid_1, kid_2]
    expected_action: reset_and_reschedule # All kids reset together
```

### Scenario 5.3: SHARED_FIRST processes like SHARED

```yaml
name: "SHARED_FIRST processes at chore level"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    completion_criteria: SHARED_FIRST
    state: APPROVED
    expected_action: reset_and_reschedule
```

---

## Scenario Group 6: Special Cases

### Scenario 6.1: No due date (Daily/Weekly without date)

```yaml
name: "Chores without due date reset but don't reschedule"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    frequency: DAILY
    has_due_date: false
    state: APPROVED
    expected_action: reset_only # Reset state, no due date to move
```

### Scenario 6.2: Non-recurring approved stays approved

```yaml
name: "Non-recurring approved chores skip timer processing"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    frequency: NONE # Non-recurring
    state: APPROVED
    expected_action: skip # Stays approved until manual change
```

### Scenario 6.3: Non-recurring PENDING stays pending

```yaml
name: "Non-recurring PENDING chores skip timer processing"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    frequency: NONE
    state: PENDING
    expected_action: skip
```

---

## Scenario Group 7: Combined Edge Cases

### Scenario 7.1: INDEPENDENT + CLAIMED + HOLD (per-kid hold)

```yaml
name: "INDEPENDENT with mixed kid states and HOLD"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    completion_criteria: INDEPENDENT
    pending_claims_handling: HOLD
    assigned_kids: [kid_1, kid_2]
    kid_states:
      kid_1: CLAIMED # Has pending claim
      kid_2: APPROVED
    expected_actions:
      kid_1: hold # Preserve kid_1's claim
      kid_2: reset_and_reschedule # Reset kid_2
```

### Scenario 7.2: SHARED + CLAIMED + CLEAR (all kids affected)

```yaml
name: "SHARED CLAIMED with CLEAR affects all kids"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    completion_criteria: SHARED
    pending_claims_handling: CLEAR
    state: CLAIMED
    assigned_kids: [kid_1, kid_2]
    expected_action: reset_and_reschedule # All kids reset, claim discarded
```

### Scenario 7.3: OVERDUE + CLAIMED combination

```yaml
name: "OVERDUE takes precedence over CLAIMED in shared"
trigger: midnight
chores:
  - approval_reset_type: AT_MIDNIGHT_ONCE
    completion_criteria: SHARED
    state: OVERDUE # Chore-level is OVERDUE
    overdue_handling: AT_DUE_DATE
    pending_claims_handling: CLEAR
    expected_action: hold # OVERDUE handling takes precedence
```

---

## Test Implementation Notes

### Engine Tests (Pure Python)

- Test `is_in_boundary_scope()` with all approval_reset_type × trigger combinations
- Test `determine_boundary_action()` with state × config option matrix
- Test `categorize_for_boundary()` with real chore_info dicts

### Manager Integration Tests

- Use `scenario_medium` fixture as base
- Mock time to control trigger events
- Verify state transitions via entity states
- Verify due date changes via sensor attributes

### Service-Based Tests (Preferred)

- Use button presses to trigger chore actions
- Use `hass.bus.async_fire(SIGNAL_MIDNIGHT_ROLLOVER)` to simulate timers
- Assert final states, not intermediate calls

---

## Coverage Matrix

| Scenario | approval_reset  | state    | overdue_handling | pending_claims | completion  | Expected        |
| -------- | --------------- | -------- | ---------------- | -------------- | ----------- | --------------- |
| 1.1a     | AT*MIDNIGHT*\*  | APPROVED | \*               | \*             | \*          | reset           |
| 1.1b     | AT*DUE_DATE*\*  | APPROVED | \*               | \*             | \*          | skip (midnight) |
| 1.3      | UPON_COMPLETION | \*       | \*               | \*             | \*          | skip            |
| 2.1      | \*              | PENDING  | \*               | \*             | \*          | skip            |
| 3.1      | \*              | CLAIMED  | \*               | HOLD           | \*          | hold            |
| 3.2      | \*              | CLAIMED  | \*               | CLEAR          | \*          | reset           |
| 3.3      | \*              | CLAIMED  | \*               | AUTO_APPROVE   | \*          | approve+reset   |
| 4.1      | \*              | OVERDUE  | AT_DUE_DATE      | \*             | \*          | hold            |
| 4.2      | \*              | OVERDUE  | CLEAR_AT_RESET   | \*             | \*          | reset           |
| 5.1      | \*              | mixed    | \*               | \*             | INDEPENDENT | per-kid         |
| 5.2      | \*              | \*       | \*               | \*             | SHARED      | chore-level     |
| 6.1      | \*              | APPROVED | \*               | \*             | \* (no due) | reset_only      |
| 6.2      | \* (freq=NONE)  | APPROVED | \*               | \*             | \*          | skip            |
