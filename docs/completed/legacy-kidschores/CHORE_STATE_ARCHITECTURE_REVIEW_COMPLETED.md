# Strategic Analysis: Chore State Architecture Review & Hardening

## Initiative snapshot

- **Name / Code**: CHORE-STATE-REVIEW (Architecture Review, Race Condition Hardening, State Simplification)
- **Target release / milestone**: v0.5.0-beta4, Schema 44
- **Owner / driver(s)**: @ccpk1 (analysis), builder TBD (implementation)
- **Status**: Decisions Approved → Technical Specification Ready

## Summary & immediate steps

| Phase / Step                             | Description                                        | % complete | Quick notes                                          |
| ---------------------------------------- | -------------------------------------------------- | ---------- | ---------------------------------------------------- |
| Phase 0 – Deep Analysis                  | Architecture review, bug root-cause, Gremlin audit | 100%       | This document                                        |
| Phase 1 – Pipeline Ordering Fix          | Fix Reset-Before-Overdue evaluation order          | 100%       | ✅ COMPLETE: fixes #237 + in-memory drift            |
| Phase 2 – COMPLETED_BY_OTHER Elimination | Remove state; sensors compute display state        | 100%       | ✅ COMPLETE: Schema 44 migration + computed blocking |
| Phase 4 – Pipeline Guard Rails           | Debug-mode invariant assertions, idempotency       | 100%       | ✅ COMPLETE: tracking + idempotency + docs + tests   |
| Phase 3 – Manual Reset Type              | Add `APPROVAL_RESET_MANUAL`                        | 100%       | ✅ COMPLETE: constant + translations + engine verify |
| Phase 5 – Missed State Tracking          | New missed tracking for overdue chores             | 100%       | ✅ COMPLETE: ChoreEngine fix + kid_name + tests      |
| Phase 6 – Due Window Lock                | Restrict claims until due window opens             | 0%         | Defer to separate initiative                         |
| Phase 7 – Rotation Chores                | Assignment rotation for shared chores              | 0%         | Defer to separate initiative                         |

1. **Key objective** – Audit the chore state machine for race conditions, processing order bugs, and unnecessary state complexity. Deliver a hardened pipeline where `f(Time, Config, UserAction)` always produces a single deterministic state outcome per tick.

2. **Summary of analysis findings**:
   - **Critical Bug (Pipeline Order)**: Overdue runs BEFORE Reset in both midnight and periodic handlers — violates the "Reset-Before-Overdue" mandate
   - **State Bloat**: `COMPLETED_BY_OTHER` is a persisted state when it should be a computed flag from `can_claim()`
   - **Gremlin Combinations**: 3+ documented, 2 additional discovered during analysis
   - **Architecture Sound**: Engine/Manager/Coordinator separation is solid; issues are in processing pipeline sequencing and state proliferation, not in the layered architecture itself

3. **Next steps (short term)**:
   - ✅ Decision: Pipeline reorder approved (Phase 1 — all items)
   - ✅ Decision: COMPLETED_BY_OTHER elimination approved with sensor computed display state (Phase 2)
   - ✅ Decision: APPROVAL_RESET_MANUAL confirmed (Phase 3)
   - ✅ Decision: Guard rails — debug mode only to start (Phase 4)
   - ✅ **Phase 1 COMPLETE** (2026-02-09): All code changes validated, in-memory drift fix applied
   - ✅ **Phase 2 COMPLETE** (2026-02-09): FSM simplified, blocking computed, schema 44 migration added
   - ✅ **Phase 3 COMPLETE** (2026-02-09): Manual reset type added, translations complete, engine verified
   - ✅ **Phase 4 COMPLETE** (2026-02-09): Guard rails implemented, idempotency checks, tests passing
   - ✅ **Implementation order adjusted** (per external review): 1 → 2 → 4 → 3 → 5-7
   - 🔄 **Next**: Phases 5-7 (Missed State, Due Window Lock, Rotation) - decision point before building

4. **Risks / blockers**:
   - ~~Phase 1 changes test expectations for midnight/periodic handlers (~20-30 tests)~~ ✅ RESOLVED: All 75 tests pass
   - **Phase 1 critical fix applied**: In-memory drift prevention via try/finally blocks (see feedback response)
   - ~~Phase 2: Sensors must still present `completed_by_other` as a computed display state for dashboard compatibility~~ ✅ RESOLVED: get_chore_status_context() computes display state
   - ~~Phase 2: Per-kid config dicts cleanup missing in deletion & data reset~~ ✅ RESOLVED: Added cleanup for per_kid_due_dates, per_kid_applicable_days, per_kid_daily_multi_times (2026-02-09)
   - Phase 2: Dashboard YAML update needed (separate repo: kidschores-ha-dashboard) ← **DEFERRED** to dashboard release
   - Phases should be sequential (1→2→4→3→5→6→7), not parallel ← **ORDER CHANGED per review**
   - Phases 5-7 have a decision point before building (planned for v0.5.0-beta4 but may defer)

