# Architectural Decision: Derived vs First-Class `paused` State

**Created**: 2026-06-06 | **Status**: Analysis
**Triggered by**: Question of whether `paused` should be a first-class persisted chore state

---

## The Architecture Boundary

ChoreOps already has a crisp separation between two state categories:

| Category | Examples | Persisted? | Meaning |
|----------|----------|-----------|---------|
| **Workflow checkpoints** | `pending`, `claimed`, `approved`, `overdue`, `missed` | ✅ Yes (`CHORE_PERSISTED_USER_STATES`) | Something **happened** — a claim, an approval, a midnight rollover |
| **Display projections** | `completed`, `due`, `waiting`, `not_my_turn`, `completed_by_other` | ❌ No (derived at runtime) | How to **show** the workflow state to the user |

This is documented explicitly in `const.py` lines 1835-1860:

```python
# - Persisted assignee state: workflow checkpoints stored in
#   assignee_chore_data[chore_id][state]
# - Persisted chore state: aggregate snapshot stored on chores[chore_id][state]
# - Derived UI state: runtime-only display projection (never persisted)
```

The question: **which bucket does `paused` belong in?**

---

## The Case for Derived (Current Plan)

`paused` is an **administrative overlay**, not a workflow event. Nothing "happened" to the chore — the user was marked away/paused, and we're choosing to suppress normal state resolution.

### How it works (derived)

```python
# In get_chore_status_context — P0 guard (single check, ~4 lines)
user_data = self.coordinator.assignees_data.get(assignee_id, {})
if user_data.get(const.DATA_USER_CHORES_PAUSED):
    return {
        CHORE_CTX_STATE: CHORE_STATE_PAUSED,
        CHORE_CTX_CAN_CLAIM: False,
        CHORE_CTX_CLAIM_MODE: CHORE_CLAIM_MODE_BLOCKED_PAUSED,
        # ... other context defaults
    }
# Fall through to normal FSM resolution
return self._resolve_normal_state(assignee_id, chore_id)
```

The underlying persisted state (`pending`, `claimed`, etc.) is **untouched**. When the flag is cleared, the FSM picks up exactly where it left off.

### Pros

| Factor | Assessment |
|--------|-----------|
| **Architecture alignment** | ✅ Fits the derived UI state pattern perfectly — `paused` joins `completed`, `due`, `waiting`, `not_my_turn` as a display projection |
| **Code surface** | ✅ ~4 lines in `get_chore_status_context`, plus 3 guard clauses in signal emitters |
| **Storage impact** | ✅ Zero — one boolean on the user record, nothing on chores |
| **State transitions** | ✅ None needed — clearing the flag restores normal FSM resolution |
| **Due date interaction** | ✅ No conflict — `_process_overdue` is skipped, due dates are whatever they are |
| **Rotation interaction** | ✅ `_advance_rotation` skips paused users, rotation fields unchanged |
| **Reversibility** | ✅ Instant — clear flag, chores resume exactly where they were |
| **Concurrent actions** | ✅ Safe — two admins pausing different users, independent flags |

### Cons

| Factor | Assessment |
|--------|-----------|
| **Per-chore granularity** | ❌ Not possible — all chores paused for user, or none |
| **"Pause everything except X"** | ❌ Not possible directly (workaround: remove user from that chore) |
| **Debugging** | ⚠️ State is computed, not visible in storage — need to check user flag to understand why chore shows `paused` |

---

## The Case for First-Class Persisted State

If `paused` were added to `CHORE_PERSISTED_USER_STATES`, it would be a workflow checkpoint stored in `assignee_chore_data[chore_id][state]`, alongside `pending`, `claimed`, `approved`, `overdue`, and `missed`.

### How it would work (persisted)

