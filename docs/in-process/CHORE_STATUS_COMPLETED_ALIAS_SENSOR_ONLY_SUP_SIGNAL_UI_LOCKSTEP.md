# Chore signal ↔ UI state lockstep analysis

## Status in roadmap

- This document is retained as **deferred follow-up analysis**.
- It is **not implementation scope** for `CHORE_STATUS_COMPLETED_ALIAS_SENSOR_ONLY`.
- Execute this analysis only after the minimal completed-display + helper-key change is implemented and validated.

## Purpose

Expand alignment analysis from `completed` only to **all chore lifecycle signals** so event semantics and visible UI state remain predictably consistent.

## Contract timing policy (explicit)

- The required invariant is **post-settle alignment** after workflow processing completes.
- Validation boundary: after `await hass.async_block_till_done()` (or equivalent settled state checkpoint).
- Transient in-transaction state transitions are acceptable and are not considered contract violations.
- Goal: avoid overengineering for millisecond-level lockstep while guaranteeing final consistency.

## Why this matters

The integration emits signals after workflow mutations, and sensors/helper derive visible state from runtime context. If those contracts are not explicit, signals can be interpreted as implying a UI state that may no longer be visible after immediate reset branches.

## Authoritative state path (confirmed)

- Manager context provider: `get_chore_status_context()`
- Sensor display state: `AssigneeChoreStatusSensor.native_value` reads `CHORE_CTX_STATE`
- Helper state projection: dashboard helper chore item projection reads the same context path

This is the correct single-path foundation for UI state.

## Persist/emit ordering patterns found

### 1) Claimed flow

- Claim applies state transition to `claimed`, then may auto-approve.
- If `auto_approve` is enabled, `_approve_chore_locked()` runs first.
- `chore_claimed` is still emitted after that branch.

**Risk**: emitted `chore_claimed` may not correspond to a visible `claimed` state in auto-approve scenarios.

**Post-settle contract**: visible state must be valid for the completed branch outcome.

### 2) Approved/completed flow

- Approval mutates data, can trigger immediate reset decisions (`upon_completion`, late immediate clear).
- Persist/update occurs before emits.
- `chore_approved` and `chore_completed` can emit when visible state has already reset to `pending` in immediate-reset paths.

**Risk**: consumers may assume visible state equals `approved/completed` at emit time.

**Post-settle contract**: visible state must match branch-defined final state set.

### 3) Overdue/missed/reset flows

- Overdue batch processing persists before signal emission.
- Missed recording persists before signal emission.
- State reset transitions persist before reset signal emission.

These are generally closer to lockstep semantics.

**Post-settle contract**: strict equality expected.

### 4) Due-window/reminder flows

- Due signals are temporal advisory signals from scan windows.
- They are not guaranteed to imply a specific final sensor state (`due`) in all branches.

These should be documented as advisory, not strict state-equality signals.

**Post-settle contract**: validate temporal predicate consistency, not exact state equality.

### Due-window/reminder: current behavior vs recommendation

**Current behavior**

- `chore_due_window` and `chore_due_reminder` are emitted from scanner window classification in `ChoreManager`.
- They do not directly mutate chore state when emitted; they report timing context for notifications.
- A chore can receive these signals while visible state may still be `pending`, `waiting`, `claimed`, or later transition independently.

**Recommendation**

- Keep these as **advisory temporal signals** (do not reinterpret as strict state transitions).
- Test contract should assert scanner/window predicate correctness and post-settle consistency with due-window flags where applicable.
- Do not require `sensor.state == due` as a universal assertion for reminder emissions.

## Lockstep contract categories

### A) Strict state-equality signals

Expected post-persist UI state should match signal family state intent:

- `chore_overdue`
- `chore_missed`
- `chore_status_reset`

### B) Lifecycle-stage signals (not strict equality)

These represent workflow milestones; visible state may differ due to immediate reset/automation:

- `chore_claimed`
- `chore_approved`
- `chore_completed`

For these, contract must explicitly define allowed post-emit visible states by branch
**and by assignee perspective** (actor vs non-actor assignees).

Important: “not strict equality” applies at the whole-chore aggregate level, not as an
excuse for ambiguity. Per assignee, expected state sets must still be explicit.

### C) Advisory temporal signals

Window-based reminders, not final-state assertions:

- `chore_due_window`
- `chore_due_reminder`

## Blocked-interaction semantics (cross-cutting)

This behavior is intentionally broader than `due`.

- A user can be **blocked from interaction** while still observing a valid lifecycle display state.
- “Blocked” is a capability outcome (`can_claim`, `can_approve`, lock reason), not a separate lifecycle state family.
- Secondary-user blocking can occur in multiple states and modes (shared-first, rotation, claim-lock windows, already-claimed/approved paths).

### Capture model (two-axis contract)

For each scenario, capture both axes explicitly:

1. **Lifecycle axis**: what the visible state is (`pending`, `due`, `claimed`, `approved`/display alias, `overdue`, `completed_by_other`, etc.)
2. **Capability axis**: whether the user can act now (`can_claim`, `can_approve`, `lock_reason`, actionable predicates)

