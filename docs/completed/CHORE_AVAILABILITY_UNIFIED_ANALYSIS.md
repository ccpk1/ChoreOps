# Strategic Analysis: Unified Chore & User Availability Control

> **⚠️ SUPERSEDED**: This document contains the full strategic analysis and design exploration. The consolidated implementation plan is at [CHORE_AVAILABILITY_UNIFIED_PLAN_IN-PROCESS.md](CHORE_AVAILABILITY_UNIFIED_PLAN_IN-PROCESS.md). Key corrections from this document:
> - **Scope narrowed**: Empty assignee list only. User unavailable flag (#152, vacation) deferred.
> - **No schema bump**: `SCHEMA_VERSION_CURRENT` stays at `100` — no new storage fields.
> - **3 services, not 4**: `add_assignee`, `remove_all_assignees`, `remove_all_assignees_by_label`.
> - **9 affected files, not 14**: No user manager, no TypedDict changes, no schema migration.
> - **Approach B (dual-axis unified) is not the recommendation** — Approach A minimal surface is.

**Status**: Analysis Phase (Revised) | **Date**: 2026-06-02 | **Target Release**: TBD
**Related Issues**: [#125], [#151], [#152]
**Type**: Architecture-level enhancement (cross-cutting)

---

## 1. Initiative Snapshot

| Field | Value |
|-------|-------|
| Code Name | `availability-dual-axis` |
| Target Release | TBD (likely v0.6.0+) |
| Owner | TBD |
| Status | **Analysis** |

---

## 2. Issues Summary

### #152 — Global Skip Based on Input Helper (Shared Custody)

**Author**: @jeffm89 | **Area**: Integration logic/state

> Shared custody with kids. Chores only due "sometimes." Currently due/overdue triggers and notifies to their devices in all instances.

**Request**: A global entity (input_boolean) that, when `on`, silently skips all due chores to the next window for specified users. When `off`, normal behavior resumes.

**Current workaround**: Scripting `choreops.skip_chore_due_date` per chore via automations. Already released: `reschedule_chores_after` service (v1.0.7) for bulk rescheduling.

---

### #151 — Unassigned Chores & Ad-Hoc Task Pool

**Author**: @bcoleg | **Area**: Dashboard UI / template

> The first to complete functionality is great, but it does cause task list to become cluttered when listing all household tasks.

**Requests**:
1. Chores created as **unassigned** (no specific user)
2. A separate card view for unassigned chores — admin assignment or user claiming
3. Completion with user selection (who did it?)
4. **Ad-hoc chores** created from the dashboard (not just config flow)

**Core motivation**: Declutter user task lists when many "anyone can do" tasks exist.

---

### #125 — Seasonal / Enable-Disable Chores

**Author**: @warbringer | **Area**: Services / automations

> Some chores are only relevant during certain periods such as mowing the lawn (spring→fall).

**Requests**:
1. `choreops.enable_chore` / `choreops.disable_chore` services
2. Optional "active window" (date range) during chore creation
3. Disabled chores: hidden from all lists, not claimable/completable, but **preserved in storage** (keep stats)

**Current workaround**: `pref_exclude_label_list` in dashboard templates (label-based filtering) — mentioned in comments.

---

### ⚠️ User Availability Gap (No Issue — Strategic Discovery)

**Identified during analysis**

> A user goes on vacation for 4 days. All their assigned chores will go overdue unless the administrator manually re-assigns every single one. There is no mechanism to temporarily pause a user's chore obligations.

**Implicit need**: Per-user availability windows that:
1. Prevent overdue escalation during absence
2. Suppress notifications to unavailable users
3. Optionally auto-reschedule chores upon return
4. Work independently of chore-level availability (a chore can be active, but the user is not)

---

## 3. The Two-Dimensional Availability Problem

All four needs (three issues + user availability gap) converge on a **dual-axis architectural gap**:

```
                    ┌─────────────────────────────────────┐
                    │        AVAILABILITY MATRIX          │
                    │                                     │
                    │           Chore Available?          │
                    │            YES         NO           │
                    │  ┌─────────────┬─────────────┐     │
                    │Y │ NORMAL      │ Chore hidden │     │
                    │E │ OPERATION   │ or skipped   │     │
                    │S │             │ (seasonal,   │     │
                    │  │             │  disabled)   │     │
                    │U ├─────────────┼─────────────┤     │
                    │s │ User's      │ BOTH         │     │
                    │e │ chores      │ unavailable  │     │
                    │r │ skipped,    │ ── strongest  │     │
                    │N │ no overdue, │    hide      │     │
                    │O │ no notifs   │              │     │
                    │  └─────────────┴─────────────┘     │
                    └─────────────────────────────────────┘
```

### Axis 1: Chore Availability ("Should this chore be active?")

Driven by: seasonal windows (#125), enable/disable (#125), unassigned pool (#151), custody toggle (#152)

### Axis 2: User Availability ("Can this user do chores right now?")

Driven by: vacation/camp/sick days (new), custody schedule (#152 from the user side)

### Interaction Rules

| Chore | User | Behavior |
|-------|------|----------|
| Available | Available | ✅ Normal FSM workflow |
| Available | Unavailable | ⚠️ Skip for this user: no overdue, no notifications, hidden from their dashboard. Other users unaffected. |
| Unavailable | Available | 🚫 Chore hidden/skipped for all users |
| Unavailable | Unavailable | 🚫 Fully hidden |

### Why Both Axes Matter

- **#125 (seasonal chores)**: Chore axis — the chore is unavailable to *everyone* out of season
- **#151 (unassigned chores)**: Chore axis — the chore is in a pool, available to anyone who claims it
- **#152 (custody skip)**: *Both* axes — the chore might be active, but a specific user is unavailable during non-custody periods
- **User vacation**: User axis — all chores remain active, but one user is temporarily exempt

This two-axis model means **#152 can be solved from either side**: a global chore toggle (chore axis) OR per-user availability windows (user axis). The user-axis solution is more natural for custody because it's the *user* who is unavailable, not the chores themselves.

### Overlap Matrix (Updated)

| Dimension | #125 (Seasonal) | #151 (Unassigned) | #152 (Custody) | User Vacation |
|-----------|----------------|-------------------|----------------|---------------|
| **Primary axis** | Chore | Chore | User (or Chore) | User |
| **Chore invisible to some users** | All users | Until claimed | Non-custody users | Vacationing user only |
| **Chore exists in storage** | ✅ Stats preserved | ✅ Stats preserved | ✅ Streaks preserved | ✅ Stats preserved |
| **State change trigger** | Date range or service | Claim action | input_boolean or date range | Date range or service |
| **Bulk operation needed** | ✅ By label | N/A (per-chore) | ✅ All chores for user | ✅ All chores for user |
| **Dashboard impact** | Hide from all cards | Show in "pool" card | Hide from specific user | Hide from specific user |
| **Notification impact** | Silent when disabled | Notify on claim | Silent when skip-active | Silent during absence |
| **Overdue behavior** | Not applicable | Not applicable | Skip to next window | Skip to next window |

---

## 4. Primary Enhancements Requested (Consolidated)

| # | Enhancement | From Issue(s) | Axis | Priority Signal |
|---|-------------|---------------|------|-----------------|
| E1 | **Chore enable/disable toggle** (per-chore, persisted) | #125 | Chore | High — most-requested pattern |
| E2 | **Date-range "active window"** on chore creation | #125 | Chore | Medium — convenience over E1+automation |
| E3 | **Unassigned chore state** (no assigned user at creation) | #151 | Chore | High — new chore paradigm |
| E4 | **User claims chore from pool** (dashboard action) | #151 | Chore → User | High — enables ad-hoc workflow |
| E5 | **Ad-hoc chore creation from dashboard** | #151 | Chore | Medium — UX improvement |
| E6 | **Global/Per-user skip mode** (input_boolean driven) | #152 | User (or Chore) | Medium — custody use case |
| E7 | **Bulk enable/disable/skip by label or group** | #125, #152 | Chore | Medium — reduces automation complexity |
| E8 | **Disabled/skipped chores preserve history & stats** | #125, #152 | Both | High — non-negotiable constraint |
| **E9** | **User vacation/absence windows** (per-user date range) | *New* | User | **Critical gap** — no current workaround |
| **E10** | **Per-user availability toggle entity** | #152, *New* | User | Medium — simpler than date ranges |
| **E11** | **Auto-reschedule on return** (optional, per-user) | *New* | User | Low — nice-to-have, can be external automation |

---

## 5. High-Level Approaches

### Approach A: Minimal Surface — Two Simple Mechanisms

**Philosophy**: Solve availability with the absolute minimum new surface area. Leverage existing data model fields to their natural conclusion rather than inventing new concepts.

#### Mechanism 1: User Unavailable Flag (Solve #152 + Vacation)

Add **one boolean** to user items: `unavailable: bool` (default `false`).

When a user is marked unavailable, chore processing flow is **unchanged** except for one rule: **instead of transitioning to `overdue`, the chore silently advances to the next due date.** No new FSM states. No mode system. No toggle entities in storage. No date windows.

| Behavior | When User is Unavailable |
|----------|--------------------------|
| Due date arrives | Chore skips to next recurrence instead of becoming overdue |
| Notifications | Suppressed (no overdue/due pings to a kid at camp) |
| Dashboard | User's chores hidden or shown in "Paused" section |
| Shared chores | Other assignees unaffected |
| Rotation chores | Unavailable user skipped in rotation cycle |
| Stats/streaks | No overdue/missed counters; streaks unaffected |
| On return | Chores are already at their next due date — nothing to catch up on |

**Service**: `set_user_unavailable(user_id, unavailable: bool)` — one service, one parameter.

**Automation-friendly**: Users drive this with an `input_boolean` + automation:
```yaml
# Vacation mode: flip helper, automation calls service
automation:
  trigger: state of input_boolean.alice_vacation_mode
  action: choreops.set_user_unavailable(user_id="...", unavailable={{ is_state('on') }})
```

No need for the integration to reference toggle entities — Home Assistant's automation engine handles that.

#### Mechanism 2: Empty Assignee List (Solve #125 + #151)

Allow `assigned_user_ids` to be **empty** (`[]`). This is the natural expression of "this chore has no one to do it right now."

When a chore has zero assignees:
- **All entity processing stops** — no sensors, no FSM evaluation, no notifications
- **Chore record stays in storage** — all history, stats, period buckets preserved
- **Re-adding users reactivates** the chore with its existing schedule and history

| Use Case | How It Works |
|----------|-------------|
| #125 Seasonal | Remove all users in fall (`choreops.remove_all_assignees`). Add back in spring. Chore is dormant, not deleted. |
| #151 Unassigned | Create chore with `assigned_user_ids: []`. Appears in "pool" card. User claims → `add_assignee(chore_id, user_id)`. |
| Bulk disable | `remove_all_assignees_by_label("seasonal")` — leverage existing label system |

**Services needed**:
- `remove_all_assignees(chore_id)` — clear the list (existing `assigned_user_ids` mutation)
- `add_assignee(chore_id, user_id)` — add one user (existing mutation)
- `remove_all_assignees_by_label(label)` — bulk operation for seasonal groups

**No new chore storage fields needed.** The `assigned_user_ids` field already exists — the only change is allowing it to be `[]` instead of requiring at least one entry.

#### How This Covers Everything

```
#125 (Seasonal):   Empty assignee list → dormant, preserved
#151 (Unassigned): Empty assignee list → pool, claimable
#152 (Custody):    User unavailable → skip instead of overdue
Vacation:          User unavailable → skip instead of overdue
```

#### What's NOT Covered (Intentionally Deferred)

| Feature | Why Deferred |
|---------|-------------|
| Active window (date range on chore) | External automation with date helpers + `remove_all_assignees_by_label` |
| Per-chore toggle entity | External automation with `input_boolean` + `remove_all_assignees` |
| Per-user toggle entity | External automation with `input_boolean` + `set_user_unavailable` |
| Auto-reschedule on return | Not needed — chores already skipped forward during absence |
| Multi-mode availability system | Over-engineered for these use cases |

**Estimated Complexity**: ⭐ (Very Low)
**New storage fields**: 1 boolean per user (`unavailable`). Zero new fields on chores.
**New FSM states**: Zero. `unavailable` flag changes a transition, not a state.
**New services**: `set_user_unavailable`, `remove_all_assignees`, `add_assignee`, `remove_all_assignees_by_label`
**Schema Version Bump**: 46 (one additive boolean on user items)
**Dashboard impact**: Pool card for zero-assignee chores; "Paused" treatment for unavailable users

---

### Approach B: Unified Dual-Axis Availability Layer (Previous Recommendation)

**Philosophy**: Introduce a first-class `availability` concept on **both** chores and users, with a shared vocabulary, multiple modes, and consistent FSM integration. _(Full detail preserved below for comparison.)_

#### B1. Chore Availability (5 modes)

| Mode | Behavior | Maps To |
|------|----------|---------|
| `always` | Chore is always active (default, backward-compatible) | Current behavior |
| `manual` | Controlled by `enabled` boolean + services | #125 seasonal chores |
| `window` | Active only between `window_start` and `window_end` | #125 seasonal windows |
| `toggle` | Active when a referenced `input_boolean` entity is `on` | #152 custody (chore-side) |
| `pool` | Unassigned — available for any user to claim | #151 unassigned chores |

#### B2. User Availability (4 modes)

| Mode | Behavior | Maps To |
|------|----------|---------|
| `always` | User is always available (default, backward-compatible) | Current behavior |
| `window` | Unavailable between `unavailable_start` and `unavailable_end` | Vacation, camp, sick days |
| `toggle` | Unavailable when a referenced `input_boolean` entity is `off` | #152 custody (user-side) |
| `manual` | Controlled by `available` boolean + `set_user_available` service | Quick manual pause |

#### B3. FSM Integration (Single Coherent Pipeline)

The FSM gets **two P0 priority checks** in `resolve_assignee_chore_state`, evaluated in order:

```python
def resolve_assignee_chore_state(chore_data, user_data, assignee_id, now, ...):
    # P0a — Chore availability check (does this chore even exist right now?)
    chore_available = ChoreEngine.compute_chore_availability(chore_data, now)
    if not chore_available:
        return (CHORE_STATE_UNAVAILABLE, "chore_disabled")
    
    # P0b — User availability check (can this person do chores right now?)
    user_available = UserEngine.compute_user_availability(user_data, assignee_id, now)
    if not user_available:
        return (CHORE_STATE_UNAVAILABLE, "user_unavailable")
    
    # P1–P8 — Normal FSM workflow (unchanged)
    ...
```

**Estimated Complexity**: ⭐⭐⭐½ (Medium-High)
**New storage fields**: `availability` dict on both chore and user items
**New FSM states**: `UNAVAILABLE` + `lock_reason`
**Schema Version Bump**: 46

---

### Approach C: Full Chore Lifecycle Rework with Tags & Rules Engine

*(Not recommended — over-engineered for these use cases.)*

**Estimated Complexity**: ⭐⭐⭐⭐⭐ (Very High)
**Recommendation**: ❌ Not recommended.

---

## 6. Recommended Approach: **A — Minimal Surface**

### Rationale

1. **Approach A covers all four use cases with ~1/3 the surface area of Approach B.** One boolean on users. One constraint relaxation on chores (allow empty `assigned_user_ids`). Zero new FSM states. Zero new mode systems.

2. **Empty assignee list is the honest representation of "this chore has no one."** It doesn't need a `pool` mode, an `availability` dict, or a `disabled` flag — the absence of assignees *means* unavailable. When you want it back, add assignees. This is simpler for users to understand and for the code to implement.

3. **Skip-instead-of-overdue is the right behavior for unavailable users.** Freezing state in `pending` (Approach B) creates a catch-up problem on return — suddenly all chores are past-due at once. Skipping forward means chores are naturally at their next due date when the user returns. No "on return" configuration needed.

4. **External automation is a feature, not a gap.** Home Assistant users already use `input_boolean` helpers and automations for scheduling. The integration doesn't need to own toggle entities, date windows, or active periods — it just needs clean service APIs that automations can drive. This keeps ChoreOps focused on chore logic.

5. **Incremental path to Approach B if needed.** If users demand built-in active windows or toggle entity references, those can be added later as convenience wrappers around the same underlying mechanisms. The minimal approach doesn't close any doors.

### Comparison at a Glance

| Dimension | A: Minimal Surface | B: Dual-Axis Unified |
|-----------|-------------------|----------------------|
| New storage fields | 1 boolean (user) | 2 dicts (chore + user availability) |
| New FSM states | 0 | 1 (`UNAVAILABLE` + reasons) |
| New services | 4 simple | 6+ parameterized |
| Config flow changes | None required | Availability section per chore + user |
| Complexity | ⭐ | ⭐⭐⭐½ |
| Covers #125 | ✅ via empty assignees | ✅ via modes |
| Covers #151 | ✅ via empty assignees + claim | ✅ via pool mode |
| Covers #152 | ✅ via user unavailable flag | ✅ via user toggle mode |
| Covers vacation | ✅ via user unavailable flag | ✅ via user window mode |
| Active window built-in | ❌ (external automation) | ✅ |
| Toggle entity built-in | ❌ (external automation) | ✅ |
| Extensible to future modes | ⚠️ Would need refactor | ✅ |

### How Each Issue Maps (Minimal Approach)

```
#125 (Seasonal Chores):
  remove_all_assignees("mow-lawn-uuid") in fall
  add_assignee("mow-lawn-uuid", "alice-uuid") in spring
  → Chore dormant in storage during off-season, history preserved
  → Bulk: remove_all_assignees_by_label("seasonal")

#151 (Unassigned Chores):
  Create chore with assigned_user_ids: []
  → Chore appears in "Claimable" pool card (no entity, read from storage)
  → User claims: add_assignee(chore_id, user_id) → chore activates

#152 (Custody Skip):
  set_user_unavailable("alice-uuid", true) when at other parent's house
  → Alice's chores skip to next due date instead of going overdue
  → Driven by: automation watching input_boolean.custody_week_a

User Vacation:
  set_user_unavailable("bob-uuid", true) for vacation duration
  → Bob's chores auto-skip, no overdue pile-up on return
  → Driven by: automation with date range or calendar trigger
```

### Key Design Decisions (Minimal Approach)

| Decision | Rationale |
|----------|-----------|
| **User unavailable = skip, not freeze** | Avoids catch-up pile on return. Chores naturally advance to next due date. |
| **Empty assignee list = dormant chore** | Natural expression. No new fields. History preserved by virtue of record staying in storage. |
| **No built-in toggle entity references** | Home Assistant automations handle this better. Integration stays focused on chore logic. |
| **No built-in date windows** | Same rationale. `input_datetime` + automation is the HA-native way. |
| **Shared chores: unavailable user is skipped** | Other assignees see chore normally. Rotation: skip unavailable user, advance to next in cycle. |
| **Notifications suppressed for unavailable users** | All chore notifications (due, overdue, reminder) suppressed when `unavailable = true`. |

---

## 6a. Deep Dive: Empty `assigned_user_ids` — What Breaks?

This section traces every code path that touches `DATA_CHORE_ASSIGNED_USER_IDS` to identify what would break if the list is allowed to be empty.

### 6a.1. Constraint Enforcement (Where It's Blocked Today)

| Location | Rule | Impact of Relaxing |
|----------|------|-------------------|
| `data_builders.py:1433-1440` (`validate_chore_data`) | **Create only**: `if not is_update and not assigned_assignees` → error | Remove the create-only guard. Updates already allow empty. |
| `flow_helpers.py` (config flow schema) | `CFOF_CHORES_INPUT_ASSIGNED_USER_IDS` defaults to `[]` but validation blocks empty on create | Schema already supports empty — just remove the validation block. |
| Shared chores (implicit) | No explicit "minimum 2" constraint found in validation | Shared chores with 0-1 assignees would be technically valid but semantically odd. Consider a soft warning in the UI rather than a hard block. |

**Finding**: The constraint is a single `if` block in `validate_chore_data()`, create-only. Update paths already tolerate empty lists.

### 6a.2. Downstream Iterators (Safe by Default)

These locations iterate `assigned_user_ids` — an empty list means zero iterations, which is safe:

| File | Line | Pattern | Empty-List Behavior |
|------|------|---------|---------------------|
| `sensor.py` | 449, 699, 1003, 1017, 2600, 4551 | Iterates per-assignee to create entities | ✅ No entities created |
| `select.py` | 533 | Iterates per-assignee for chore status | ✅ No iterations |
| `calendar.py` | 383-388 | **Already guarded**: `if not assigned_user_ids: return` | ✅ Already safe |
| `entity_helpers.py` | 770 | Iterates for device lookups | ✅ No iterations |
| `gamification_manager.py` | 3363 | Checks if assignee is in chore's list | ✅ `x in []` → always False |
| `coordinator.py` | 547-552 | Compares previous/current lists for change detection | ✅ Empty → empty is a no-change |
| `options_flow.py` | 1111, 1430, 1602, 1905, 2146 | Various edit form population | ✅ Forms can show empty selector |
| `boot_repairs.py` | 80 | Integrity checks on assignee IDs | ✅ Empty list passes validation |

### 6a.3. FSM / State Resolution (Needs Attention)

| Location | Concern | Risk |
|----------|---------|------|
| `chore_engine.py:1056` (`compute_global_chore_state`) | With zero assignee states, all counts are 0. Currently: counts → no match → falls through to mixed-state logic | **Medium**: Need to verify the fallthrough produces a sensible state (likely `pending` or `unknown`). Should explicitly handle `total == 0`. |
| `chore_engine.py:1260` (`resolve_rotation_global_state`) | Rotation chores with no assignees — `rotation_current_assignee_id` is a dangling reference | **Medium**: Rotation chores should probably not be allowed to go empty. If all assignees are removed from a rotation chore, the rotation pointer becomes dangling. |
| `DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID` | Points to a single UUID. If that user is removed from the list, the reference is stale | **Medium**: Need cleanup logic — when removing the last assignee from a rotation chore, clear the rotation pointer. |

### 6a.4. Gamification (Badges, Achievements, Challenges)

| System | How It References Chores | Empty-Assignee Impact |
|--------|-------------------------|----------------------|
| **Badges (tracked chores)** | `DATA_BADGE_TRACKED_CHORES` stores a list of chore IDs. `get_badge_in_scope_chores_list()` intersects these with what the assignee is actually assigned to. | ✅ Safe — an empty-assignee chore won't appear in any assignee's scope. Badge evaluation simply ignores it. |
| **Achievements (selected chore)** | `DATA_ACHIEVEMENT_SELECTED_CHORE_ID` — a single chore UUID. `_map_achievement_to_canonical_target()` checks if the assignee is assigned to that chore. | ✅ Safe — if no one is assigned, `tracked_chore_ids` becomes `[]` for all assignees. Achievement won't progress until someone is assigned. |
| **Challenges** | Currently disabled (sunset), same pattern as achievements when re-enabled | ✅ Same safety. |

### 6a.5. Data Integrity (Historical)

| Data Structure | Concern | Verdict |
|---------------|---------|---------|
| `assignee_chore_data[chore_id]` (per-user chore tracking) | Removing all assignees doesn't delete their historical tracking data — it stays in each former assignee's `DATA_USER_CHORE_DATA` dict | ✅ History preserved. When reassigned, historical data is still there. |
| `per_assignee_due_dates` | Keyed by assignee ID. Empty assignee list → empty dict. | ✅ Safe |
| `per_assignee_applicable_days` | Same pattern. | ✅ Safe |
| Period buckets (daily/weekly/monthly) | Stats are stored per-assignee, not per-chore. Removing assignees from a chore doesn't touch their stats. | ✅ History preserved |
| Streaks | Stored in assignee `chore_data[chore_id]`. Removing assignment doesn't erase streak history. | ✅ History preserved |

### 6a.6. Notification & Timer Loops

| Loop | Pattern | Empty-List Behavior |
|------|---------|---------------------|
| Due date notification loop | Iterates `assigned_user_ids` → checks `chore_is_actionable()` | ✅ No iterations |
| Overdue notification loop | Same pattern | ✅ No iterations |
| Due reminder loop | Same pattern | ✅ No iterations |
| Approval reset boundary processing | Iterates assignees to reset approval state | ✅ No iterations |

### 6a.7. What Actually Needs Changing (Mechanism 2)

The impact is remarkably small:

1. **Remove one validation guard** in `validate_chore_data()` (line ~1433-1440): allow empty `assigned_user_ids` on create
2. **Add explicit `total == 0` handling** in `compute_global_chore_state()`: return `pending` or a new derived state
3. **Rotation chore guard**: prevent removing the last assignee from a rotation chore (or auto-clear `rotation_current_assignee_id`)
4. **That's it.** Everything else already handles empty lists gracefully.

The "shared chores require at least 2" concern is **not currently enforced** in code — it's a logical expectation, not a hard constraint. Shared chores with 0-1 assignees would work mechanically (the FSM would just never reach `claimed_in_part`/`approved_in_part`), but the UX would be confusing. Recommend a **soft UI warning** rather than a hard block.

---

## 7. Phase Breakdown (Preliminary — Minimal Approach)

### Phase 1: User Unavailable Flag (#152 + Vacation)

**Goal**: One boolean, one behavior change. Users marked unavailable silently skip chores instead of going overdue.

- [ ] Add `DATA_USER_UNAVAILABLE: Final = "unavailable"` constant to `const.py`
- [ ] Schema migration v45→v46: default all existing users to `unavailable: false`
- [ ] In `resolve_assignee_chore_state`: when user is unavailable and chore would enter P5 (overdue), instead advance due date to next recurrence and return `pending` (or `due` if already in next window)
- [ ] In `chore_manager.py` overdue notification loop: skip unavailable users
- [ ] In `chore_manager.py` due reminder loop: skip unavailable users
- [ ] Add `set_user_unavailable` service (user_id, unavailable: bool)
- [ ] Rotation chore handling: skip unavailable user in `_advance_rotation()`

### Phase 2: Empty Assignee List (#125 + #151)

**Goal**: Allow `assigned_user_ids: []`. Chore stays in storage, entity processing stops.

- [ ] Relax validation in `data_builders.py` / `flow_helpers.py` to allow empty `assigned_user_ids`
- [ ] In entity platform setup: skip chore if `assigned_user_ids` is empty (no entities to create)
- [ ] In notification and overdue loops: skip chores with empty assignee list
- [ ] Add `remove_all_assignees(chore_id)` service
- [ ] Add `add_assignee(chore_id, user_id)` service
- [ ] Add `remove_all_assignees_by_label(label)` bulk service
- [ ] Config flow: allow creating chore with no users assigned (shows "Unassigned" badge)

### Phase 3: Dashboard (#151 Pool Card)

**Goal**: Dashboard templates handle zero-assignee chores and unavailable users.

- [ ] Pool card: query storage for chores where `assigned_user_ids == []` and render claim button per chore
- [ ] User chore cards: filter out chores for unavailable users (or show in "Paused" section)
- [ ] "Paused" indicator on user dashboard when `unavailable == true`
- [ ] Claim button on pool chores calls `add_assignee` service

### Phase 4: Testing

**Goal**: Coverage of both mechanisms and their interactions.

- [ ] Unit tests: overdue → skip transition when user unavailable
- [ ] Unit tests: empty assignee list skips entity creation
- [ ] Integration tests: `set_user_unavailable` service lifecycle
- [ ] Integration tests: `remove_all_assignees` → `add_assignee` round-trip
- [ ] Integration tests: rotation chore skips unavailable user
- [ ] Integration tests: shared chore with one unavailable user
- [ ] Integration tests: bulk `remove_all_assignees_by_label`
- [ ] Migration tests: v45 → v46 (users get `unavailable: false`)
- [ ] Dashboard snapshot tests: pool card, paused user card
- [ ] Notification suppression tests: unavailable user receives no due/overdue pings

---

## 8. Decisions & Completion Checklist

- [ ] **Approach selected** (A: Minimal Surface / B: Dual-Axis Unified / C: Tags & Rules)
- [ ] Schema version increment confirmed (`46`)
- [ ] `DATA_USER_UNAVAILABLE` constant defined in `const.py`
- [ ] Empty `assigned_user_ids` validation relaxed in data builders and flow helpers
- [ ] Translation keys identified (`TRANS_KEY_*` for new services, user unavailable state)
- [ ] No breaking changes to existing storage contracts (backward-compatible migration)
- [ ] User unavailable interaction with rotation chores designed
- [ ] User unavailable interaction with shared chores designed (other assignees unaffected)
- [ ] Dashboard pool card design for zero-assignee chores
- [ ] Dashboard paused-user card design for unavailable users
- [ ] All four use cases' acceptance criteria mapped to phases (#125, #151, #152, vacation)
- [ ] Release note category label identified

---

## 9. References

- [ARCHITECTURE.md](../ARCHITECTURE.md) — Data model, FSM contract, storage schema
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Coding standards, constant naming
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) — Phase 0 audit framework
- [QUALITY_REFERENCE.md](../QUALITY_REFERENCE.md) — Platinum quality requirements
- [Issue #125](https://github.com/ccpk1/ChoreOps/issues/125) — Seasonal chores
- [Issue #151](https://github.com/ccpk1/ChoreOps/issues/151) — Unassigned chores
- [Issue #152](https://github.com/ccpk1/ChoreOps/issues/152) — Global skip / custody mode
