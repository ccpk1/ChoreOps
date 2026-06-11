# Lexical Analysis: Avoiding "unavailable" Collision with Home Assistant

**Created**: 2026-06-05 | **Status**: Recommendation ready
**Triggered by**: `USER_AVAILABILITY_PLAN_IN-PROCESS.md` proposing `CHORE_STATE_UNAVAILABLE = "unavailable"`

---

## The Problem

Home Assistant reserves the entity state `"unavailable"` as a built-in protocol state — it means "the device/integration is offline, cannot be reached." It is defined in `homeassistant/const.py`:

```python
STATE_UNAVAILABLE: Final = "unavailable"
```

The User Availability plan proposes:

```python
CHORE_STATE_UNAVAILABLE: Final = "unavailable"
```

This creates a **lexical collision** between two distinct concepts:

| Concept | Meaning | Trigger |
|---------|---------|---------|
| HA entity `unavailable` | The sensor/device is offline, broken, or disconnected | Integration crash, network loss, setup failure |
| Proposed chore state `unavailable` | The user is away — their chores are paused | Admin sets user as away |

### How the collision manifests

The `AssigneeChoreStatusSensor.native_value` property (line ~891 of `sensor.py`) returns the chore state string directly:

```python
@property
def native_value(self) -> Any:
    ctx = self.coordinator.chore_manager.get_chore_status_context(
        self._assignee_id, self._chore_id
    )
    return cast("str", ctx[const.CHORE_CTX_STATE])
```

If the context returns `"unavailable"`, the sensor's displayed state becomes the string `"unavailable"`. To a user looking at their dashboard, this is **indistinguishable** from the sensor actually being offline/broken. The state badge looks identical.

### Existing precedent: `CHORE_STATE_UNKNOWN`

The codebase already collides with `STATE_UNKNOWN = "unknown"` via `CHORE_STATE_UNKNOWN = "unknown"`. However:
- `unknown` is a fallback state, rarely displayed to users
- `unknown` is less alarming — it means "don't know" in both contexts
- The proposed `unavailable` would be **actively displayed** whenever a user is away

The `unavailable` collision is therefore much more impactful than the existing `unknown` collision.

---

## Lexicon Standards Check

The DEVELOPMENT_STANDARDS.md §9 (Lexicon Standards) is explicit:

> **Critical Rule**: Never use "Entity" when referring to a Chore, Assignee, Badge, etc. These are **Items** in storage, not HA registry objects.

The ARCHITECTURE.md lexicon table reinforces:

| Term | Usage | Example |
|------|-------|---------|
| **Entity** | ONLY a Home Assistant platform object | Sensor, Button, Select |
| **Entity ID** | The Home Assistant registry string | `sensor.kc_alice_points` |

While these rules specifically address the Item/Entity distinction, the underlying principle applies here: **ChoreOps domain concepts must not use the same terms as HA platform concepts in ways that create ambiguity.**

Using `"unavailable"` as a chore state value creates exactly this kind of ambiguity — is the sensor entity unavailable (broken), or is the user's chore paused (by design)?

---

## Decision Criteria

A suitable replacement term must satisfy ALL of these:

| Criterion | Requirement |
|-----------|------------|
| **HA collision** | Must NOT match any HA built-in state (`on`, `off`, `unavailable`, `unknown`) |
| **Entity confusion** | Must NOT suggest the sensor/device is broken or offline |
| **Meaning clarity** | Must clearly convey "this user's chores are temporarily suspended" |
| **Existing pattern fit** | Must follow `CHORE_STATE_*` naming conventions (single word, lowercase) |
| **Dashboard readability** | Must work as a short status badge label |
| **Translation fit** | Must have a clear, concise English translation |
| **Sort order semantics** | Must slot logically into the actionability sort chain |
| **Storage key fit** | Must work as both a `DATA_USER_*` key and a `CHORE_STATE_*` display value |

---

## Options Evaluated

### Option A: `paused` ⭐ RECOMMENDED

