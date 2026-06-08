# Gap Analysis: User Chore Pause Plan

**Created**: 2026-06-06 | **Status**: Analysis
**Based on**: `USER_CHORE_PAUSE_PLAN_IN-PROCESS.md` (v1, 2026-06-06)

---

## Summary

Second-level analysis identified **11 gaps** (6 code-level, 3 design-level, 2 documentation-level), **4 decision traps** that need explicit resolution, and **3 opportunities** for follow-up work.

---

## Code-Level Gaps (Missing from Plan Phases)

### GAP-1: `chore_counts_toward_due_today_summary` — no pause exclusion

**Location**: `chore_manager.py` line 4176
**Impact**: Paused chores counted in "Due Today" summary
**Fix**: Add to TWO exclusion lists in the function

The function has two independent exclusion checks:

```python
# Current exclusion list (line 4193-4200):
if display_state in (
    CHORE_STATE_CLAIMED,
    CHORE_STATE_COMPLETED,
    CHORE_STATE_COMPLETED_BY_OTHER,
    CHORE_STATE_NOT_MY_TURN,
    CHORE_STATE_OVERDUE,
    CHORE_STATE_MISSED,
):
    return False

# Current exclusion list (line 4202-4208):
if claim_mode in (
    CHORE_CLAIM_MODE_BLOCKED_COMPLETED_BY_OTHER,
    CHORE_CLAIM_MODE_BLOCKED_ALREADY_APPROVED,
    CHORE_CLAIM_MODE_BLOCKED_PENDING_CLAIM,
    CHORE_CLAIM_MODE_BLOCKED_NOT_MY_TURN,
    CHORE_CLAIM_MODE_BLOCKED_MISSED_LOCKED,
):
    return False
```

**Required additions**:
- `CHORE_STATE_PAUSED` → state exclusion list
- `CHORE_CLAIM_MODE_BLOCKED_PAUSED` → claim mode exclusion list

**Phase to update**: Phase 2, Step 2 (or new Phase 2 Step 6)

---

### GAP-2: `_is_chore_due_today_for_assignee` — no pause guard

**Location**: `statistics_manager.py` line 2354
**Impact**: Paused chores counted as "due today" in statistics
**Fix**: Add early-return at function entry

```python
def _is_chore_due_today_for_assignee(
    self, chore_info: dict[str, Any], assignee_id: str, today_iso: str
) -> bool:
    """Return True if this chore is assignee-actionable today."""
    # Guard: paused users have no actionable chores
    user_data = self.coordinator._data.get(DATA_USERS, {}).get(assignee_id, {})
    if user_data.get(DATA_USER_CHORES_PAUSED):
        return False

    # ... existing logic
```

**Why GAP-1 alone isn't enough**: `chore_counts_toward_due_today_summary` checks the display state. But `_is_chore_due_today_for_assignee` uses the RAW due date, not the display state. A paused chore could have a due date matching today without ever reaching the display state check. Both guards are needed.

**Phase to update**: Phase 2 (new step) or Phase 3 (verification item)

---

### GAP-3: `set_rotation_turn` — accepts paused users as turn target

**Location**: `chore_manager.py` line 5124
**Impact**: Approver can set rotation turn to a paused user, creating a frozen turn-holder
**Fix**: Add validation after assignment check

```python
async def set_rotation_turn(self, chore_id: str, assignee_id: str) -> None:
    # ... existing rotation/assignment validation ...

    # NEW: Reject setting turn to a paused user
    if self._is_chore_paused_for_assignee(assignee_id, chore_id):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=TRANS_KEY_ERROR_CHORE_PAUSED,
            translation_placeholders={"user_name": ...},
        )
```

**Severity**: Medium. The rotation skip guard in `_advance_rotation` would advance past the paused user at the next rotation event anyway. But preventing the action is cleaner than silently overriding it later.

**Phase to update**: Phase 2 (new step) or Phase 5 (service guard)

---

### GAP-4: Midnight `_process_approval_reset_entries` — potential signal emission for paused users

**Location**: `chore_manager.py` line 334 (`_on_midnight_rollover`)
**Impact**: Approval period resets might trigger state transitions and signals for paused users
**Fix**: Audit `_process_approval_reset_entries` for signal emission paths