```python
# Setting paused (per-chore):
assignee_chore_data[chore_id][DATA_CHORE_STATE] = CHORE_STATE_PAUSED
self._persist()

# Bulk pause (per-user):
for chore_id in user_chores:
    assignee_chore_data[chore_id][DATA_CHORE_STATE] = CHORE_STATE_PAUSED
self._persist()

# State resolution would check:
if assignee_chore_data[chore_id].get(DATA_CHORE_STATE) == CHORE_STATE_PAUSED:
    return (CHORE_STATE_PAUSED, ...)
```

### Pros

| Factor | Assessment |
|--------|-----------|
| **Per-chore granularity** | ✅ Can pause individual chores for individual users |
| **"Pause all except X"** | ✅ Bulk pause all, then unpause specific ones |
| **Debugging** | ✅ State visible in storage — `state: "paused"` on the chore entry |
| **Service/automation** | ✅ Can be set by external automations per-chore |

### Cons (Critical)

| Factor | Assessment |
|--------|-----------|
| **State transition explosion** | ❌ Need transitions for: `pending→paused`, `due→paused`, `waiting→paused`, `claimed→paused`, `overdue→paused`, AND reverse: `paused→?` (what state do you go back to?) |
| **Reverse transition ambiguity** | ❌ If a chore was `due` when paused, should it resume as `due`, `pending`, or recalculate? If due date passed while paused, should it resume as `overdue`? |
| **Overdue interaction** | ❌ If chore is `paused` and due date passes, does it become `overdue`? If no, the `_process_overdue` guard is still needed. If yes, what's the point of pausing? |
| **Rotation interaction** | ❌ If turn-holder's state is `paused`, does rotation advance? If yes, you lose your place. If no, the chore is frozen for everyone. |
| **Architecture violation** | ❌ `paused` is not a workflow event — nothing "happened." It's an administrative decision. Mixing it with workflow checkpoints blurs the boundary. |
| **Storage bloat** | ⚠️ Every paused chore stores its state, even though the information is "this chore is paused because the user is paused" — redundant with a user flag |
| **Unpause complexity** | ❌ Must iterate all chores to unpause. If per-chore unpause is also supported, need to track which were individually paused vs bulk-paused |
| **Code surface** | ❌ ~50+ lines for state transitions, ~30+ lines for bulk operations, new service schemas |

---

## The Hybrid Option: Dual-Source Derived State

A middle ground exists: keep `paused` as a derived state (not persisted on chores), but allow TWO sources for the derivation:

1. **User-level flag** (`DATA_USER_CHORES_PAUSED`) — bulk pause all chores
2. **Chore-level pause list** (`paused_for: [user_id, ...]`) — per-chore pause

```python
# In get_chore_status_context — P0 guard with dual sources
user_paused = self.coordinator.assignees_data.get(assignee_id, {}).get(
    const.DATA_USER_CHORES_PAUSED
)
chore_paused_for_user = assignee_id in chore_data.get("paused_for", [])

if user_paused or chore_paused_for_user:
    return {
        CHORE_CTX_STATE: CHORE_STATE_PAUSED,
        CHORE_CTX_CAN_CLAIM: False,
        CHORE_CTX_CLAIM_MODE: CHORE_CLAIM_MODE_BLOCKED_PAUSED,
    }
```

### Pros vs first-class persisted

| Factor | Assessment |
|--------|-----------|
| **No state transitions** | ✅ Still derived — clearing the source restores normal FSM |
| **No reverse ambiguity** | ✅ Unpause = remove from `paused_for` or clear user flag |
| **Per-chore granularity** | ✅ Can pause specific chores via `paused_for` list |
| **"All except X"** | ✅ Bulk-pause user, then add exceptions by removing from `paused_for` |
| **Storage** | ✅ One list on chore record (small), one boolean on user record (tiny) |
| **Architecture** | ✅ Stays in the derived UI state bucket |

### Cons vs simple user-level flag

| Factor | Assessment |
|--------|-----------|
| **Complexity** | ⚠️ Two sources to check, two places to clear on unpause |
| **Edge cases** | ⚠️ User flag=true AND chore has user in paused_for (redundant but harmless) |
|    | ⚠️ User flag=false BUT chore has user in paused_for (per-chore override) |
| **Admin UX** | ⚠️ Need UI for per-chore pause (or defer to services only) |