| Level | Constant | Value |
|-------|----------|-------|
| Storage (user flag) | `DATA_USER_CHORES_PAUSED` | `"chores_paused"` |
| Storage (return date) | `DATA_USER_CHORES_PAUSED_UNTIL` | `"chores_paused_until"` |
| Display (chore state) | `CHORE_STATE_PAUSED` | `"paused"` |
| Claim mode | `CHORE_CLAIM_MODE_BLOCKED_PAUSED` | `"blocked_paused"` |

**Pros**:
- Zero collision with HA built-in states ✅
- Single word, follows existing `CHORE_STATE_*` pattern ✅
- Clear meaning: chores are paused for this user ✅
- Dashboard-friendly: short label ("Paused") ✅
- `CHORES_PAUSED` in storage key makes scope explicit (chore processing, not account status) ✅
- Sort order: between `completed_by_other` (6) and `not_my_turn` (8) — paused is a neutral administrative state ✅

**Cons**:
- Minor: `paused` could theoretically be confused with "chore is paused globally." Mitigated by context — each user sees their own chore state. Admin dashboard shows per-user states.
- Minor: Home Assistant uses "paused" for automations, but that's an automation state, not an entity state. No collision risk.

### Option B: `away`

| Level | Constant | Value |
|-------|----------|-------|
| Storage | `DATA_USER_AWAY` | `"away"` |
| Storage | `DATA_USER_AWAY_UNTIL` | `"away_until"` |
| Display | `CHORE_STATE_AWAY` | `"away"` |
| Claim mode | `CHORE_CLAIM_MODE_BLOCKED_AWAY` | `"blocked_away"` |

**Pros**: Short (4 chars), no HA collision, very clear meaning
**Cons**: "away" describes the USER, not the CHORE state. A chore state called "away" reads oddly — "this chore is away." The existing states describe the chore's status relative to the user (`not_my_turn`, `completed_by_other`), not the user's status.

### Option C: `suspended`

**Pros**: Formal, clear, no HA collision
**Cons**: 9 chars (longest option), "suspended" carries disciplinary connotations, heavier tone than the friendly language used elsewhere

### Option D: `on_hold`

**Pros**: Friendly, clear meaning
**Cons**: Two words with underscore (`on_hold`), breaks the single-word pattern of all other states, awkward in sort order logic

### Option E: `absent`

**Pros**: No HA collision, precise meaning
**Cons**: Similar to `away` — describes user state, not chore state. Reads oddly: "this chore is absent."

### Option F: `inactive`

**Pros**: Short, clear
**Cons**: Ambiguous — "inactive" could mean the chore was disabled/deleted, not temporarily paused

---

## Recommendation: `paused`

`paused` is the recommended term across all levels — storage constants, display states, claim modes, and translations.

### Why `paused` wins

1. **No HA collision**: `"paused"` is not a Home Assistant protocol state. The closest HA concept is automation state, which is a different domain (automation config, not entity state).

2. **Describes the chore, not the user**: All existing `CHORE_STATE_*` values describe the chore's status relative to the assignee: `pending`, `due`, `waiting`, `claimed`, `overdue`, `missed`, `not_my_turn`, `completed`, `completed_by_other`. `paused` continues this pattern — the chore IS paused (for this user). Contrast with `away`/`absent` which describe the user.

3. **Storage key scoping**: `DATA_USER_CHORES_PAUSED` makes it explicit that this flag affects chore processing, not the user's account status. This prevents future confusion if other "pause" concepts are added (e.g., pausing notifications, pausing point accrual).

4. **Translation naturalness**:
   - English: "Paused" — natural, friendly
   - Spanish: "Pausado" — natural
   - French: "En pause" — natural
   - German: "Pausiert" — natural

5. **Dashboard sort order**: `paused` slots naturally at priority 5-6 — above `completed_by_other` (terminal states) but below `overdue`/`due` (actionable states). It's an administrative state that needs attention but isn't urgent.

---

## Updated Constant Map

### Storage constants (`const.py`)

```python
# User data fields (near DATA_USER_CAN_BE_ASSIGNED, ~line 1235)
DATA_USER_CHORES_PAUSED: Final = "chores_paused"
DATA_USER_CHORES_PAUSED_UNTIL: Final = "chores_paused_until"
```

### State constants (`const.py`)

