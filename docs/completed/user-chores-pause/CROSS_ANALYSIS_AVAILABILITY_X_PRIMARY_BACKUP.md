# Cross-Plan Analysis: User Availability × Primary-Backup Chore Type

**Created**: 2026-06-05 | **Status**: Analysis complete
**Plans analyzed**:
- `USER_AVAILABILITY_PLAN_IN-PROCESS.md` (availability flag, P0 guard, signal suppression)
- `PRIMARY_BACKUP_CHORE_TYPE_IN-PROCESS.md` (rotation_primary_backup criteria, standby_backup state)

---

## Summary

Two features under analysis touch the same methods and state machinery but are **compatible with minor ordering adjustments**. There are 2 critical interactions that need explicit coordination and 6 moderate interactions worth noting.

---

## Critical Interactions (Must Resolve Before Either Ships)

### CRIT-1: `_advance_rotation()` — guard ordering determines correctness

**Problem**: Both plans modify `_advance_rotation()` at the same location (~line 4960), and they have conflicting assumptions about what runs first.

| Plan | What it does in `_advance_rotation()` |
|------|--------------------------------------|
| **Primary-Backup** | Early-return: `new_assignee_id = assigned[0]`, skips simple/smart calculation entirely |
| **User Availability** | Post-calculation loop: iterates assigned users, skips any with `DATA_USER_UNAVAILABLE`, freezes if all unavailable |

If primary-backup is implemented first, its early-return exits BEFORE the availability skip loop runs → **unavailable primary is set as turn-holder** (bug).

If user availability is implemented first, its skip loop runs only on simple/smart results → primary-backup's `assigned[0]` never gets checked → **same bug**.

**Required resolution**: Restructure so the availability skip is a shared post-processing step that runs AFTER any criteria-specific `new_assignee_id` calculation but BEFORE the signal payload/write:

```python
def _advance_rotation(self, chore_id, completing_assignee_id, method="auto"):
    ...
    completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
    assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])

    # Step A: Determine candidate (criteria-specific)
    if completion_criteria == const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
        new_assignee_id = assigned[0] if assigned else None
    elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SIMPLE:
        new_assignee_id = self._calculate_next_turn_simple(...)
    else:  # smart
        new_assignee_id = self._calculate_next_turn_smart(...)

    # Step B: Skip unavailable (shared, criteria-agnostic)
    if new_assignee_id is not None and assigned:
        idx = assigned.index(new_assignee_id)
        for _ in range(len(assigned)):
            candidate = assigned[(idx + 1) % len(assigned)]
            if not self.coordinator.assignees_data.get(candidate, {}).get(
                const.DATA_USER_UNAVAILABLE
            ):
                new_assignee_id = candidate
                break
        else:
            pass  # ALL unavailable — freeze at current position

    # Step C: Rest of method (override clear, signal payload, write)
    ...
```

This ordering means: for primary-backup, the candidate is always `assigned[0]` (primary), then availability check advances past unavailable primary to first available backup. For simple/smart, candidate is calculated by existing logic, then availability check advances past unavailable turn-holder.

**Coordination**: Whichever plan is implemented second MUST refactor the other plan's code into this shared structure. Recommend implementing user availability FIRST (adds the skip loop), then primary-backup adds its early-return BEFORE the skip loop.

---

### CRIT-2: Reset-boundary force-to-primary vs unavailable primary

**Problem**: The primary-backup plan adds a force-to-primary at every reset boundary:

```python
# In _transition_chore_state, at reset boundary:
if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == \
        const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
    assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
    if assigned:
        chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = assigned[0]
```