---

## Recommendation: Phased Approach

### Phase 1 (MVP): User-level flag → derived state only

Ship the simplest version that covers the primary use case: "family going on vacation, pause everyone's chores." This is the user-level flag approach in the current plan.

### Phase 2 (follow-up): Add `paused_for` list on chores

If per-chore granularity is needed, add the `paused_for: [user_id, ...]` list to chore records. The P0 guard becomes a two-source check. No migration needed — the user flag still works, the new list is additive.

### What we should NOT do

Do **not** make `paused` a first-class persisted workflow state (`CHORE_PERSISTED_USER_STATES`). The architectural cost (state transitions, reverse ambiguity, rotation interaction, storage bloat) vastly outweighs the benefit of per-chore granularity. The derived approach with dual sources achieves the same flexibility at a fraction of the complexity.

---

## Design Decision Record

| D-# | Decision | Rationale |
|-----|----------|-----------|
| D-8 | `paused` is a **derived UI state**, never persisted on chore records | It's an administrative overlay, not a workflow event. Fits the `completed`/`due`/`waiting`/`not_my_turn` pattern. |
| D-9 | MVP uses **user-level flag only** (`DATA_USER_CHORES_PAUSED`) | Covers the primary use case with ~4 lines of code. Per-chore granularity deferred. |
| D-10 | If per-chore pause is needed later, add `paused_for: [user_id]` list to chore records | Achieves granularity without making `paused` a persisted workflow state. No state transitions, no reverse ambiguity. |

---

## Updated: What "first-class" means for `paused`

The user asked whether `paused` should be "a first-class state." We need to be precise about what that means:

| Interpretation | What it would entail | Recommended? |
|---------------|---------------------|--------------|
| "First-class **derived UI state**" | Added to `CHORE_UI_ASSIGNEE_STATES`, has translations, dashboard entries, sort order, icon | ✅ **Yes** — this is what the current plan does |
| "First-class **persisted workflow state**" | Added to `CHORE_PERSISTED_USER_STATES`, stored per-chore, has state transitions | ❌ **No** — architectural mismatch, high complexity |
| "First-class **claim mode**" | Added to `CHORE_CLAIM_MODES`, has icon, dashboard treatment | ✅ **Yes** — `blocked_paused` joins `blocked_not_my_turn` |
| "First-class **data model field**" | `DATA_USER_CHORES_PAUSED` on user record, validated in data_builders, surfaced in options flow | ✅ **Yes** — this is the storage contract |

So `paused` IS a first-class concept — it's just first-class at the **user record** and **display** levels, not at the **chore workflow checkpoint** level.

---

## The Three Pause Scopes (Extended Analysis)

**Added**: 2026-06-06 | **Triggered by**: Identifying that "pause" has three distinct scopes

### The insight

"Pause" is not one concept — it's three, operating at different levels of the data model:

```
                    ┌──────────────────────────────────┐
                    │        THE CHORE SPACE           │
                    │                                  │
                    │   ┌──────────────────────────┐   │
                    │   │  Scope 3: Chore×User      │   │
                    │   │  "Sarah can't do dishes"  │   │
                    │   │  paused_for: [user_id]    │   │
                    │   └──────────────────────────┘   │
                    │                                  │
                    │   ┌──────────────────────────┐   │
                    │   │  Scope 2: Chore (global)  │   │
                    │   │  "Dishwasher is broken"   │   │
                    │   │  DATA_CHORE_PAUSED: true  │   │
                    │   └──────────────────────────┘   │
                    │                                  │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┴───────────────────┐
                    │        THE USER SPACE            │
                    │                                  │
                    │   ┌──────────────────────────┐   │
                    │   │  Scope 1: User (all chores)│   │
                    │   │  "Sarah is on vacation"    │   │
                    │   │  DATA_USER_CHORES_PAUSED   │   │
                    │   └──────────────────────────┘   │
                    │                                  │
                    └──────────────────────────────────┘
```