```python
# Derived UI-only states (near CHORE_STATE_NOT_MY_TURN, ~line 1859)
CHORE_STATE_PAUSED: Final = "paused"

# Must be added to CHORE_UI_ASSIGNEE_STATES frozenset (~line 1889)

# Claim modes (near CHORE_CLAIM_MODE_BLOCKED_MISSED_LOCKED, ~line 1926)
CHORE_CLAIM_MODE_BLOCKED_PAUSED: Final = "blocked_paused"

# Must be added to CHORE_CLAIM_MODES frozenset
```

### CFOF constants (`const.py`)

```python
# Near CFOF_USERS_INPUT_CAN_BE_ASSIGNED
CFOF_USERS_INPUT_CHORES_PAUSED: Final = "chores_paused"
CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL: Final = "chores_paused_until"
```

### Translation key constants (`const.py`)

```python
TRANS_KEY_ERROR_CHORE_PAUSED: Final = "chore_paused"
```

### Translations (`en.json`)

```json
{
  "entity": {
    "sensor": {
      "chore_status_sensor": {
        "state": {
          "paused": "Paused"
        },
        "state_attributes": {
          "claim_mode": {
            "state": {
              "blocked_paused": "Chores are paused for this user"
            }
          }
        }
      }
    }
  },
  "exceptions": {
    "chore_paused": "Chores are currently paused for {user_name}. They cannot claim or be assigned overdue or missed chores."
  }
}
```

### Dashboard translations (`en_dashboard.json`)

```json
{
  "paused": "Paused",
  "blocked_paused": "Paused"
}
```

---

## Impact on Existing Plans

Both `USER_AVAILABILITY_PLAN_IN-PROCESS.md` and `CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md` use `unavailable` throughout. Every occurrence of the following should be replaced:

| Old term | New term |
|----------|----------|
| `CHORE_STATE_UNAVAILABLE` | `CHORE_STATE_PAUSED` |
| `CHORE_CLAIM_MODE_BLOCKED_UNAVAILABLE` | `CHORE_CLAIM_MODE_BLOCKED_PAUSED` |
| `DATA_USER_UNAVAILABLE` | `DATA_USER_CHORES_PAUSED` |
| `DATA_USER_UNAVAILABLE_UNTIL` | `DATA_USER_CHORES_PAUSED_UNTIL` |
| `_process_overdue` guard comment: "Skip unavailable users" | "Skip users with chores paused" |
| `_record_chore_missed` guard comment: "No missed recording for unavailable users" | "No missed recording when chores paused" |
| `_advance_rotation` guard comment: "Skip unavailable users in rotation" | "Skip users with chores paused in rotation" |
| `get_chore_status_context` comment: "P0 — User unavailable" | "P0 — User chores paused" |
| Dashboard state label: `"unavailable": "Unavailable"` | `"paused": "Paused"` |
| Dashboard claim mode: `"blocked_unavailable"` | `"blocked_paused"` |
| Dashboard icon: `mdi:account-cancel-outline` | `mdi:pause-circle-outline` |
| Admin workflow card title: "Set User as Unavailable" | "Pause User's Chores" |
| Admin workflow card description references to "unavailable" | "paused" |
| `choreops.set_user_availability` service | `choreops.pause_user_chores` |
| All edge case descriptions referencing "unavailable" | "chores paused" |

---

## Notes

- **Dashboard icon change**: `mdi:account-cancel-outline` (user cancelled/blocked) → `mdi:pause-circle-outline` (paused). This is semantically more accurate — the user isn't cancelled, their chores are paused.
- **Service naming**: `choreops.pause_user_chores` is more descriptive than `choreops.set_user_availability`. It tells you exactly what the service does.
- **Cross-plan document**: `CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md` uses "unavailable" ~40 times. All should be updated to `paused` / `chores paused` before either plan enters implementation.
- **No schema version bump needed**: The field key changes from `"unavailable"` to `"chores_paused"`, but since neither has been implemented yet, there's no migration concern. If user availability ships after primary-backup, the schema version bump happens once when `DATA_USER_CHORES_PAUSED` is first added.

> **Analysis created**: 2026-06-05 | **Recommendation**: Adopt `paused` / `chores_paused` throughout both plans.