5. **References**:
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model, layered architecture
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Event architecture, signal rules
   - [CHORE_TIMER_REFACTOR_COMPLETE.md](../completed/CHORE_TIMER_REFACTOR_COMPLETE.md) - Current timer mechanics
   - [CHORE_FEATURES_V051_ANALYSIS_IN-PROCESS.md](CHORE_FEATURES_V051_ANALYSIS_IN-PROCESS.md) - Planned features
   - [CHORE_STATE_ARCHITECTURE_REVIEW_SUP_TECH_SPEC.md](CHORE_STATE_ARCHITECTURE_REVIEW_SUP_TECH_SPEC.md) - Technical specification for implementation
   - [CHORE_STATE_ARCHITECTURE_REVIEW_SUP_FEEDBACK_RESPONSE.md](CHORE_STATE_ARCHITECTURE_REVIEW_SUP_FEEDBACK_RESPONSE.md) - External review feedback & actions (2026-02-09)
   - [GitHub Issue #237](https://github.com/ad-ha/kidschores-ha/issues/237) - User-reported overdue-after-approval bug

6. **Decisions & completion check**:
   - **Decisions captured**:
     - **D1 (Phase 1 Pipeline Order)**: APPROVED — Reset-Before-Overdue reorder, two-phase pipeline, non-recurring past-due guard, auto-approve atomicity fix. All items approved.
     - **D2 (Phase 1 Non-Recurring Guard)**: APPROVED — Clear due date on UPON_COMPLETION reset for FREQUENCY_NONE chores.
     - **D3 (Phase 1 Auto-Approve)**: APPROVED — Change from background task (`async_create_task`) to inline `_approve_chore_locked()` call.
     - **D4 (Phase 2 COMPLETED_BY_OTHER)**: APPROVED WITH CONDITIONS — Remove `completed_by_other` from state engine AND data store. However, chore sensors must still compute a `completed_by_other` display state for dashboard rendering. Enhance with claim attribute details (who claimed, when).
     - **D5 (Phase 3 Manual Reset)**: APPROVED — Add APPROVAL_RESET_MANUAL type.
     - **D6 (Phase 4 Guard Rails)**: APPROVED — Debug mode only to start. Not production assertions.
     - **D7 (Target Release)**: ALL phases targeting v0.5.0-beta4 schema 44 (not deferred to v0.5.1/v0.5.2/v0.6.0). Chore state handling is foundational.
     - **D8 (Feature Phases)**: Planned features (Missed State, Due Window Lock, Rotation) added as Phases 5-7 with a decision point before building.
     - **D9 (Phase 5 Missed Refinements)**: APPROVED (2026-02-09) — Add `OVERDUE_HANDLING_CLEAR_AND_MARK_MISSED` (no rename of existing options). Use period bucket pattern matching existing chore statistics: `last_missed` (top-level timestamp), `missed` (period counter), `missed_streak_tally` (daily consecutive), `missed_longest_streak` (all-time high-water mark). Add `mark_as_missed` parameter to skip service. StatisticsManager handles period bucket writes via CHORE_MISSED signal. No migration required, additive only.
   - **Completion confirmation**: `[x]` Analysis reviewed and approved — proceed to Technical Specification
   - **Technical Specification**: See `CHORE_STATE_ARCHITECTURE_REVIEW_SUP_TECH_SPEC.md`

---

## Section A: The Five Logic Drivers – Current Implementation Audit

### A.1 Driver Interaction Model

The chore state is determined by: `State = f(CompletionCriteria, Frequency, ApprovalResetType, PendingClaimAction, OverdueHandling)`

These five drivers interact at two processing boundaries:

1. **User Action Boundary** – claim, approve, disapprove, undo (synchronous, locked)
2. **Time Boundary** – midnight rollover, periodic update (asynchronous, unlocked)

**Current code locations:**

| Driver               | Engine Method                             | Manager Method                                       | Const Prefix                     |
| -------------------- | ----------------------------------------- | ---------------------------------------------------- | -------------------------------- |
| Completion Criteria  | `calculate_transition()` (line 149)       | `_handle_completion_criteria()` (line 2998)          | `COMPLETION_CRITERIA_*`          |
| Recurring Frequency  | (schedule_engine.py)                      | `_reschedule_chore_due()` (line 3404)                | `FREQUENCY_*`                    |
| Approval Reset Type  | `should_process_at_boundary()` (line 960) | `_process_approval_reset_entries()` (line 1468)      | `APPROVAL_RESET_*`               |
| Pending Claim Action | `calculate_boundary_action()` (line 996)  | `_handle_pending_chore_claim_at_reset()` (line 1586) | `APPROVAL_RESET_PENDING_CLAIM_*` |
| Overdue Handling     | `calculate_boundary_action()` (line 996)  | `_process_overdue()` (line 1309)                     | `OVERDUE_HANDLING_*`             |

### A.2 Architecture Assessment: What's Working Well ✅

1. **Engine/Manager separation** – ChoreEngine is pure, stateless, and testable. Manager provides data routing. This is solid.

2. **TransitionEffect pattern** – Planning effects before applying them prevents partial state corruption. Good transactional design.

3. **Lock protection on user actions** – `claim_chore()` and `approve_chore()` use per-kid+chore asyncio locks. Race conditions between concurrent user actions are handled.

4. **Single-pass scanner** – `process_time_checks()` iterates chores once and categorizes into buckets. Efficient.

5. **Signal-first communication** – Managers don't call each other's write methods. Cross-domain coordination uses dispatcher signals. This prevents circular dependencies.

6. **`calculate_boundary_action()` decision matrix** – Clean, exhaustive mapping of (state × config) → action. The Engine makes the decision; the Manager executes it.

### A.3 Architecture Assessment: What Needs Improvement ⚠️

See detailed findings below (Sections B through G).

---

## Section B: CRITICAL FINDING – Pipeline Processing Order Bug

### B.1 The Problem

**In both `_on_midnight_rollover()` (line 145) and `_on_periodic_update()` (line 184), overdue is processed BEFORE approval resets.**

```
Current order (WRONG):
1. process_time_checks()       → Single scan, categorize everything
2. _process_overdue()          → Mark chores OVERDUE  ← runs first
3. _process_approval_reset()   → Reset chores to PENDING  ← runs second
```

This means:

- A chore that SHOULD be reset (e.g., APPROVED + AT_MIDNIGHT_ONCE at midnight) first gets checked for overdue
- Since `chore_is_actionable()` filters out APPROVED chores from the overdue scan, the immediate issue is masked for the most common case
- BUT: for `UPON_COMPLETION` chores that reset to PENDING immediately on approval, the next periodic scan sees them as PENDING + past due → marks OVERDUE

### B.2 Root Cause of Issue #237

The user's scenario in issue #237:

1. Chore has `approval_reset: upon_completion`, `frequency: none`, due date set externally
2. User completes chore → goes to APPROVED → `UPON_COMPLETION` immediately resets to PENDING
3. Due date is already in the past (chore was overdue when completed)
4. Next periodic scan (within 5 minutes): `process_time_checks()` sees PENDING + past due → categorizes as overdue
5. `_process_overdue()` marks it OVERDUE
6. There's no reset to clear it because `frequency: none` means no rescheduling

**This is fundamentally the "Impossible Reset" Gremlin**:

- `frequency: none` + `approval_reset: upon_completion` + `due_date in past`
- After UPON_COMPLETION reset, chore is PENDING with a past due date
- System immediately re-marks it OVERDUE because nothing advances the due date

### B.3 The Correct Pipeline Order

```
Correct order:
1. process_time_checks()       → Single scan, categorize everything
2. _process_approval_reset()   → Reset chores to PENDING FIRST
3. _process_overdue()          → Mark only still-eligible chores OVERDUE
```

**But this alone is insufficient.** The scan happens at step 1, so the overdue list is already built. Reordering steps 2 and 3 won't remove items from the overdue list that were reset in step 2.

### B.4 Recommended Fix: Two-Phase Pipeline

```
Phase A: Reset (clears stale states)
  1. process_time_checks(now, trigger)    → categorize
  2. _process_approval_reset(scan, now)    → reset eligible chores to PENDING
  3. Reschedule (set new due dates for reset chores)

Phase B: Overdue (marks fresh violations)
  4. RE-SCAN: process_time_checks(now, trigger) again
     OR: filter overdue list to exclude chores just reset
  5. _process_overdue(filtered_overdue, now)    → mark remaining as OVERDUE
  6. _process_due_window(scan)
  7. _process_due_reminder(scan)
```

**Optimization**: Instead of a full re-scan, track which (kid_id, chore_id) pairs were reset in Phase A and filter them out of the overdue list before Phase B.

```python
# Pseudocode for hardened pipeline
async def _on_periodic_update(self, ...):
    scan = self.process_time_checks(now_utc, trigger=trigger)

    # Phase A: Resets first (returns set of reset kid+chore pairs)
    reset_pairs = await self._process_approval_reset_entries(scan, now_utc, trigger)

    # Phase B: Overdue, excluding anything just reset
    filtered_overdue = [
        e for e in scan["overdue"]
        if (e["kid_id"], e["chore_id"]) not in reset_pairs
    ]
    await self._process_overdue(filtered_overdue, now_utc)

    # Phase C: Notifications (unchanged)
    self._process_due_window(scan["in_due_window"])
    self._process_due_reminder(scan["due_reminder"])
```

### B.5 Additional Fix: Non-Recurring Past-Due Guard

For `frequency: none` chores with a past due date that just got approved+reset via UPON_COMPLETION:

The chore returns to PENDING with the old (past) due date. Without a new due date, the next scan immediately marks it overdue.

**Fix**: After `UPON_COMPLETION` reset, if `frequency == FREQUENCY_NONE`, **clear the due date** (set to None). The chore stays PENDING indefinitely until the user (or automation) sets a new due date. This matches the user's expectation in #237.

```python
# In approve_chore, after UPON_COMPLETION reset:
if should_reset_immediately and frequency == const.FREQUENCY_NONE:
    # Clear past due date to prevent immediate re-overdue
    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        per_kid_dates = chore_data.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        per_kid_dates.pop(kid_id, None)
    else:
        chore_data.pop(const.DATA_CHORE_DUE_DATE, None)
```

### B.6 Impact Assessment

| Impact                                        | Scope                                          | Risk                                                    |
| --------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------- |
| Pipeline reorder                              | `_on_midnight_rollover`, `_on_periodic_update` | LOW - same operations, different order                  |
| `_process_approval_reset_entries` return type | Return set of reset pairs instead of count     | LOW - additive change                                   |
| Non-recurring past-due guard                  | `_approve_chore_locked`                        | LOW - only affects `UPON_COMPLETION` + `FREQUENCY_NONE` |
| Test updates                                  | 20-30 tests checking processing order          | MEDIUM - test expectations need updating                |

---

## Section C: COMPLETED_BY_OTHER State – Elimination Analysis

### C.1 Current Implementation

`CHORE_STATE_COMPLETED_BY_OTHER` is used for `SHARED_FIRST` chores. When Kid A claims a SHARED_FIRST chore:

- Kid A → `CLAIMED`
- All other kids → `COMPLETED_BY_OTHER`

When Kid A is approved:

- Kid A → `APPROVED`
- Other kids stay `COMPLETED_BY_OTHER`

When Kid A is disapproved:

- ALL kids → `PENDING` (race re-opens)

### C.2 Problems with COMPLETED_BY_OTHER as a State

1. **It's not a true chore state** – It describes a _relationship_ ("someone else is handling this"), not a _chore lifecycle stage_. The chore isn't "completed" — it's "locked by another claimant."

2. **FSM bloat** – It requires:
   - Entry in `VALID_TRANSITIONS` (can only go to PENDING)
   - Special handling in `_transition_chore_state()` to manage `completed_by_other_chores` list
   - Check in `can_claim_chore()` to block claims
   - Check in `can_approve_chore()` to block approvals

3. **Dashboard coupling** – `completed_by_other_chores` list is maintained on `kid_info` (DATA_KID_COMPLETED_BY_OTHER_CHORES) for sensor display. This is a display concern leaking into the data model.

4. **Misleading semantics** – "Completed by other" implies the work is done. But in SHARED_FIRST, if the claimant is disapproved, the race re-opens. Nothing was "completed."

### C.3 Proposed Replacement: Computed Blocking via `can_claim()`

Instead of storing `COMPLETED_BY_OTHER`, derive the blocking at claim time:

```python
# In can_claim_chore() - enhanced logic:
if criteria == COMPLETION_CRITERIA_SHARED_FIRST:
    # Check if any other kid has a pending claim or approval
    for other_kid_id in assigned_kids:
        if other_kid_id != kid_id:
            other_data = get_chore_data_for_kid(other_kid_data, chore_id)
            other_state = other_data.get(DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING)
            if other_state in (CHORE_STATE_CLAIMED, CHORE_STATE_APPROVED):
                return (False, "chore_claimed_by_other")
```

**Kid states would be:**

- Kid A claims → Kid A: `CLAIMED`, Other kids: **stay `PENDING`** (but `can_claim` returns False)
- Kid A approved → Kid A: `APPROVED`, Other kids: **stay `PENDING`** (but `can_claim` returns False)
- Kid A disapproved → Kid A: `PENDING`, Other kids: already `PENDING` (no state change needed)
- Reset → All kids: `PENDING`

### C.4 Benefits

| Benefit                      | Details                                                                  |
| ---------------------------- | ------------------------------------------------------------------------ |
| **Simpler FSM**              | Remove one state, reduce `VALID_TRANSITIONS`, fewer edge cases           |
| **No list management**       | Eliminate `DATA_KID_COMPLETED_BY_OTHER_CHORES` list on kid_info          |
| **Cleaner disapprove**       | No need to reset "other" kids — they never changed state                 |
| **Cleaner undo**             | Same benefit — undo only affects the actor                               |
| **Accurate semantics**       | Other kids are "blocked" (derivable), not "completed" (misleading)       |
| **Dashboard simplification** | Dashboard shows "Pending (claimed by Sarah)" instead of a separate state |

### C.5 Costs and Considerations

| Cost                                       | Details                                                            | Mitigation                                                                                     |
| ------------------------------------------ | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| **`compute_global_chore_state()` change**  | Currently checks for COMPLETED_BY_OTHER in state counting          | Replace with: if SHARED_FIRST and any kid is CLAIMED/APPROVED, global state = CLAIMED/APPROVED |
| **Sensor display logic**                   | Currently uses COMPLETED_BY_OTHER state to show special icon/color | Use `can_claim` return value + `claimed_by` field for display                                  |
| **Dashboard YAML**                         | References `completed_by_other` state for coloring                 | Update to check `claimed_by` attribute + state                                                 |
| **Schema migration**                       | Existing chores with COMPLETED_BY_OTHER state need migration       | On load: convert any `completed_by_other` → `pending`                                          |
| **`_plan_claim_effects()` simplification** | No longer needs to emit effects for other kids on claim            | Simpler code, fewer effects to apply                                                           |

### C.6 Recommendation

**Proceed with elimination.** The benefits (simpler FSM, fewer edge cases, cleaner semantics) significantly outweigh the costs. This is a **data model improvement** that pays compound dividends on every future feature (rotation, missed state, etc.).

**Phasing**:

- Phase 2a: Add computed blocking to `can_claim()` for SHARED_FIRST
- Phase 2b: Remove COMPLETED_BY_OTHER from `_plan_claim_effects()` / `_plan_approve_effects()`
- Phase 2c: Remove from FSM, `_transition_chore_state()`, kid_info list management
- Phase 2d: Schema migration (convert existing `completed_by_other` → `pending`)
- Phase 2e: Dashboard update

---

## Section D: Gremlin Audit – All Known Problematic Combinations

### D.1 Previously Documented Gremlins

#### Gremlin 1: "The Impossible Reset"

- **Config**: `frequency: none` + `approval_reset: at_due_date_once` + `due_date: NULL`
- **Symptom**: Chore never resets because `now > due_date` is never true
- **Current Status**: Partially mitigated by flow validation (AT_DUE_DATE requires due date)
- **Remaining Gap**: User can clear due date via service after config, recreating the gremlin
- **Fix**: In `_process_approval_reset_entries`, for AT_DUE_DATE triggers, always check `has_due_date` before including in reset scan ← **Already done** (line 1203-1210 of chore_manager.py)

#### Gremlin 2: "The Zombie Claim"

- **Config**: `approval_reset: at_midnight_once` + `pending_claims: hold_pending`
- **Symptom**: Kid claims at 11:59 PM → midnight holds → next day chore still CLAIMED
- **Current Status**: Working as designed. `calculate_boundary_action()` returns "hold" for CLAIMED + HOLD. This is intentional for spanning tasks.
- **Recommendation**: **Document behavior, don't fix**. Add tooltip in UI: "Chore will remain claimed across reset boundaries."

#### Gremlin 3: "The Infinite Overdue" (Reset vs Overdue priority)

- **Config**: `overdue_handling: at_due_date` + `approval_reset: at_midnight`
- **Symptom**: Overdue at 10PM, midnight hits, should reset win or overdue win?
- **Current Status**: `calculate_boundary_action()` returns "hold" for OVERDUE + AT_DUE_DATE. The overdue blocks the reset.
- **Recommendation**: This is correct behavior — AT_DUE_DATE overdue IS blocking by design. BUT: `CLEAR_AT_APPROVAL_RESET` overdue DOES get reset. The distinction is intentional and working.

### D.2 Newly Discovered Gremlins

#### Gremlin 4: "The Re-Overdue Loop" (Issue #237 Root Cause)

- **Config**: `frequency: none` + `approval_reset: upon_completion` + past due date
- **Symptom**: Approve → UPON_COMPLETION resets to PENDING → past due date still set → next scan marks OVERDUE again → infinite loop
- **Root Cause**: UPON_COMPLETION reset doesn't clear past due dates for non-recurring chores
- **Fix**: Phase 1 (Section B.5) – clear due date on UPON_COMPLETION reset for `FREQUENCY_NONE`

#### Gremlin 5: "The Phantom Overdue After Reset"

- **Config**: `approval_reset: at_midnight_once` + any overdue_handling with recurring chore
- **Symptom**: Midnight hits → scan captures overdue entries AND reset entries → overdue processes first → chore becomes OVERDUE → reset runs second → chore resets to PENDING → but overdue already emitted signal and recorded stats
- **Root Cause**: Processing order (Section B)
- **Impact**: False overdue stats, unnecessary notification
- **Fix**: Phase 1 pipeline reorder (Section B.4)

#### Gremlin 6: "Auto-Approve + SHARED_FIRST Instant Overdue"

- **Config**: `auto_approve: true` + `completion_criteria: shared_first` + past due date
- **Symptom**: Kid claims → `auto_approve` fires immediately → chore approved → UPON_COMPLETION (if configured) resets to PENDING → immediately overdue. Or: approved but other kids see `completed_by_other` which then becomes confusing at reset boundary.
- **Root Cause**: `auto_approve` creates a task (`hass.async_create_task`) for approve, which runs asynchronously. If the periodic scanner runs between claim and auto-approve completion, state inconsistency can occur.
- **Impact**: Mentioned in #237 comments ("shared first and auto approve is doing this")
- **Fix**: For auto-approve, the claim+approve should be atomic (not separate task). Consider inlining the approve logic when auto_approve is True, or await the task instead of creating a background task.

### D.3 Gremlin Summary Matrix

| #   | Name                        | Severity         | Fix Phase       | Effort |
| --- | --------------------------- | ---------------- | --------------- | ------ |
| 1   | Impossible Reset            | Low (mitigated)  | Already handled | N/A    |
| 2   | Zombie Claim                | None (by design) | Document only   | 1h     |
| 3   | Infinite Overdue            | None (correct)   | N/A             | N/A    |
| 4   | Re-Overdue Loop             | **HIGH**         | Phase 1         | 4h     |
| 5   | Phantom Overdue After Reset | **MEDIUM**       | Phase 1         | 4h     |
| 6   | Auto-Approve Race           | **MEDIUM**       | Phase 1         | 2h     |

---

## Section E: Auto-Approve Atomicity Issue

### E.1 Current Implementation

In `_claim_chore_locked()` (line 413-416):

```python
auto_approve = chore_data.get(const.DATA_CHORE_AUTO_APPROVE, ...)
if auto_approve:
    self.hass.async_create_task(
        self.approve_chore("auto_approve", kid_id, chore_id)
    )
```

This creates a **background task** for approval. The claim method returns, releasing the lock, and approval runs later.

### E.2 The Problem

Between claim and auto-approve:

1. The periodic scanner could run and see the chore as CLAIMED + past due → mark OVERDUE
2. Another kid could try to claim (unlikely but possible with fast automation)
3. For SHARED_FIRST: other kids are already in `COMPLETED_BY_OTHER` state, but approval hasn't confirmed it yet

### E.3 Recommended Fix

**Await the auto-approve directly instead of creating a background task:**

```python
if auto_approve:
    await self.approve_chore("auto_approve", kid_id, chore_id)
```

Since both `claim_chore()` and `approve_chore()` use the same per-kid+chore lock, this would deadlock with the current implementation. The fix requires:

**Option A**: Call `_approve_chore_locked()` directly (already inside lock):

```python
if auto_approve:
    await self._approve_chore_locked("auto_approve", kid_id, chore_id)
```

**Option B**: Use re-entrant lock pattern (more complex, not recommended)

**Recommendation**: Option A – direct call to locked implementation. This is safe because we're already inside the same lock context.

---

## Section F: APPROVAL_RESET_MANUAL – New Reset Type

### F.1 User Request (from #237)

Users need chores that:

- Can be completed at any time
- Stay APPROVED indefinitely after completion
- Only reset via explicit manual action (button press or service call)
- Optionally have due dates for tracking/display without triggering automatic resets

### F.2 Implementation Assessment

**Complexity: LOW** – This is the simplest of all reset types because it does nothing automatically.

```python
# const.py
APPROVAL_RESET_MANUAL = "manual"

# chore_engine.py - should_process_at_boundary()
# MANUAL → Always returns False (never processes at timer boundary)

# chore_engine.py - calculate_boundary_action()
# Not called because should_process_at_boundary returns False

# Services: reset_chore_to_pending already exists for manual reset
```

### F.3 Affected Files

| File                      | Change                                                                                       |
| ------------------------- | -------------------------------------------------------------------------------------------- |
| `const.py`                | Add `APPROVAL_RESET_MANUAL` constant                                                         |
| `engines/chore_engine.py` | No change needed (already returns False for unknown types in `should_process_at_boundary()`) |
| `helpers/flow_helpers.py` | Add to approval reset type options list                                                      |
| `translations/en.json`    | Add label for "Manual reset only"                                                            |
| `data_builders.py`        | No change (default stays AT_MIDNIGHT_ONCE)                                                   |

### F.4 Recommendation

**Implement in Phase 3.** Low effort (2-3 hours including tests), high user value, zero risk to existing functionality.

---

## Section G: Processing Pipeline Hardening Recommendations

### G.1 Invariant: One State Outcome Per Tick

**Rule**: For any given (kid_id, chore_id) pair, a single timer tick (midnight or periodic) must produce at most ONE state change.

**Current violation**: A chore can be both in the overdue list AND the reset list. If both process, it gets two state changes in one tick.

**Fix**: The set-based exclusion from Phase 1 (Section B.4) ensures each pair is processed at most once.

### G.2 Invariant: Persist-Once-Per-Batch

**Current issue**: `_process_overdue()` calls `_coordinator._persist()` inside its loop (line 1375), once per overdue chore. Then `_process_approval_reset_entries()` also persists per reset.

**Fix**: Batch all state changes, then persist once at the end of the pipeline:

```python
async def _on_periodic_update(self, ...):
    scan = self.process_time_checks(now_utc, trigger)

    # Phase A: Resets (no persist yet)
    reset_pairs = await self._process_approval_reset_entries(scan, now_utc, trigger, persist=False)

    # Phase B: Overdue (no persist yet)
    filtered = [e for e in scan["overdue"] if (e["kid_id"], e["chore_id"]) not in reset_pairs]
    await self._process_overdue(filtered, now_utc, persist=False)

    # Phase C: Single persist
    self._coordinator._persist()
    self._coordinator.async_set_updated_data(self._coordinator._data)
```

**Benefit**: Reduces SD card writes from O(n) to O(1) per tick. More atomic — either all changes persist or none.

### G.3 Invariant: Idempotent Processing

**Rule**: Running the same scan twice with the same `now_utc` should produce the same result.

**Current violation**: `_process_overdue()` mutates state (PENDING → OVERDUE), so a second run would see the chore as OVERDUE (not actionable) and skip it. This is accidentally idempotent but fragile.

**Fix**: Check current state BEFORE applying, not just actionability:

```python
# In _process_overdue, before applying:
current_state = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)
if current_state == CHORE_STATE_OVERDUE:
    continue  # Already overdue, skip
```

### G.4 Invariant: Locks on Timer Processing

**Current gap**: User actions (claim, approve) use per-kid+chore locks. But timer processing (`_process_overdue`, `_process_approval_reset_entries`) does NOT acquire locks.

**Scenario**: User approves a chore at the exact moment the periodic scanner runs. Both threads modify the same kid_chore_data dict.

**Mitigation**: In practice, asyncio is single-threaded so this can't happen concurrently. However, `await` points during persist can yield to other coroutines.

**Recommendation**: Since asyncio is cooperative, the actual risk is LOW. But document this assumption clearly and consider adding a global "processing" flag:

```python
self._processing_timer = True
try:
    ... timer processing ...
finally:
    self._processing_timer = False
```

User actions can check this flag and retry or queue.

---

## Section H: Impact on Planned Features (v0.5.1)

### H.1 How Each Finding Affects CHORE_FEATURES_V051

| Planned Feature     | Impact from This Analysis                                                                                                           | Recommendation                         |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| **Missed State**    | Pipeline reorder (Phase 1) is PREREQUISITE. Missed stats must be recorded AFTER reset processing, not during overdue scan.          | Do Phase 1 first, then Missed State    |
| **Due Window Lock** | COMPLETED_BY_OTHER elimination (Phase 2) simplifies `can_claim()` which is the exact method Due Window Lock extends                 | Do Phase 2 first, then Due Window Lock |
| **Rotation**        | COMPLETED_BY_OTHER elimination is CRITICAL for Rotation. Rotation needs "whose turn" logic in `can_claim()`, not a state assignment | Do Phase 2 first, then Rotation        |
| **Manual Reset**    | Independent of other phases. Can be done anytime.                                                                                   | Can proceed in parallel                |

### H.2 Recommended Feature Sequencing

> **⚠️ SUPERSEDED by Decision D7**: All phases now target v0.5.0-beta4 schema 44. The original versioned sequencing below is retained for historical context only. Execution order remains 1→2→3→4→5→6→7 sequential.

```
# ORIGINAL (superseded):
v0.5.1 (Stability):
  1. Pipeline Ordering Fix (Phase 1) ← Prerequisite for all
  2. COMPLETED_BY_OTHER Elimination (Phase 2) ← Prerequisite for Rotation/Due Window Lock
  3. Manual Reset Type (Phase 3) ← Independent
  4. Auto-Approve Atomicity Fix (Gremlin 6) ← Independent

v0.5.2 (Features):
  5. Missed State Tracking ← Requires Phase 1
  6. Due Window Claim Restrictions ← Requires Phase 2

v0.6.0 (Major):
  7. Rotation Completion Criteria ← Requires Phase 2
```

---

## Section I: Detailed Phase Plans

### Phase 1 – Pipeline Ordering Fix (Estimated: 12-16 hours)

**Goal**: Fix the Reset-Before-Overdue processing order in both midnight and periodic handlers.

#### Steps

- [ ] **1.1** Modify `_process_approval_reset_entries()` to return `set[tuple[str, str]]` of (kid_id, chore_id) pairs that were reset, in addition to the count
  - File: `managers/chore_manager.py` line 1468
  - Current return: `int` (count)
  - New return: `tuple[int, set[tuple[str, str]]]` or add return value to include reset pairs

- [ ] **1.2** Reorder `_on_midnight_rollover()` to process resets BEFORE overdue
  - File: `managers/chore_manager.py` line 145
  - Move `_process_approval_reset_entries()` before `_process_overdue()`
  - Filter overdue entries using reset_pairs set

- [ ] **1.3** Reorder `_on_periodic_update()` same way
  - File: `managers/chore_manager.py` line 184
  - Same reorder as midnight

- [ ] **1.4** Add non-recurring past-due guard in `_approve_chore_locked()`
  - File: `managers/chore_manager.py` ~line 640 (after UPON_COMPLETION reset block)
  - Clear due date when `frequency == FREQUENCY_NONE` and `should_reset_immediately`

- [ ] **1.5** Add persist batching — `_process_overdue()` and `_process_approval_reset_entries()` accept `persist=False` parameter
  - Move persist to end of pipeline in both handlers

- [ ] **1.6** Fix auto-approve atomicity: change `hass.async_create_task(self.approve_chore(...))` to `await self._approve_chore_locked(...)`
  - File: `managers/chore_manager.py` line 413-416

- [ ] **1.7** Update tests
  - Files: `tests/test_chore_scheduling.py`, `tests/test_approval_reset_overdue_interaction.py`
  - Update processing order expectations
  - Add test: approve overdue chore with UPON_COMPLETION + FREQUENCY_NONE → stays PENDING (not re-overdue)
  - Add test: midnight processes reset BEFORE overdue

#### Validation

```bash
pytest tests/test_chore_scheduling.py tests/test_approval_reset_overdue_interaction.py -v
pytest tests/ -v --tb=line
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/
```

---

### Phase 2 – COMPLETED_BY_OTHER Elimination (Estimated: 16-20 hours)

**Goal**: Replace the `COMPLETED_BY_OTHER` persisted state with computed `can_claim()` blocking for SHARED_FIRST chores.

#### Steps

- [ ] **2.1** Enhance `can_claim_chore()` in ChoreEngine to check other kids' states for SHARED_FIRST blocking
  - File: `engines/chore_engine.py` line 432
  - Add new parameter: `other_kids_states: dict[str, str] | None = None`
  - When `criteria == SHARED_FIRST` and any other kid is CLAIMED or APPROVED, return `(False, "chore_claimed_by_other")`

- [ ] **2.2** Update `can_claim_chore()` wrapper in ChoreManager to pass other kids' states
  - File: `managers/chore_manager.py` line 2443

- [ ] **2.3** Simplify `_plan_claim_effects()` for SHARED_FIRST
  - File: `engines/chore_engine.py` line 244
  - Remove effects for other kids (no longer transitioning them to COMPLETED_BY_OTHER)
  - Only emit effect for the claiming kid

- [ ] **2.4** Simplify `_plan_approve_effects()` for SHARED_FIRST
  - File: `engines/chore_engine.py` line 287
  - Remove COMPLETED_BY_OTHER effects for other kids

- [ ] **2.5** Simplify `_plan_disapprove_effects()` for SHARED_FIRST
  - File: `engines/chore_engine.py` line 323
  - Only reset the actor kid (others are already PENDING)

- [ ] **2.6** Simplify `_plan_undo_effects()` for SHARED_FIRST
  - File: `engines/chore_engine.py` line 369
  - Same simplification as disapprove

- [ ] **2.7** Update `compute_global_chore_state()` for SHARED_FIRST
  - File: `engines/chore_engine.py` line 783
  - Remove COMPLETED_BY_OTHER counting
  - SHARED_FIRST global state: if any kid APPROVED → APPROVED, if any CLAIMED → CLAIMED, else PENDING

- [ ] **2.8** Remove COMPLETED_BY_OTHER from `VALID_TRANSITIONS`
  - File: `engines/chore_engine.py` line 94
  - Remove the entry entirely

- [ ] **2.9** Remove `completed_by_other_chores` list management from `_transition_chore_state()`
  - File: `managers/chore_manager.py` line 2840-2850
  - Remove the block that manages `DATA_KID_COMPLETED_BY_OTHER_CHORES`

- [ ] **2.10** Add schema migration: convert existing `completed_by_other` states to `pending`
  - File: `helpers/migration_helpers.py` or inline in SystemManager
  - Bump schema version

- [ ] **2.11** Update sensor.py to derive SHARED_FIRST blocking from `can_claim` + `claimed_by`
  - File: `sensor.py` (search for `completed_by_other` references)

- [ ] **2.12** Update dashboard YAML
  - File: `kc_dashboard_all.yaml` in kidschores-ha-dashboard repo
  - Replace `completed_by_other` state coloring with `claimed_by` attribute check

- [ ] **2.13** Update tests
  - Multiple test files referencing COMPLETED_BY_OTHER state
  - New tests: SHARED_FIRST claim shows PENDING for other kids + `can_claim` returns False

#### Validation

```bash
pytest tests/test_chore_state_matrix.py tests/test_shared_chore_features.py -v
pytest tests/ -v --tb=line
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/
```

---

### Phase 3 – Manual Reset Type (Estimated: 3-4 hours)

**Goal**: Add `APPROVAL_RESET_MANUAL` option that never auto-resets.

#### Steps

- [ ] **3.1** Add constant `APPROVAL_RESET_MANUAL = "manual"` to const.py
  - File: `const.py` near existing `APPROVAL_RESET_*` constants

- [ ] **3.2** Add to approval reset type options in flow_helpers.py
  - File: `helpers/flow_helpers.py` (approval reset selector list)

- [ ] **3.3** Add translation entry
  - File: `translations/en.json` (approval reset options section)

- [ ] **3.4** Verify `should_process_at_boundary()` returns False for unknown types (already does)
  - File: `engines/chore_engine.py` line 960 — confirm fallthrough returns False

- [ ] **3.5** Add test: manual reset type chore stays APPROVED through midnight and periodic scans
  - File: `tests/test_chore_scheduling.py`

#### Validation

```bash
pytest tests/test_chore_scheduling.py -v
pytest tests/test_config_flow.py -v
./utils/quick_lint.sh --fix
```

---

### Phase 4 – Pipeline Guard Rails (Estimated: 8-10 hours)

**Goal**: Add invariant enforcement and defensive patterns to prevent future Gremlins.

#### Steps

- [x] **4.1** Add `_assert_single_state_per_tick()` debug-mode validator
  - Track (kid_id, chore_id) pairs modified per pipeline run
  - Log warning if same pair modified twice
  - **Implementation**: `_track_state_modification()`, `_reset_pipeline_tracking()` methods added
  - **Location**: `chore_manager.py` lines ~130-160, called from `_transition_chore_state()`
  - **Debug flag**: `const.DEBUG_PIPELINE_GUARDS` (default False)

- [x] **4.2** Consolidate persist to end-of-pipeline (if not done in Phase 1)
  - **Status**: Already complete in Phase 1 implementation
  - Both midnight and periodic handlers batch persist at end

- [x] **4.3** Add idempotency guard in `_process_overdue()`
  - Skip if already OVERDUE
  - **Implementation**: State check added before processing each overdue entry
  - **Location**: `chore_manager.py` `_process_overdue()` method (~line 1510)

- [x] **4.4** Document all five Logic Driver interaction rules
  - Update ARCHITECTURE.md with driver matrix
  - Document "valid" vs "gremlin" combinations
  - **Implementation**: New "Chore State Processing Architecture" section added
  - **Location**: `docs/ARCHITECTURE.md` after "Layered Architecture"
  - **Content**: Five drivers table, processing boundaries, pipeline hardening, Gremlin scenarios

- [x] **4.5** Add integration test: full pipeline with all 5 gremlin configurations
  - Verify each produces expected single outcome
  - **Implementation**: `test_phase4_pipeline_guards.py` created with 5 tests
  - **Tests**: Idempotency, Gremlin #1-3 prevention, debug tracking
  - **Location**: `tests/test_phase4_pipeline_guards.py`

#### Validation

```bash
pytest tests/test_phase4_pipeline_guards.py -v
pytest tests/ -v --tb=line
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/
```

**Phase 4 Status**: ✅ **COMPLETE** (2026-02-09)

---

## Section J: Testing Strategy

### J.1 New Test Scenarios Needed

| Scenario                                                   | Tests | Priority |
| ---------------------------------------------------------- | ----- | -------- |
| Pipeline ordering: reset before overdue at midnight        | 3-4   | P0       |
| Pipeline ordering: reset before overdue at periodic        | 3-4   | P0       |
| UPON_COMPLETION + FREQUENCY_NONE + past due: no re-overdue | 2-3   | P0       |
| Auto-approve atomicity (inline vs background task)         | 2-3   | P1       |
| SHARED_FIRST without COMPLETED_BY_OTHER state              | 8-10  | P1       |
| Manual reset type: never auto-resets                       | 3-4   | P2       |
| All 6 Gremlin scenarios as regression tests                | 6     | P2       |

### J.2 Existing Tests at Risk

Tests that assert processing order or COMPLETED_BY_OTHER state will need updates:

- `test_chore_scheduling.py` – overdue/reset interaction tests
- `test_approval_reset_overdue_interaction.py` – directly tests this interplay
- `test_chore_state_matrix.py` – COMPLETED_BY_OTHER state expectations
- `test_shared_chore_features.py` – SHARED_FIRST state transitions

---

## Section K: Decision Points — RESOLVED

All decisions approved on 2026-02-08. Target: v0.5.0-beta4, Schema 44.

1. **Phase 1 (Pipeline Order)**: ✅ APPROVED — Reset-Before-Overdue reorder, two-phase pipeline approach, all sub-items.
2. **Phase 1 (Non-Recurring Guard)**: ✅ APPROVED — Clear due date on UPON_COMPLETION reset for FREQUENCY_NONE chores.
3. **Phase 1 (Auto-Approve)**: ✅ APPROVED — Change from background task to inline `_approve_chore_locked()` call.
4. **Phase 2 (COMPLETED_BY_OTHER)**: ✅ APPROVED WITH CONDITIONS — Remove from state engine AND data store. Sensors must still compute `completed_by_other` as a display state. Enhance with claim attribute details for dashboard.
5. **Phase 3 (Manual Reset)**: ✅ APPROVED — Add APPROVAL_RESET_MANUAL type.
6. **Phase 4 (Guard Rails)**: ✅ APPROVED — Debug mode only to start.
7. **Feature Sequencing**: ✅ ALL phases target v0.5.0-beta4 schema 44. Features (Missed State, Due Window Lock, Rotation) added as Phases 5-7 with decision point before building.

---

## Notes & follow-up

- This analysis supersedes the processing order assumptions in `CHORE_TIMER_REFACTOR_COMPLETE.md`
- Phase 2 (COMPLETED_BY_OTHER elimination) unblocks cleaner Rotation implementation
- Phase 1 is the highest priority — it fixes the active bug class reported in #237
- **Technical Specification**: `CHORE_STATE_ARCHITECTURE_REVIEW_SUP_TECH_SPEC.md` contains pseudo-code, API definitions, and logic flows for builder handoff
- Phases 5-7 (Missed State, Due Window Lock, Rotation) are planned for this release but have a decision point before building
- Dashboard repo (`kidschores-ha-dashboard`) requires coordinated update for Phase 2 display state changes

> **Analysis Status**: Complete. Decisions approved. Technical Specification created for builder handoff.
