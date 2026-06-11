# Decision Questions: User Chore Pause Plan

**Created**: 2026-06-06 | **Status**: Open
**Based on**: `GAP_ANALYSIS_USER_CHORE_PAUSE.md`

---

## Priority: Critical (must answer before updating the plan)

These questions affect plan structure, architecture decisions, or MVP scope. They must be resolved before the plan can be considered complete.

### Q1: Global chore state when all assignees are paused

**Source**: GAP-7
**What**: `get_global_chore_state_context()` returns aggregate chore state. When all assignees are paused, what should the global state sensor display?

| Option | Behavior |
|--------|----------|
| A | Show underlying workflow state (`pending`, `overdue`, etc.) — pause is per-assignee, global is aggregate |
| B | Show `paused` — if nobody can act, the chore is effectively paused |

**Why critical**: Affects whether `paused` needs to be added to `CHORE_UI_GLOBAL_STATES` frozenset, whether `get_global_chore_state_context` needs a guard, and what admin dashboards show for chore aggregate state.

**Recommendation**: Option A. Pause is per-assignee display; global state is workflow aggregate. The chore isn't paused — the people are.

---

### Q2: Paused users' claimed chores in the approver queue

**Source**: GAP-8
**What**: If a user claims a chore, then gets paused, the claim exists in storage. Should the chore appear in the admin "Approve Chores" queue?

| Option | Behavior |
|--------|----------|
| A | Show in queue, allow approval — claims survive pause, approver resolves the in-flight workflow |
| B | Show in queue with "⚠ Paused" indicator, allow approval — same as A with visual distinction |
| C | Hide from queue entirely — paused means "don't process anything" |

**Why critical**: Affects whether `can_approve_chore` needs a pause guard, whether the dashboard helper's approval queue payload needs a `paused_user` flag, and what the admin approval UX looks like.

**Recommendation**: Option B. Claims are workflow checkpoints that should be resolved. The visual indicator prevents admin confusion ("why am I approving a paused user's chore?").

---

### Q3: Midnight `_process_approval_reset_entries` — does it emit signals for paused users?

**Source**: GAP-4
**What**: The midnight rollover's Phase A (`_process_approval_reset_entries`) processes approval period resets. Does it call `_transition_chore_state` or emit signals that would reach notification/statistics managers for paused users?

**Why critical**: If this path emits signals without a pause guard, paused users would get approval-reset notifications and statistics updates. This is the last un-audited signal emission path.

**Action needed**: Trace `_process_approval_reset_entries` in `chore_manager.py` (starts at the midnight handler, line ~370) and confirm whether it:
- Calls `_transition_chore_state` (which may emit signals)
- Calls `_advance_rotation` (which is already guarded by Phase 2 Step 5)
- Emits any other signals directly

**Answer format**: "Yes, it emits X signal at line Y — needs guard" or "No, it only modifies storage directly — safe."

---

## Priority: High (should answer before Phase 2 implementation)

These questions affect code-level implementation details. They can be answered during Phase 1 (storage/constants) without blocking the plan update.

### Q4: Auto-clear persistent notifications on pause — MVP or follow-up?

**Source**: OPP-1
**What**: When a user is paused, existing overdue/missed persistent notifications remain visible. Should `choreops.pause_user_chores` auto-clear them?

| Option | Effort | UX impact |
|--------|--------|-----------|
| MVP | ~5 lines in service handler | Clean — no stale "Chore X is overdue!" after pausing |
| Follow-up | Deferred | User sees stale notifications until manually cleared |

**Why high**: Small code change with significant UX improvement. If it's MVP, the `pause_user_chores` service handler and `services.yaml` need updating in Phase 5.

**Recommendation**: MVP. It's a one-liner dismiss call and prevents the most common support question ("I paused Sarah but she still has overdue notifications!").

---

### Q5: Pause reason field — MVP or follow-up?

**Source**: OPP-2
**What**: Add `chores_paused_reason` free-text field so admins can note why chores are paused (e.g., "Sarah on vacation until June 10").

| Option | Storage | UI |
|--------|---------|-----|
| MVP | 1 new user field + 1 CFOF constant + 1 translation key | Options flow + dashboard card |
| Follow-up | Deferred | N/A |

**Why high**: If MVP, it needs to be in Phase 1 (storage/constants) and Phase 5 (dashboard card). Adding it later requires a schema migration. Adding it now is ~3 lines of code.

**Recommendation**: MVP. The cost of adding it later (schema migration) far exceeds the cost of adding it now (3 lines).

---

### Q6: `set_rotation_turn` to paused user — silent skip or error?

**Source**: GAP-3
**What**: If an approver calls `set_rotation_turn` targeting a paused user, what should happen?

| Option | Behavior |
|--------|----------|
| A | Raise `ServiceValidationError` — reject the action |
| B | Silently skip to next available — "you asked for Sarah but she's paused, so I set John instead" |
| C | Allow it — the rotation skip guard in `_advance_rotation` will override at next rotation event |

**Why high**: Affects the error translation key needed and the service behavior contract.

**Recommendation**: Option A. Explicit rejection is clearer than silent override. The approver should know the user is paused before setting the turn.

---

## Priority: Medium (nice to answer before coding)

These questions affect polish and edge case handling. They don't block the plan but should be decided before writing tests.

### Q7: `chores_paused_until` timezone strategy