This runs AFTER `_advance_rotation` (which would have advanced past an unavailable primary thanks to CRIT-1's fix). But then force-to-primary **overrides** that and sets the turn back to `assigned[0]` — who might be unavailable.

**Result**: The chore's turn is set to an unavailable primary. At next midnight cycle, `_advance_rotation` would skip the unavailable primary again (if CRIT-1 fix is in place), but the cycle repeats: advance → force-to-primary → advance → force-to-primary. The chore would ping-pong between the unavailable primary and the first available backup at each reset boundary.

**Required resolution**: The force-to-primary directive must also check availability:

```python
if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == \
        const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
    assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
    if assigned:
        # Try primary first; fall back to first available if primary unavailable
        target = assigned[0]
        primary_data = self.coordinator.assignees_data.get(target, {})
        if primary_data.get(const.DATA_USER_UNAVAILABLE):
            # Find first available backup
            for candidate in assigned[1:]:
                if not self.coordinator.assignees_data.get(candidate, {}).get(
                    const.DATA_USER_UNAVAILABLE
                ):
                    target = candidate
                    break
            # If ALL unavailable, freeze (don't change turn)
            else:
                target = None
        if target is not None:
            chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = target
```

This ensures: primary available → turn snaps to primary (correct). Primary unavailable, backups available → turn snaps to first available backup. All unavailable → turn freezes at current position.

**Note**: Even with this fix, if the primary returns from unavailability, the next reset boundary will snap the turn back to them. This is correct behavior — "primary" means "permanent owner when available."

---

## Moderate Interactions (Important, Lower Risk)

### MOD-1: P0 guard precedence — `unavailable` beats `standby_backup`

**Analysis**: The user availability plan adds a P0 guard in `get_chore_status_context` that checks `DATA_USER_UNAVAILABLE` before calling `resolve_assignee_chore_state`. The primary-backup plan adds a P3 sub-branch inside `resolve_assignee_chore_state` that returns `standby_backup` for non-turn backups.

Since P0 runs before P3 (and before the FSM call entirely), an unavailable backup sees `unavailable` — not `standby_backup`. This is **correct**: `unavailable` is a stronger condition and should take display precedence.

**No action needed** — the ordering is already correct.

---

### MOD-2: All-unavailable on primary-backup chore

**Analysis**: If primary AND all backups are unavailable, both plans freeze at current position (CRIT-1 and CRIT-2 both have "all unavailable → freeze" fallbacks). This is consistent behavior.

**No action needed** — both plans handle this identically.

---

### MOD-3: `set_rotation_turn` to an unavailable backup

**Analysis**: An approver manually sets the turn to a backup who is unavailable. The backup sees `unavailable` state (P0 guard). No one can claim the chore (primary sees `standby_backup`, backup sees `unavailable`). At next reset boundary, CRIT-2 (with fix) snaps turn to first available user. The temporary stuck state resolves within one cycle.

**No action needed** — acceptable edge case. Self-resolving. Could add a validation guard in `set_rotation_turn` to warn when setting turn to an unavailable user, but that's polish, not correctness.

---

### MOD-4: Primary unavailable — stronger argument for auto-failover

**Analysis**: The user availability plan defers "auto-activate backup when primary unavailable" (edge case O-1). However, with primary-backup chores, this feature becomes **more valuable** because:

- Without auto-failover: primary unavailable → `_advance_rotation` skips to first backup → backup becomes turn-holder → chore processes normally. Actually, this works! The availability skip in `_advance_rotation` already handles this for rotation advancement.
- The gap is: when primary is marked unavailable mid-cycle (between midnights), the chore stays with the primary as turn-holder until the next reset boundary. The P0 guard shows `unavailable` for the primary. The chore is effectively paused until midnight.

**Action**: Document in user availability plan that for primary-backup chores, the "gap" (mid-cycle unavailability) resolves within one day at next reset boundary. No immediate auto-failover needed — the existing machinery covers it within 24h.

---

### MOD-5: Overdue steal with unavailable backups

**Analysis**: Primary-backup chore with `allow_steal`. Primary is unavailable, some backups unavailable, some available. Chore becomes overdue:
- Unavailable backups: P0 guard returns `unavailable`, can't claim (correct)
- Available backups: steal window opens, can claim (correct)
- After completion: `_advance_rotation` advances past unavailable primary to first available backup (CRIT-1 fix), then force-to-primary at next reset (CRIT-2 fix may override back to primary)

**No action needed** — behavior is correct. The available backups can cover.

---

### MOD-6: Shared frozenset additions (no conflict)

**Analysis**: Both plans add entries to `CHORE_UI_ASSIGNEE_STATES` and `CHORE_CLAIM_MODES`. These are independent additions — no ordering dependency.

| Frozenset | Primary-Backup adds | User Availability adds |
|-----------|-------------------|----------------------|
| `CHORE_UI_ASSIGNEE_STATES` | `standby_backup` | `unavailable` |
| `CHORE_CLAIM_MODES` | `blocked_standby_backup` | `blocked_unavailable` |

**No action needed** — just ensure both are added when the second plan lands.

---

## Implementation Order Recommendations

### If User Availability is implemented first:

1. Add `DATA_USER_UNAVAILABLE` field and P0 guard in `get_chore_status_context`
2. Add availability skip loop in `_advance_rotation` (after simple/smart calculation)
3. Add skip guards in `_process_overdue` and `_record_chore_missed`

**When Primary-Backup lands later**:
- Refactor `_advance_rotation` to put primary-backup's `assigned[0]` candidate BEFORE the availability skip loop
- Add availability check to the force-to-primary reset boundary logic
- Verify that P0 guard already covers primary-backup (it does — P0 is criteria-agnostic)

### If Primary-Backup is implemented first:

1. Add primary-backup early-return in `_advance_rotation`
2. Add force-to-primary at reset boundary
3. Add `standby_backup` P3 sub-branch

**When User Availability lands later**:
- Refactor `_advance_rotation` to add availability skip loop AFTER primary-backup's candidate is determined
- Refactor force-to-primary to check availability (CRIT-2 fix)
- Verify that P0 guard in `get_chore_status_context` short-circuits before P3 `standby_backup` check (it will — P0 is outside `resolve_assignee_chore_state`)

**Recommendation**: Implement User Availability first. The availability skip loop is the simpler addition to `_advance_rotation` (one shared loop after criteria dispatch). Primary-backup then adds its criteria-specific candidate + the force-to-primary availability check, both of which are natural extensions of the existing structure.

---

## Dashboard Coexistence

Both plans add new dashboard states. Their sort order and display tier need consistent treatment:

| State | Plan | Recommended sort priority | Reasoning |
|-------|------|--------------------------|-----------|
| `unavailable` | User Availability | 5 (between `waiting` and `completed_by_other`) | Strong admin signal — user is paused, needs attention |
| `standby_backup` | Primary-Backup | 7 (between `completed_by_other` and `not_my_turn`) | Informational — backup is available but not active |

Both add entries to `status_map`, `status_color_map`, and `claimModeIconMap` in the same template files. These are independent additions — just ensure both sets of entries are present when the second plan's dashboard changes land.

---

## Notes & Follow-Up

- **Refactoring opportunity**: After both features land, the `_advance_rotation` method will have a clear "determine candidate → skip unavailable → apply" pipeline. Consider extracting the availability skip into its own helper method `_skip_unavailable_assignees(candidates, assigned)` for clarity.
- **Test matrix**: Test interactions should cover: primary-backup + primary unavailable, primary-backup + backup unavailable, primary-backup + all unavailable, rotation_simple + turn-holder unavailable, shared_first + all unavailable.
- **Neither plan needs to block the other**: The interactions are resolvable with minor ordering adjustments. No architectural conflicts.

> **Analysis created**: 2026-06-05 | **Based on**: Full review of both plans' code paths, state machinery, and dashboard surfaces.