The midnight rollover has two phases:
- **Phase A**: `_process_approval_reset_entries` — resets approval periods, may advance rotation
- **Phase B**: `_process_overdue` — already guarded (Phase 2 Step 3)

Phase A needs audit: does it call `_transition_chore_state` or emit signals? If it advances rotation for a paused user, the rotation skip in `_advance_rotation` should catch it. But if it emits other signals (status reset, approval period expired), those might reach notification/statistics managers for paused users.

**Action**: During implementation, trace `_process_approval_reset_entries` and verify all signal emission points are guarded against paused users.

**Phase to update**: Phase 3 (new verification item)

---

### GAP-5: `build_user_profile` — function name mismatch in plan

**Location**: `data_builders.py` line 1104
**Impact**: Plan references `build_user()` which doesn't exist
**Fix**: Update plan Phase 1 Steps 5-7 to reference `build_user_profile()` and `build_user_assignment_profile()` (line 769)

**Phase to update**: Phase 1, Steps 5-7

---

### GAP-6: `SIGNAL_SUFFIX_USER_UPDATED` — verify downstream refresh for paused users

**Location**: `services.py` (pause_user_chores handler emits this)
**Impact**: If any consumer of this signal doesn't handle `chores_paused` changes, stale data persists
**Fix**: Verify these consumers handle the new fields:

| Consumer | What to verify |
|----------|---------------|
| `AssigneeDashboardHelperSensor` | Rebuilds payload; `paused` chores included with correct state |
| `AssigneeChoreStatusSensor` (all instances) | Refreshes via coordinator; P0 guard returns `paused` |
| `StatisticsManager` | Due-today counts updated (GAP-1 + GAP-2) |
| `Calendar` entities | Events refreshed; paused chores still appear (by design, edge case #6) |
| `NotificationManager` | No direct impact (signals suppressed at source) |

**Phase to update**: Phase 3 (new verification item)

---

## Design-Level Gaps (Decisions Not Yet Made)

### GAP-7: Global chore state when all assignees are paused

**Question**: `get_global_chore_state_context` (line 3910) returns aggregate chore state. When all assignees are paused, should the global state reflect this?

**Options**:

| Option | Global state shows | Rationale |
|--------|-------------------|-----------|
| A (recommended) | Underlying workflow state (`pending`, `overdue`, etc.) | Pause is per-assignee display; global state is aggregate workflow. The chore itself isn't paused — the assignees are. |
| B | `paused` | Simplifies: "if nobody can act, the chore is effectively paused." But loses workflow information. |

**Recommendation**: Option A. The global state sensor is titled "Chore State" — it describes the chore's workflow position. Pause is about who can act on it, not what state it's in. Admin dashboard can show a separate "Paused Users" indicator.

---

### GAP-8: Approver view of paused users' chores

**Question**: The admin "Approve Chores" queue shows all claimed chores. If a paused user has a claimed chore, should it appear in the approve queue?

**Analysis**: `get_chore_status_context` early-returns `paused` for the assignee's view, but the approver queue queries by global chore state (`claimed`/`claimed_in_part`), not per-assignee state. So paused users' claimed chores WOULD appear in the approve queue unless we add a filter.

**Options**:

| Option | Behavior | Rationale |
|--------|----------|-----------|
| A | Show in queue, allow approval | Claims survive pause. Approver can complete the workflow. The chore was claimed before the pause — it should be resolved. |
| B (recommended) | Show in queue with "Paused" indicator, allow approval | Same as A but with visual distinction so approver knows the user is paused |
| C | Hide from queue | Paused means "don't process." But this leaves claims in limbo. |

**Recommendation**: Option B. Add a `paused_user` flag to the dashboard helper's approval queue entry. The admin dashboard can show a "⚠ Paused" badge next to the user's name in the approve view.

---

### GAP-9: `choreops.update_user` service doesn't exist

**Question**: The plan references `choreops.update_user` as an alternative to `choreops.pause_user_chores` (Phase 5 Step 3, Option B). But `update_user` doesn't exist.

**Resolution**: This is fine — `choreops.pause_user_chores` is the dedicated service. There's no need for a general `update_user` service for MVP. Remove the Option A/Option B discussion from Phase 5 Step 3 — `pause_user_chores` is the only path.

**Note**: If a general `update_user` service is added later (for editing user profiles via automation), `chores_paused` could be added there too.

---

## Decision Traps (Subtle Gotchas)

### TRAP-1: Paused user who is also an approver — `can_approve` in context

**Trap**: `get_chore_status_context` returns `can_approve=False` in the P0 early-return. But a paused user who is also an approver SHOULD still be able to approve OTHER people's chores — just not their own.

**Analysis**: The context is per-assignee+per-chore. `can_approve=False` in the context means "this assignee cannot approve THIS chore." For their own assigned chores, this is correct (they can't approve their own work). For OTHER chores where they're the approver, `get_chore_status_context` isn't called — `can_approve_chore` is called directly, which checks the approver role, not the assignee's pause status.

**Verdict**: No bug. But the distinction between "can't approve own chores" and "can approve others' chores" is subtle. Document it.

---

### TRAP-2: Sort order shift breaks existing template logic

**Trap**: Inserting `paused` at priority 6 shifts `completed_by_other` from 6→7, `not_my_turn` from 7→8, `completed` from 8→9, `missed` from 9→10. All template variants with hardcoded `{%- elif chore_state == 'X' -%} {%- set state_priority = N -%}` must be updated.

**Current state**: The plan mentions sort order for `user-chores-essential-v1.yaml` but doesn't explicitly call out that ALL existing priority numbers in ALL template variants shift.

**Fix**: Phase 4 must include a step to audit and update sort priorities across all 4 user template variants + any shared row templates that contain sort logic.

---

### TRAP-3: `_is_chore_paused_for_assignee` called in loops — performance profile

**Trap**: The helper does two dict lookups (`_data[DATA_USERS][assignee_id]` and `_data[DATA_CHORES][chore_id]`). In `_process_overdue`, this is called per-entry in the overdue list. For a household with 5 users and 20 chores each, the overdue list is typically small (1-5 entries). Negligible.

But in `_advance_rotation`, it's called in a `for _ in range(len(assigned))` loop. If a chore has 10 assignees and they're all paused, that's 10 calls. Still negligible (dict lookups are O(1)).

**Verdict**: No performance concern for typical household sizes. But if scaling to hundreds of users, consider caching the pause check result per (assignee_id, chore_id) pair within a single request.

---

### TRAP-4: `DATA_USER_CHORES_PAUSED_UNTIL` timezone handling

**Trap**: The `chores_paused_until` field stores an ISO datetime. But what timezone? If admin sets "return on June 10" in New York (UTC-4), but the server is UTC, should the auto-re-enable fire at midnight UTC on June 10 or midnight NY on June 10?

**Resolution for MVP**: The field is informational only — no automatic re-enable. Timezone doesn't matter. When auto-re-enable is added in a follow-up, use `dt_parse(value, return_type=HELPER_RETURN_DATETIME_LOCAL)` to convert to local time before comparing.

---

## Opportunities (Beyond MVP)

### OPP-1: Auto-clear persistent notifications on pause

When a user is paused, existing persistent overdue/missed notifications remain visible. The `pause_user_chores` service could auto-clear persistent notifications for that user. This would be a better UX — no stale "Chore X is overdue!" messages after pausing.

**Effort**: ~5 lines in `pause_user_chores` handler (call `persistent_notification.async_dismiss` for relevant notification IDs)

---

### OPP-2: Pause reason field

Add a `chores_paused_reason` field (free text) so admins can note WHY chores are paused. Displayed in the admin dashboard and user's dashboard. "Sarah is on vacation until June 10" is more informative than just "Paused."

**Effort**: 1 new storage field, 1 new CFOF constant, 1 new dashboard translation key.

---

### OPP-3: Dashboard "pause indicator" on user selector chip

When an admin selects a user in the dashboard user selector, if that user's chores are paused, show a visual indicator (colored dot, icon badge) on the selector chip. This helps admins avoid accidentally operating on a paused user's chores.

**Effort**: Dashboard template change only — read `chores_paused` from user data via template sensor.

---

## Updated Phase Assignments

| Gap/Trap/Opp | Current Plan | Recommended Action |
|-------------|-------------|-------------------|
| GAP-1 (due_today exclusion) | Not covered | **Add to Phase 2**, new Step 6 |
| GAP-2 (stats due-today guard) | Not covered | **Add to Phase 2**, new Step 7 |
| GAP-3 (set_rotation_turn guard) | Not covered | **Add to Phase 2**, new Step 8 |
| GAP-4 (midnight reset audit) | Not covered | **Add to Phase 3**, new verification item |
| GAP-5 (build_user_profile name) | Phase 1 Steps 5-7 | **Fix plan** — reference correct function names |
| GAP-6 (SIGNAL_SUFFIX_USER_UPDATED) | Not covered | **Add to Phase 3**, new verification item |
| GAP-7 (global state decision) | Not covered | **Add decision** to plan's decision list (D-15) |
| GAP-8 (approver queue) | Not covered | **Add decision** to plan's decision list (D-16) |
| GAP-9 (update_user doesn't exist) | Phase 5 Step 3 | **Remove** Option A/Option B discussion from plan |
| TRAP-1 (approver-can_approve) | Not documented | **Add note** to Phase 2 key issues |
| TRAP-2 (sort order shift) | Mentioned | **Expand** Phase 4 step 5 to be explicit about ALL variants |
| TRAP-3 (loop performance) | Not documented | **Add note** to Phase 2 key issues |
| TRAP-4 (timezone) | Not documented | **Add note** to Phase 1 key issues |
| OPP-1 (clear notifications) | Not considered | **Add to follow-up list** in plan |
| OPP-2 (pause reason) | Not considered | **Add to follow-up list** in plan |
| OPP-3 (dashboard indicator) | Phase 4 Step 7 (stretch) | **Keep as stretch**, add clearer spec |

---

## New Decisions Required

| D-# | Decision | Rationale |
|-----|----------|-----------|
| D-15 | Global chore state does NOT show `paused` — it shows the underlying workflow state | Pause is per-assignee display. Global state is aggregate workflow. The chore isn't paused — the assignees are. |
| D-16 | Paused users' claimed chores appear in approver queue with a visual indicator | Claims survive pause. Approver can resolve them. Visual indicator prevents confusion. |
| D-17 | `choreops.pause_user_chores` is the only service path for setting the pause flag | No general `update_user` service exists. Dedicated service is cleaner. |

---

## Summary of Plan Changes Needed

### Phase 1 changes
- Step 5-7: Replace `build_user()` with `build_user_profile()` / `build_user_assignment_profile()`
- Key issues: Add timezone note for `chores_paused_until`

### Phase 2 changes
- Add Step 6: `chore_counts_toward_due_today_summary` — add `CHORE_STATE_PAUSED` and `CHORE_CLAIM_MODE_BLOCKED_PAUSED` to exclusion lists
- Add Step 7: `_is_chore_due_today_for_assignee` — add pause guard
- Add Step 8: `set_rotation_turn` — add pause validation
- Key issues: Add TRAP-1 (approver can_approve distinction) and TRAP-3 (performance profile)

### Phase 3 changes
- Add verification item 7: Audit `_process_approval_reset_entries` for signal emission to paused users
- Add verification item 8: Verify `SIGNAL_SUFFIX_USER_UPDATED` consumers handle `chores_paused` changes

### Phase 4 changes
- Step 5: Expand sort order update to explicitly cover ALL 4 user template variants
- Step 7 (stretch): Add clearer spec for dashboard pause indicator

### Phase 5 changes
- Step 3: Remove Option A/Option B discussion — `pause_user_chores` is the only path
- Key issues: Add note about persistent notification cleanup opportunity

### Decisions section
- Add D-15 (global state), D-16 (approver queue), D-17 (service exclusivity)

### Follow-up list
- Add OPP-1: Auto-clear persistent notifications on pause
- Add OPP-2: Pause reason field
- Confirm OPP-3: Dashboard pause indicator

> **Analysis created**: 2026-06-06 | **Verdict**: Plan is solid but needs 11 gap fixes, 4 trap notes, and 3 additional decisions before implementation.