**Source**: TRAP-4
**What**: `chores_paused_until` stores an ISO datetime. For MVP, it's informational only (no auto-re-enable). But for the follow-up auto-re-enable: what timezone does the stored value represent?

| Option | Behavior |
|--------|----------|
| A | UTC always — stored as UTC, compared against `utcnow()` |
| B | Local timezone — stored as local, compared against local now |
| C | Store as UTC but compare against local midnight — "return on June 10" means midnight local time on June 10 |

**Why medium**: Doesn't matter for MVP (no auto-re-enable). But the storage format decision now affects the follow-up migration.

**Recommendation**: Store as UTC (consistent with all other timestamps in the codebase per DEVELOPMENT_STANDARDS.md §6). Auto-re-enable follow-up converts to local for the "return date" comparison.

---

### Q8: Paused user with pending approval on their own chore — what happens?

**Source**: TRAP-1 variant
**What**: User claims chore → admin pauses user → approver approves the claim → the chore completes. Is this correct? Should the approval be blocked because the user is paused?

**Why medium**: This is an edge case that reveals a tension: pause says "don't process," but an in-flight claim is already being processed. Letting it complete is consistent with "claims survive pause." Blocking it is consistent with "pause means freeze everything."

**Recommendation**: Allow the approval to complete. The claim was made before the pause. The approver is resolving an in-flight workflow. This is consistent with GAP-8 (Option B).

---

### Q9: Calendar — filter paused chores or show with indicator?

**Source**: Edge case #6 (plan)
**What**: The calendar entity shows all assignee chore due dates. Should paused users' chores appear?

| Option | Behavior |
|--------|----------|
| A | Show all — "calendar is a planning tool, not an action tool" |
| B | Filter paused — "calendar is an action tool, don't show things you can't act on" |
| C | Show with visual distinction — append " (Paused)" to event title |

**Why medium**: Deferrable. Calendar is informational. But the answer affects whether the calendar entity needs a pause guard.

**Recommendation**: Option A for MVP. Calendar is a planning surface. Admins use it to see the full picture. Filtering can be added later if requested.

---

## Priority: Low (defer to implementation or follow-up)

### Q10: Dashboard pause indicator on user selector chip — MVP stretch or follow-up?

**Source**: OPP-3
**What**: When admin selects a user in the dashboard selector, show a visual indicator if that user's chores are paused.

**Recommendation**: Follow-up. Dashboard template change only (no backend). Low risk, can be added anytime.

---

### Q11: Should `choreops.update_user` be created as a general service?

**Source**: GAP-9
**What**: The plan discussed `update_user` as an alternative service path, but it doesn't exist.

**Recommendation**: No. `choreops.pause_user_chores` is the dedicated path. Create `update_user` only if other user fields need service-level mutation. Remove the Option A/Option B discussion from the plan.

---

### Q12: Should the admin workflow card auto-execute Push Chores Forward?

**Source**: Plan Phase 5
**What**: The dashboard card calls `reschedule_chores_after` + `pause_user_chores` in sequence. Should this be a single atomic service instead?

**Recommendation**: No. Two-service `multi-actions` pattern is acceptable. Single atomic service is over-engineered for MVP. The partial-state risk (reschedule succeeds, pause fails) is low and self-recoverable.

---

## Quick-Answer Summary

| # | Question | Quick answer | Blocking? |
|---|----------|-------------|-----------|
| Q1 | Global state for all-paused? | Show underlying workflow state | Yes — plan update |
| Q2 | Paused claims in approver queue? | Show with "Paused" indicator | Yes — plan update |
| Q3 | Midnight reset emits for paused? | Needs code audit | Yes — plan update |
| Q4 | Auto-clear notifications on pause? | Yes, MVP (~5 lines) | No — Phase 5 |
| Q5 | Pause reason field? | Yes, MVP (~3 lines) | No — Phase 1 |
| Q6 | set_rotation_turn to paused? | Reject with error | No — Phase 2 |
| Q7 | Timezone for paused_until? | UTC (consistent with all timestamps) | No — Phase 1 note |
| Q8 | Approval of paused user's claim? | Allow (claims survive pause) | No — test scenario |
| Q9 | Calendar filter for paused? | Show all (informational surface) | No — follow-up |
| Q10 | Dashboard pause indicator? | Follow-up (template only) | No — follow-up |
| Q11 | Create update_user service? | No (pause_user_chores is sufficient) | No — plan cleanup |
| Q12 | Atomic push+pause service? | No (multi-actions is fine) | No — confirmed |

---

## Next Step

After these questions are answered, the plan needs these specific updates:

1. **Phase 1**: Add `chores_paused_reason` field (Q5), fix function name references (GAP-5), note UTC timezone (Q7)
2. **Phase 2**: Add Steps 6-8 (GAP-1, GAP-2, GAP-3), add Q6 error translation key
3. **Phase 3**: Add verification items for midnight reset (Q3) and signal consumers (GAP-6)
4. **Phase 4**: Expand sort order update to all variants (TRAP-2)
5. **Phase 5**: Add notification clearing (Q4), remove update_user discussion (Q11), add reason field to card (Q5)
6. **Decisions**: Add D-15 (global state, Q1), D-16 (approver queue, Q2), D-17 (service exclusivity, Q11)
7. **Edge cases**: Add Q8 (approval of paused claim) and Q9 (calendar) notes

> **Questions compiled**: 2026-06-06 | **12 questions, 3 critical, 3 high, 3 medium, 3 low**