This prevents false assumptions like “state X always implies user can interact.”

### Canonical per-assignee examples (normative)

1. **Shared-first claim (`chore_claimed`)**
   - Scenario: `userA` claims, `userB` is another assigned user.
   - Expected post-settle state:
     - `userA`: `claimed`
     - `userB`: `completed_by_other`
   - Capability axis:
     - `userA`: claim is already consumed; approval capability follows normal rules.
     - `userB`: `can_claim=False` with completed-by-other style lock semantics.

2. **Rotation simple overdue without steal (`chore_overdue`)**
   - Scenario: current turn is `userA`, `userB` is not current turn, overdue handling is
     not `allow_steal`.
   - Expected post-settle state:
     - `userA`: `overdue`
     - `userB`: `not_my_turn`
   - Capability axis:
     - `userA`: actionable per overdue policy.
     - `userB`: `can_claim=False`, lock reason `not_my_turn`.

3. **Rotation simple overdue with steal (`chore_overdue`)**
   - Scenario: same as above, but overdue handling is `allow_steal`.
   - Expected post-settle state:
     - `userA`: `overdue`
     - `userB`: `overdue` (turn lock lifted in steal window)
   - Capability axis:
     - `userB`: `can_claim=True` in steal window.

These examples are contract anchors and should be encoded as direct tests.

### Required artifact in tests/docs

Add/maintain a matrix with these columns:

- signal family
- completion criteria / mode (independent/shared/shared_first/rotation)
- assignee role context (active assignee vs blocked secondary assignee)
- expected visible-state set (post-settle)
- expected capability flags (`can_claim`, `can_approve`, `lock_reason`)
- contract type (strict equality vs lifecycle-stage vs advisory)

For lifecycle-stage signals, include at least two assignee rows per scenario:

- actor assignee expected state/capability
- non-actor assignee expected state/capability

### Practical rule

- UI and helper must stay lockstep on **visible state projection** (single state path).
- Interaction enablement must be derived from capability fields, not inferred from state name alone.
- Assertions are evaluated at post-settle boundary.

## Recommended contract style (Platinum)

1. **Explicit contract table in code/docs**:
   - Signal family
   - Trigger source
   - Persist boundary
   - Allowed visible-state set after emit
   - Consumer guidance
2. **Single-source state checks in tests**:
   - Verify helper/sensor state from same context projection
3. **Branch-aware regression tests**:
   - Include auto-approve and upon-completion immediate-reset scenarios
4. **No signal semantic changes in this initiative**:
   - Keep payloads and event meanings stable
   - Only codify and test alignment expectations
5. **Post-settle test discipline**:

- All lockstep assertions run after settle boundary, not mid-transaction.

## Test-preservation policy (anti-dilution)

This initiative must not reduce test quality to absorb alias-related failures.

### Allowed test updates

- Update expected display values for approved→completed alias behavior.
- Update helper key access from `status` to `state`.
- Correct outdated assumptions when branch behavior is proven by existing lifecycle rules.

### Prohibited test updates

- Replacing exact branch assertions with overly broad state sets without branch justification.
- Dropping actor vs non-actor assertions in shared/rotation scenarios.
- Removing capability-axis checks (`can_claim`, `can_approve`, `lock_reason`) from covered scenarios.
- Deleting failing scenario tests when failure indicates possible lifecycle drift.

### Failure triage rule

For each failing test, classify as:

1. display-contract mismatch (expected from alias/key rename)
2. real lifecycle regression (must be fixed in code path, not tests)
3. test assumption bug (update assertion with explicit rationale)

Only categories (1) and (3) permit test expectation changes.

## Suggested test matrix additions

- `chore_claimed`:
  - shared-first: actor=`claimed`, other assigned assignee=`completed_by_other`
  - auto-approve branch: actor follows approved/completed/reset policy; non-actor states branch-aware
- `chore_approved`:
  - non-immediate reset: actor follows approved/completed alias contract, non-actor follows criteria rules
  - immediate reset (`upon_completion`): actor may settle to `pending`; non-actor expectations explicit by criteria
- `chore_completed`:
  - single-claimer and shared-all completion gates; validate actor + non-actor post-settle state sets
- `chore_overdue`, `chore_missed`, `chore_status_reset`:
  - strict visible-state checks per assignee role where applicable
  - include rotation overdue with and without `allow_steal`
- `chore_due_window`, `chore_due_reminder`:
  - advisory contract checks against due-window predicates, plus capability/state split assertions

## Confirmed hard-fork decisions reflected here

1. Dashboard helper key is `state` only (no `status` compatibility field).
2. Shared global chore sensor remains and expands to include rotation completion types.
3. Signal semantics remain unchanged; lockstep validation is post-settle and branch-aware.

## Decision summary for this initiative

- Keep existing signal semantics unchanged.
- Add all-signal lockstep contract documentation and tests.
- Ensure helper and sensor UI state remain single-path aligned.