### Scope definitions

| # | Scope | Storage location | Constant | Use case |
|---|-------|-----------------|----------|----------|
| **1** | **Pause User** (user-level, all chores) | `users[id].chores_paused` | `DATA_USER_CHORES_PAUSED` | Vacation, illness, away from home. "Don't process ANY chores for Sarah." |
| **2** | **Pause Chore** (chore-level, all users) | `chores[id].paused` | `DATA_CHORE_PAUSED` | Dishwasher broken, seasonal chore, renovation. "Don't process 'Mow Lawn' for ANYONE." |
| **3** | **Pause Chore×User** (intersection) | `chores[id].paused_for` | `DATA_CHORE_PAUSED_FOR` | Specific exemption. "Sarah broke her arm — she can't do dishes but can do homework." |

### Why this matters now

The current plan only addresses Scope 1. But if we design the P0 guard to only check the user flag, adding Scopes 2 and 3 later requires refactoring the guard, re-testing all FSM paths, and potentially introducing ordering bugs.

If we design the guard for all three scopes **now** (even if only Scope 1 is implemented in MVP), the architecture is ready for Scopes 2 and 3 as additive changes.

### Unified P0 guard design

```python
# In get_chore_status_context — single P0 guard, three sources

def _is_chore_paused_for_assignee(
    self, assignee_id: str, chore_id: str
) -> bool:
    """Check all three pause scopes. Returns True if chore is paused."""
    chore_data = self._data[DATA_CHORES].get(chore_id, {})
    user_data = self._data[DATA_USERS].get(assignee_id, {})

    # Scope 1: User-level — all chores paused for this user
    if user_data.get(const.DATA_USER_CHORES_PAUSED):
        return True

    # Scope 2: Chore-level — this chore paused for all users
    if chore_data.get(const.DATA_CHORE_PAUSED):
        return True

    # Scope 3: Chore×User — this chore paused for this specific user
    if assignee_id in chore_data.get(const.DATA_CHORE_PAUSED_FOR, []):
        return True

    return False


# Usage in get_chore_status_context:
if self._is_chore_paused_for_assignee(assignee_id, chore_id):
    return {
        CHORE_CTX_STATE: CHORE_STATE_PAUSED,
        CHORE_CTX_CAN_CLAIM: False,
        CHORE_CTX_CLAIM_MODE: CHORE_CLAIM_MODE_BLOCKED_PAUSED,
    }
```

### Interaction matrix

How the three scopes interact with each other:

| Scope 1 (user) | Scope 2 (chore) | Scope 3 (chore×user) | Result |
|:---:|:---:|:---:|--------|
| ❌ | ❌ | ❌ | Normal FSM resolution |
| ✅ | ❌ | ❌ | All chores paused for user (Scope 1 wins) |
| ❌ | ✅ | ❌ | This chore paused for all users (Scope 2 wins) |
| ❌ | ❌ | ✅ | This chore paused for this user (Scope 3 wins) |
| ✅ | ✅ | ❌ | Paused (either source) |
| ✅ | ❌ | ✅ | Paused (either source — redundant but harmless) |
| ❌ | ✅ | ✅ | Paused (either source — redundant but harmless) |
| ✅ | ✅ | ✅ | Paused (all three — redundant but harmless) |

Key property: **any single source being True means paused**. This is a simple OR — no priority conflicts, no resolution order bugs.

### Scope 2 (global chore pause) — special considerations

A globally paused chore has different implications than a user-paused chore:

| Concern | User pause (Scope 1) | Chore pause (Scope 2) |
|---------|---------------------|----------------------|
| Claim gating | User can't claim | NO ONE can claim |
| Rotation advance | Advance past paused user | Freeze rotation entirely |
| `_process_overdue` | Skip paused user's entries | Skip chore entirely |
| `_record_chore_missed` | Skip for paused user | Skip for all users |
| Shared chore resolution | Other assignees process normally | All assignees see `paused` |
| Dashboard display | "Paused" badge on user's chores | "Paused" badge on all users' view of this chore |
| Existing claims | Paused user can't claim new; existing claims persist | Should existing claims be cleared? **Recommendation**: existing claims persist — admin should disapprove before pausing chore globally |

### Scope 3 (chore×user) — the `paused_for` list

This is the most granular scope. Operations:

| Operation | How |
|-----------|-----|
| Add user to `paused_for` | Append to list, persist |
| Remove user from `paused_for` | Remove from list, persist |
| Check if paused | `user_id in chore_data.get(DATA_CHORE_PAUSED_FOR, [])` |
| Bulk clear (unpause chore) | Set `paused_for = []` |
| Bulk clear (unpause user) | Iterate all chores, remove user from each `paused_for` |

Edge cases:
- User is in `paused_for` AND `DATA_USER_CHORES_PAUSED` is True → redundant, but user unpause (clear flag) doesn't auto-remove from `paused_for` lists. The per-chore pauses persist until explicitly cleared.
- User is removed from chore entirely → auto-remove from `paused_for` if present.
- Chore is deleted → `paused_for` goes with it.

### Signal suppression across scopes

The three guard clauses in signal emitters need to handle all scopes:

```python
# _process_overdue — skip paused chores/users
def _process_overdue(self, ...):
    for entry in overdue_entries:
        assignee_id = entry[CHORE_SCAN_ENTRY_USER_ID]
        chore_id = entry[CHORE_SCAN_ENTRY_CHORE_ID]

        # Skip if paused (any scope)
        if self._is_chore_paused_for_assignee(assignee_id, chore_id):
            continue
        # ... normal overdue processing

# _record_chore_missed — skip paused
def _record_chore_missed(self, assignee_id, chore_id, ...):
    if self._is_chore_paused_for_assignee(assignee_id, chore_id):
        return  # No missed recording

# _advance_rotation — skip paused
# (Same pattern — check before advancing to candidate)
```

### Implementation phasing

| Phase | Scope | What ships | Storage changes |
|-------|-------|-----------|----------------|
| **MVP** (Phase 1) | Scope 1 only | User-level pause via options flow + dashboard card | `DATA_USER_CHORES_PAUSED` + `DATA_USER_CHORES_PAUSED_UNTIL` |
| **Phase 2** | Scope 3 | Per-chore pause via service call (`choreops.pause_chore_for_user`) | `DATA_CHORE_PAUSED_FOR` list on chore records |
| **Phase 3** | Scope 2 | Global chore pause via service call + options flow chore edit | `DATA_CHORE_PAUSED` boolean on chore records |

The P0 guard is designed for all three from day one — Scopes 2 and 3 are additive storage fields and service endpoints, not guard refactors.

### Updated design decisions

| D-# | Decision | Rationale |
|-----|----------|-----------|
| D-11 | The P0 guard checks **three sources** via `_is_chore_paused_for_assignee()` | Single point of truth. All scopes compose via OR. |
| D-12 | All three scopes use the same display state (`paused`) and claim mode (`blocked_paused`) | Users don't need to know WHY a chore is paused — just THAT it's paused. Admin dashboard can show the reason. |
| D-13 | Scope 2 (global chore pause) does NOT auto-clear existing claims | Claims are workflow state; pause is administrative overlay. Admin should disapprove before pausing. |
| D-14 | MVP ships Scope 1 only; Scopes 2 & 3 are architectural hooks | Guard handles all three from day one. Additional scopes are additive storage + service endpoints. |

> **Analysis created**: 2026-06-06 | **Extended**: 2026-06-06 (three-scope analysis)
> **Decision**: Keep `paused` derived. Design P0 guard for three scopes. Ship Scope 1 in MVP.
