# Unified Data Reset Service V2 - Implementation Plan

## Initiative snapshot

- **Name / Code**: Unified Data Reset Service V2 (`reset_transactional_data`)
- **Target release / milestone**: v0.5.0
- **Owner / driver(s)**: Strategic Planning Agent → Builder Agent
- **Status**: In progress
- **Breaking Change**: Yes - Replaces `reset_all_chores`, `reset_rewards`, `reset_penalties`, `reset_bonuses`. Also renames `reset_all_data` → `factory_reset`.

## Summary & immediate steps

| Phase / Step                   | Description                                         | % complete | Quick notes                                                                                 |
| ------------------------------ | --------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------- |
| Phase 1 – Field Definitions    | Define preserve/runtime field sets in data_builders | 100%       | ✅ All 6 frozensets defined                                                                 |
| Phase 2 – Constants & Signals  | Add signals, service constants, translations        | 100%       | ✅ 8 signals + item_type terminology adopted                                                |
| Phase 3 – Manager Handlers     | Implement data*reset*\*() in domain managers        | 100%       | ✅ All 9 handlers + StatisticsManager listeners                                             |
| **Phase 3B – Landlord/Tenant** | **Ownership boundaries + Genesis initialization**   | **100%**   | ✅ Multiplier signal, Genesis structures, Tenant guards                                     |
| Phase 4 – SystemManager        | Implement orchestration method                      | 100%       | ✅ Direct calls, backup, scope validation, broadcast notification, order & multiplier fixes |
| Phase 5 – Service Registration | Register service in services.py + services.yaml     | 100%       | ✅ Schema, handler, YAML definition, en.json translations                                   |
| Phase 6 – Testing              | Comprehensive test coverage                         | 100%       | 14 tests created, all passing                                                               |
| Phase 7 – Cleanup              | Remove legacy code and old plan                     | 100%       | ✅ 7A-7E done; 7F-7G remaining (archive, deferred architecture)                             |

1. **Key objective** – Replace 4 legacy reset services with ONE unified `reset_transactional_data` service. Uses "Direct Call + Completion Signal" architecture where SystemManager calls domain managers directly, each manager persists and emits completion signal.

2. **Summary of recent work** – **Phase 7A-7E COMPLETE**: Legacy services removed (`reset_rewards`, `reset_penalties`, `reset_bonuses`), service renames done (`reset_all_data` → `factory_reset`, `reset_all_chores` → `reset_chores_to_pending_state`), migration cleanup added for `DATA_KID_OVERDUE_CHORES_LEGACY`. All 1199 tests passing.

3. **Next steps (short term)** – **Phase 7F**: Archive old plan. Phase 7G: Deferred architectural cleanup (stats consolidation).

4. **Risks / blockers** – Breaking change (old services removed). Phase 3B resolved critical resurrection bug vulnerability.

5. **References**:
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and storage structure
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Constant naming and Manager patterns
   - [services.py](../../custom_components/kidschores/services.py) - Existing service patterns
   - [data_builders.py](../../custom_components/kidschores/data_builders.py) - Field definitions location

6. **Decisions & completion check**
   - **Decisions captured**:
     - **Architecture**: Direct Call + Completion Signal (NOT signal-initiated)
     - **Field definitions**: Frozensets in data_builders.py (NO pure functions)
     - **Reset logic**: Lives in domain Managers (NOT in data_builders or helpers)
     - **Persistence**: Each Manager calls `_persist()` individually (debounce handles efficiency)
     - **Global scope**: Via `scope: "global"` or omit scope (no convenience method)
     - **Service name**: `reset_transactional_data`
     - **Safety**: Required `confirm_destructive: true` field
     - **Backup**: Created before any reset via existing backup infrastructure
     - **Services KEPT**: `reset_overdue_chores` (specialized workflow), `remove_awarded_badges` (different purpose)
     - **Factory reset**: Rename `reset_all_data` → `factory_reset` (clarify total-wipe nature)
     - **reset_all_chores**: Rename to `reset_chores_to_pending_state` (state reset, not data reset) - SEPARATE from unified service
     - **Kid-side field organization**: Per-domain frozensets in data_builders.py (e.g., `_CHORE_KID_RUNTIME_FIELDS`, `_BADGE_KID_RUNTIME_FIELDS`)
     - **Signal payloads**: Standard format with `scope: str, kid_id: str | None, item_id: str | None`
   - **Completion confirmation**: `[ ]` All follow-up items completed before marking done

---

## ⚠️ CRITICAL: Naming Convention (Non-Negotiable)

**THE TERM "RESET" MUST NEVER APPEAR ALONE IN THIS CODEBASE**

### Mandatory Pattern: Always Qualify as "data_reset"

| ❌ FORBIDDEN         | ✅ REQUIRED                  |
| -------------------- | ---------------------------- |
| `reset_kid()`        | `data_reset_kid()`           |
| `reset_helpers.py`   | `data_reset_helpers.py`      |
| `RESET_SCOPE_GLOBAL` | `DATA_RESET_SCOPE_GLOBAL`    |
| `handle_reset()`     | `handle_data_reset()`        |
| `# Reset points`     | `# Data reset: Clear points` |
| `BACKUP_TAG_RESET`   | `BACKUP_TAG_DATA_RESET`      |

**Why This Matters:**

- Avoids confusion with UI resets, connection resets, state machine resets
- Makes grep/search results unambiguous
- Self-documenting code (clear what kind of reset)

**Applies To:**

- Python function/method names
- Python variable names
- Constant names in const.py
- File names (modules, helpers)
- Code comments and docstrings
- Translation keys
- Log messages, error messages
- Test function names

**Exceptions:**

- `factory_reset` - explicit enough (total wipe)
- `reset_transactional_data` - already qualified by service name
- `reset_chores_to_pending_state` - qualified by action description
- `reset_overdue_chores` - existing specialized workflow (kept as-is)

---

## ✅ RESOLVED: Architecture Decisions

### Decision 1: Kid-Side Runtime Field Set Organization

**Decision**: **Option B** - Per-domain frozensets in data_builders.py

Each domain manager has its own frozenset defining which kid-side structures it owns:

```python
# In data_builders.py, after build_chore()
_CHORE_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
    const.DATA_KID_CHORE_DATA,
    const.DATA_KID_CHORE_STATS,
    const.DATA_KID_OVERDUE_CHORES,
})

# After build_badge()
_BADGE_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
    const.DATA_KID_BADGES_EARNED,
    const.DATA_KID_BADGE_PROGRESS,
    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS,
})

# After build_reward()
_REWARD_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
    const.DATA_KID_REWARD_DATA,
})

# After build_penalty()
_PENALTY_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
    const.DATA_KID_PENALTY_APPLIES,
})

# After build_bonus()
_BONUS_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
    const.DATA_KID_BONUS_APPLIES,
})

# After build_kid() - scalar fields owned by EconomyManager
_KID_SCALAR_RUNTIME_FIELDS: frozenset[str] = frozenset({
    const.DATA_KID_POINTS,
    const.DATA_KID_CURRENT_STREAK,
    const.DATA_KID_OVERALL_CHORE_STREAK,
    const.DATA_KID_LAST_CHORE_DATE,
    const.DATA_KID_LAST_STREAK_DATE,
    const.DATA_KID_LEDGER,
    const.DATA_KID_POINT_DATA,
})
```

**Rationale**: Clear ownership per domain, single source of truth in data_builders.py, matches existing preserve-field pattern.

---

### Decision 2: Completion Signal Payloads

**Decision**: **Standard payload** with 3 fields

```python
self.emit(
    SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE,
    scope=scope,       # "global" | "kid" | "item_type" | "item"
    kid_id=kid_id,     # str | None
    item_id=item_id,   # str | None (only for item scope)
)
```

**All 8 signals use the same payload format:**

| Signal                                          | Emitter             | Payload                  |
| ----------------------------------------------- | ------------------- | ------------------------ |
| `SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE`       | ChoreManager        | `scope, kid_id, item_id` |
| `SIGNAL_SUFFIX_KID_DATA_RESET_COMPLETE`         | EconomyManager      | `scope, kid_id, item_id` |
| `SIGNAL_SUFFIX_BADGE_DATA_RESET_COMPLETE`       | GamificationManager | `scope, kid_id, item_id` |
| `SIGNAL_SUFFIX_ACHIEVEMENT_DATA_RESET_COMPLETE` | GamificationManager | `scope, kid_id, item_id` |
| `SIGNAL_SUFFIX_CHALLENGE_DATA_RESET_COMPLETE`   | GamificationManager | `scope, kid_id, item_id` |
| `SIGNAL_SUFFIX_REWARD_DATA_RESET_COMPLETE`      | RewardManager       | `scope, kid_id, item_id` |
| `SIGNAL_SUFFIX_PENALTY_DATA_RESET_COMPLETE`     | EconomyManager      | `scope, kid_id, item_id` |
| `SIGNAL_SUFFIX_BONUS_DATA_RESET_COMPLETE`       | EconomyManager      | `scope, kid_id, item_id` |

**Rationale**: Enables targeted cache invalidation by StatisticsManager without over-engineering.

---

## Service Clarification: What's Changing

### Services Being REPLACED by `reset_transactional_data`

| Old Service       | New Equivalent         | Migration          |
| ----------------- | ---------------------- | ------------------ |
| `reset_rewards`   | `item_type: rewards`   | Direct replacement |
| `reset_penalties` | `item_type: penalties` | Direct replacement |
| `reset_bonuses`   | `item_type: bonuses`   | Direct replacement |

### Services Being RENAMED (Not Removed)

| Old Name           | New Name                        | Rationale                                 |
| ------------------ | ------------------------------- | ----------------------------------------- |
| `reset_all_data`   | `factory_reset`                 | Clarifies total-wipe behavior             |
| `reset_all_chores` | `reset_chores_to_pending_state` | Clarifies it's state reset not data reset |

### Services KEPT As-Is

| Service                 | Reason                                                              |
| ----------------------- | ------------------------------------------------------------------- |
| `reset_overdue_chores`  | Specialized workflow (reschedules due dates, handles notifications) |
| `remove_awarded_badges` | Different purpose (selective badge removal, not data reset)         |

---

## Critical Architecture: Direct Call + Completion Signal

```
┌─────────────────────────────────────────────────────────────────────┐
│           DIRECT CALL + COMPLETION SIGNAL ARCHITECTURE              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Service Handler (services.py)                                      │
│       │                                                             │
│       ▼ call coordinator.system_manager.orchestrate_data_reset()    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  SystemManager (orchestrator)                                │   │
│  │  1. Validates scope, creates backup                         │   │
│  │  2. DIRECTLY CALLS each domain manager:                     │   │
│  │     await chore_manager.data_reset_chores(scope, kid_id)    │   │
│  │     await gamification_manager.data_reset_badges(...)       │   │
│  │     await economy_manager.data_reset_kids(...)              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ▼ (each manager does its work, persists, emits completion)   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ DomainManager.data_reset_*()                                 │  │
│  │  1. Modify data structures using field frozensets            │  │
│  │  2. self._persist()  ← Individual persist (debounced)       │  │
│  │  3. emit SIGNAL_SUFFIX_*_DATA_RESET_COMPLETE                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  StatisticsManager (listener)                                       │
│  - Listens for *_DATA_RESET_COMPLETE signals                       │
│  - Invalidates/recalculates caches                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Item Type Master Mapping

| Item Type      | Master Manager        | Handler Method              |
| -------------- | --------------------- | --------------------------- |
| `chores`       | `ChoreManager`        | `data_reset_chores()`       |
| `kids`         | `UserManager`         | `data_reset_kids()`         |
| `badges`       | `GamificationManager` | `data_reset_badges()`       |
| `achievements` | `GamificationManager` | `data_reset_achievements()` |
| `challenges`   | `GamificationManager` | `data_reset_challenges()`   |
| `rewards`      | `RewardManager`       | `data_reset_rewards()`      |
| `penalties`    | `EconomyManager`      | `data_reset_penalties()`    |
| `bonuses`      | `EconomyManager`      | `data_reset_bonuses()`      |

---

## Detailed phase tracking

### Phase 1 – Field Definitions in data_builders.py

- **Goal**: Define frozensets that specify which fields to PRESERVE during data reset AND which kid-side structures each domain owns. These are the source of truth - Managers import them.
- **Steps / detailed work items**

  #### 1A: Review Existing Field Sets
  - Check what already exists in data_builders.py:
    - `_KID_DATA_RESET_PRESERVE_FIELDS` - exists ✅
    - `_KID_RUNTIME_DATA_STRUCTURES` - exists but will be REPLACED by per-domain sets
    - `_CHORE_DATA_RESET_PRESERVE_FIELDS` - exists ✅
    - `_CHORE_PER_KID_RUNTIME_LISTS` - exists ✅
    - `_BADGE_DATA_RESET_PRESERVE_FIELDS` - exists ✅
  - **Action**: Remove `_KID_RUNTIME_DATA_STRUCTURES`, add per-domain kid runtime sets

  #### 1B: Kid Preserve Fields (verify existing)
  - Location: `data_builders.py` after `build_kid()` function
  - Verify existing `_KID_DATA_RESET_PRESERVE_FIELDS` is complete

  #### 1C: Kid Scalar Runtime Fields (NEW)
  - Add after `_KID_DATA_RESET_PRESERVE_FIELDS`:
    ```python
    # Scalar runtime fields owned by EconomyManager (data_reset_kids)
    # NOTE: point_stats excluded - will be eliminated in Phase 7G
    _KID_SCALAR_RUNTIME_FIELDS: frozenset[str] = frozenset({
        const.DATA_KID_POINTS,
        const.DATA_KID_CURRENT_STREAK,
        const.DATA_KID_OVERALL_CHORE_STREAK,
        const.DATA_KID_LAST_CHORE_DATE,
        const.DATA_KID_LAST_STREAK_DATE,
        const.DATA_KID_LEDGER,
        const.DATA_KID_POINT_DATA,
    })
    ```

  #### 1D: Chore Kid Runtime Fields (NEW)
  - Add after `_CHORE_PER_KID_RUNTIME_LISTS`:
    ```python
    # Kid-side structures owned by ChoreManager (data_reset_chores)
    # NOTE: chore_stats excluded - will be eliminated in Phase 7G
    _CHORE_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
        const.DATA_KID_CHORE_DATA,
        const.DATA_KID_OVERDUE_CHORES,
    })
    ```

  #### 1E: Badge Kid Runtime Fields (NEW)
  - Add after `_BADGE_DATA_RESET_PRESERVE_FIELDS`:
    ```python
    # Kid-side structures owned by GamificationManager (data_reset_badges)
    _BADGE_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
        const.DATA_KID_BADGES_EARNED,
        const.DATA_KID_BADGE_PROGRESS,
        const.DATA_KID_CUMULATIVE_BADGE_PROGRESS,
    })
    ```

  #### 1F: Reward Kid Runtime Fields (NEW)
  - Add after `build_reward()` section:
    ```python
    # Kid-side structures owned by RewardManager (data_reset_rewards)
    _REWARD_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
        const.DATA_KID_REWARD_DATA,
    })
    ```

  #### 1G: Penalty Kid Runtime Fields (NEW)
  - Add after `build_penalty()` section:
    ```python
    # Kid-side structures owned by EconomyManager (data_reset_penalties)
    _PENALTY_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
        const.DATA_KID_PENALTY_APPLIES,
    })
    ```

  #### 1H: Bonus Kid Runtime Fields (NEW)
  - Add after `build_bonus()` section:
    ```python
    # Kid-side structures owned by EconomyManager (data_reset_bonuses)
    _BONUS_KID_RUNTIME_FIELDS: frozenset[str] = frozenset({
        const.DATA_KID_BONUS_APPLIES,
    })
    ```

  #### 1I: Achievement/Challenge Preserve Fields (verify existing or add)
  - Verify `_ACHIEVEMENT_DATA_RESET_PRESERVE_FIELDS` exists
  - Verify `_CHALLENGE_DATA_RESET_PRESERVE_FIELDS` exists
  - Note: Achievements/challenges have NO kid-side structures (progress stored on entity itself)

  #### 1J: Remove Old Aggregate Set
  - Delete `_KID_RUNTIME_DATA_STRUCTURES` (replaced by per-domain sets)

- **Key issues**:
  - Must verify all existing frozensets are complete before adding new ones
  - Run `./utils/quick_lint.sh` after changes

### Phase 2 – Constants & Signals in const.py

- **Goal**: Add completion signals, service constants, and translation keys
- **Steps / detailed work items**

  #### 2A: Add Completion Signal Constants
  - File: `custom_components/kidschores/const.py`
  - Location: Signal suffix section (~line 2180)
  - Add:
    ```python
    # Data reset completion signals (emitted AFTER reset work is done)
    SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE: Final = "chore_data_reset_complete"
    SIGNAL_SUFFIX_KID_DATA_RESET_COMPLETE: Final = "kid_data_reset_complete"
    SIGNAL_SUFFIX_BADGE_DATA_RESET_COMPLETE: Final = "badge_data_reset_complete"
    SIGNAL_SUFFIX_ACHIEVEMENT_DATA_RESET_COMPLETE: Final = "achievement_data_reset_complete"
    SIGNAL_SUFFIX_CHALLENGE_DATA_RESET_COMPLETE: Final = "challenge_data_reset_complete"
    SIGNAL_SUFFIX_REWARD_DATA_RESET_COMPLETE: Final = "reward_data_reset_complete"
    SIGNAL_SUFFIX_PENALTY_DATA_RESET_COMPLETE: Final = "penalty_data_reset_complete"
    SIGNAL_SUFFIX_BONUS_DATA_RESET_COMPLETE: Final = "bonus_data_reset_complete"
    ```

  #### 2B: Add Service Constants (verify/add if missing)
  - Service and field constants:
    ```python
    SERVICE_RESET_TRANSACTIONAL_DATA = "reset_transactional_data"
    SERVICE_FIELD_CONFIRM_DESTRUCTIVE = "confirm_destructive"
    SERVICE_FIELD_SCOPE = "scope"
    SERVICE_FIELD_KID_NAME = "kid_name"
    SERVICE_FIELD_ITEM_TYPE = "item_type"  # Used for both item_type scope AND item scope
    SERVICE_FIELD_ITEM_NAME = "item_name"
    ```
  - Scope constants (use DATA*RESET* prefix per naming convention):
    ```python
    DATA_RESET_SCOPE_GLOBAL = "global"
    DATA_RESET_SCOPE_KID = "kid"
    DATA_RESET_SCOPE_ITEM_TYPE = "item_type"
    DATA_RESET_SCOPE_ITEM = "item"
    ```
  - Item type constants:
    ```python
    DATA_RESET_ITEM_TYPE_KIDS = "kids"
    DATA_RESET_ITEM_TYPE_CHORES = "chores"
    DATA_RESET_ITEM_TYPE_REWARDS = "rewards"
    DATA_RESET_ITEM_TYPE_BADGES = "badges"
    DATA_RESET_ITEM_TYPE_ACHIEVEMENTS = "achievements"
    DATA_RESET_ITEM_TYPE_CHALLENGES = "challenges"
    DATA_RESET_ITEM_TYPE_PENALTIES = "penalties"
    DATA_RESET_ITEM_TYPE_BONUSES = "bonuses"
    ```
  - Backup tag:
    ```python
    BACKUP_TAG_DATA_RESET = "data_reset"
    ```

  #### 2C: Add Error Translation Keys
  - Add to const.py (translation keys section):
    ```python
    TRANS_KEY_SERVICE_DATA_RESET_CONFIRMATION_REQUIRED = "service_data_reset_confirmation_required"
    TRANS_KEY_SERVICE_DATA_RESET_KID_NOT_FOUND = "service_data_reset_kid_not_found"
    TRANS_KEY_SERVICE_DATA_RESET_ITEM_NOT_FOUND = "service_data_reset_item_not_found"
    TRANS_KEY_SERVICE_DATA_RESET_INVALID_SCOPE = "service_data_reset_invalid_scope"
    TRANS_KEY_SERVICE_DATA_RESET_INVALID_ITEM_TYPE = "service_data_reset_invalid_item_type"
    ```
  - Add to translations/en.json:
    ```json
    "service_data_reset_confirmation_required": "You must set confirm_destructive: true to proceed with data reset",
    "service_data_reset_kid_not_found": "Kid '{kid_name}' not found",
    "service_data_reset_item_not_found": "{item_type} '{item_name}' not found",
    "service_data_reset_invalid_scope": "Invalid scope '{scope}'. Must be: global, kid, item_type, or item",
    "service_data_reset_invalid_item_type": "Invalid item_type '{item_type}'. Must be: kids, chores, rewards, badges, achievements, challenges, penalties, or bonuses"
    ```

  #### 2D: Add Notification Translation Keys
  - Add to const.py:
    ```python
    TRANS_KEY_NOTIF_TITLE_DATA_RESET = "notif_title_data_reset"
    TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_GLOBAL = "notif_message_data_reset_global"
    TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_KID = "notif_message_data_reset_kid"
    TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ITEM_TYPE = "notif_message_data_reset_item_type"
    TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ITEM = "notif_message_data_reset_item"
    ```
  - Add to translations/en.json:
    ```json
    "notif_title_data_reset": "Transactional Data Reset",
    "notif_message_data_reset_global": "All runtime data has been reset. Configuration preserved.",
    "notif_message_data_reset_kid": "Data reset complete for {kid_name}. Points, stats, and progress cleared.",
    "notif_message_data_reset_item_type": "Data reset complete for all {item_type}. Runtime data cleared.",
    "notif_message_data_reset_item": "Data reset complete for {item_name}. Runtime data cleared."
    ```

- **Key issues**: Check if some constants already exist from V1 work

### Phase 3 – Manager Data Reset Handlers

- **Goal**: Implement `data_reset_*()` methods in each domain Manager
- **Steps / detailed work items**

  #### 3A: ChoreManager.data_reset_chores()
  - File: `managers/chore_manager.py`
  - Method signature: `async def data_reset_chores(self, scope: str, kid_id: str | None = None) -> None`
  - Implementation:
    1. Import field sets from data_builders
    2. Loop through chores, reset runtime fields (state, claimed_by, etc.)
    3. If kid_id provided, only remove that kid from lists
    4. Clean kid-side chore_data entries
    5. `self._persist()`
    6. `self.emit(SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE, ...)`

  #### 3B: EconomyManager.data_reset_kids()
  - File: `managers/economy_manager.py`
  - Method signature: `async def data_reset_kids(self, scope: str, kid_id: str | None = None) -> None`
  - Implementation:
    1. Import field sets from data_builders
    2. Loop through kids (or single kid if kid_id provided)
    3. Reset scalar runtime fields (points=0, streaks=0, etc.)
    4. Delete runtime data structures (chore_data, badges_earned, etc.)
    5. `self._persist()`
    6. `self.emit(SIGNAL_SUFFIX_KID_DATA_RESET_COMPLETE, ...)`

  #### 3C: EconomyManager.data_reset_penalties()
  - Method: Clear `kid[penalty_applies]` entries
  - Persist + emit

  #### 3D: EconomyManager.data_reset_bonuses()
  - Method: Clear `kid[bonus_applies]` entries
  - Persist + emit

  #### 3E: GamificationManager.data_reset_badges()
  - File: `managers/gamification_manager.py`
  - Method: Reset earned_by lists on badges, clean kid badges_earned entries
  - Persist + emit

  #### 3F: GamificationManager.data_reset_achievements()
  - Method: Clear progress dicts on achievements
  - Persist + emit

  #### 3G: GamificationManager.data_reset_challenges()
  - Method: Clear progress dicts on challenges
  - Persist + emit

  #### 3H: RewardManager.data_reset_rewards()
  - File: `managers/reward_manager.py`
  - Method: Clear `kid[reward_data]` entries
  - Persist + emit

  #### 3I: StatisticsManager Listeners
  - File: `managers/statistics_manager.py`
  - Add listeners for all `*_DATA_RESET_COMPLETE` signals
  - Handler: Invalidate/schedule cache refresh

- **Key issues**:
  - Each Manager must import field sets from data_builders
  - Ensure persist is called before emit (data consistency)

### Phase 3B – Landlord/Tenant Ownership Model (NEW - Critical)

- **Goal**: Establish clear data ownership boundaries to prevent "Resurrection Bugs" where StatisticsManager's `setdefault()` recreates deleted data after a reset operation.

- **Problem Statement**: Currently StatisticsManager uses `setdefault()` to lazily create structures like `point_stats`, `point_data`, and `chore_data`. If we reset/delete these structures, a stray signal (delayed approval, etc.) can cause StatisticsManager to recreate them, defeating the reset.

- **Solution**: "Landlord and Tenant" model where:
  - **Landlords** (domain managers) own and create their data structures
  - **Tenants** (StatisticsManager) only write to sub-keys within Landlord-created containers
  - If a Tenant receives an event for a missing container, it logs a warning and skips (never recreates)

---

#### Landlord Ownership Matrix

| Structure                          | Landlord (Owner)        | Tenants           | Genesis Location              |
| ---------------------------------- | ----------------------- | ----------------- | ----------------------------- |
| `points`, `points_multiplier`      | **EconomyManager**      | None              | `build_kid()` ✅              |
| `ledger`                           | **EconomyManager**      | None              | `build_kid()` ✅              |
| `point_stats`                      | **EconomyManager**      | StatisticsManager | ❌ Add to `build_kid()`       |
| `point_data.periods`               | **EconomyManager**      | StatisticsManager | ❌ Add to `build_kid()`       |
| `chore_data`                       | **ChoreManager**        | StatisticsManager | On-demand when chore assigned |
| `chore_stats`                      | **ChoreManager**        | StatisticsManager | ❌ Add to `build_kid()`       |
| `badges_earned`                    | **GamificationManager** | None              | `build_kid()` ✅              |
| `badge_progress`                   | **GamificationManager** | None              | Lazy OK (Landlord owns)       |
| `cumulative_badge_progress`        | **GamificationManager** | None              | Lazy OK (Landlord owns)       |
| `reward_data`                      | **RewardManager**       | None              | `build_kid()` ✅              |
| `penalty_applies`, `bonus_applies` | **EconomyManager**      | None              | `build_kid()` ✅              |

---

#### Dependency Chain Mapping (Reset Cascades)

```
RESET: chores
├─ ChoreManager deletes: chore_data[*]
├─ StatisticsManager: Receives DATA_RESET_COMPLETE → invalidates cache
└─ GamificationManager: Receives DATA_RESET_COMPLETE → recalculates badge_progress

RESET: kids (economy)
├─ EconomyManager deletes: points→0, ledger→[], point_stats→zeroed, point_data→{}
├─ StatisticsManager: Receives DATA_RESET_COMPLETE → invalidates cache
└─ GamificationManager: multiplier unaffected (config), badge_progress zeroed via signal

RESET: badges
├─ GamificationManager deletes: badges_earned, badge_progress, cumulative_badge_progress
├─ EconomyManager: Receives MULTIPLIER_CHANGE_REQUESTED → sets multiplier to 1.0
└─ StatisticsManager: No action (doesn't track badge stats)

RESET: rewards
├─ RewardManager deletes: reward_data[*]
└─ StatisticsManager: Receives DATA_RESET_COMPLETE → invalidates cache

RESET: penalties/bonuses
├─ EconomyManager deletes: penalty_applies, bonus_applies
└─ No cascade dependencies
```

---

#### Decisions (Resolved)

| Question                         | Decision                                                                   |
| -------------------------------- | -------------------------------------------------------------------------- |
| Genesis location                 | **Option A**: Extend `build_kid()` with all empty containers               |
| `chore_data.{chore_id}` creation | On-demand by **ChoreManager** when chore assigned (not pre-created)        |
| Missing container handling       | **Log warning and skip** (don't mask bugs with diagnostic signals)         |
| Reset cascade policy             | **Option B**: Emit data reset signal, let receiving managers decide action |

---

#### Implementation Steps

##### 3B.1: Multiplier Ownership Transfer ✅ COMPLETE

**Current (WRONG)**: GamificationManager directly writes `DATA_KID_POINTS_MULTIPLIER`

```python
# gamification_manager.py:1392
kid_info[const.DATA_KID_POINTS_MULTIPLIER] = multiplier  # Direct write - VIOLATES OWNERSHIP
```

**Target (CORRECT)**: Signal-based, EconomyManager writes

```python
# GamificationManager emits
self.emit(const.SIGNAL_SUFFIX_MULTIPLIER_CHANGE_REQUESTED,
    kid_id=kid_id,
    multiplier=multiplier,
)

# EconomyManager listens and writes
def _on_multiplier_change_requested(self, payload):
    kid_info[const.DATA_KID_POINTS_MULTIPLIER] = payload["multiplier"]
    self._coordinator._persist()
```

**Work items:**

- [x] Add `SIGNAL_SUFFIX_MULTIPLIER_CHANGE_REQUESTED` to const.py
- [x] EconomyManager: Add listener in `async_setup()` + handler `_on_multiplier_change_requested()`
- [x] GamificationManager: Replace direct write with emit in `update_point_multiplier_for_kid()` (line ~1392)
- [x] GamificationManager: Update `_handle_badge_earned()` uses BADGE_EARNED signal already (no change needed)
- [x] Verify all other multiplier writes use the signal pattern

##### 3B.2: Genesis - EconomyManager Structures ✅ COMPLETE

**File**: `data_builders.py` - Extend `build_kid()`

Add to `build_kid()` return dict:

```python
# Point statistics (EconomyManager owns, StatisticsManager writes buckets)
const.DATA_KID_POINT_STATS: (
    existing.get(const.DATA_KID_POINT_STATS, {
        const.DATA_KID_POINT_STATS_EARNED_ALL_TIME: 0.0,
        const.DATA_KID_POINT_STATS_SPENT_ALL_TIME: 0.0,
        const.DATA_KID_POINT_STATS_NET_ALL_TIME: 0.0,
        const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME: {},
        const.DATA_KID_POINT_STATS_HIGHEST_BALANCE: 0.0,
    }) if existing else {
        const.DATA_KID_POINT_STATS_EARNED_ALL_TIME: 0.0,
        const.DATA_KID_POINT_STATS_SPENT_ALL_TIME: 0.0,
        const.DATA_KID_POINT_STATS_NET_ALL_TIME: 0.0,
        const.DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME: {},
        const.DATA_KID_POINT_STATS_HIGHEST_BALANCE: 0.0,
    }
),
# Point data periods (EconomyManager owns, StatisticsManager writes buckets)
const.DATA_KID_POINT_DATA: (
    existing.get(const.DATA_KID_POINT_DATA, {
        const.DATA_KID_POINT_DATA_PERIODS: {},
    }) if existing else {
        const.DATA_KID_POINT_DATA_PERIODS: {},
    }
),
```

**Work items:**

- [x] Add `DATA_KID_POINT_STATS` with default structure to `build_kid()`
- [x] Add `DATA_KID_POINT_DATA` with nested `periods` to `build_kid()`
- [x] Verify TypedDict `KidData` includes these fields (added `point_data`)

##### 3B.3: Genesis - ChoreManager Structures ✅ COMPLETE

**File**: `data_builders.py` - Extend `build_kid()`

Add to `build_kid()` return dict:

```python
# Chore data container (ChoreManager owns, creates per-chore entries on assignment)
const.DATA_KID_CHORE_DATA: (
    existing.get(const.DATA_KID_CHORE_DATA, {}) if existing else {}
),
# Chore statistics (ChoreManager owns, StatisticsManager writes buckets)
const.DATA_KID_CHORE_STATS: (
    existing.get(const.DATA_KID_CHORE_STATS, {
        const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME: 0,
        const.DATA_KID_CHORE_STATS_APPROVED_TODAY: 0,
    }) if existing else {
        const.DATA_KID_CHORE_STATS_APPROVED_ALL_TIME: 0,
        const.DATA_KID_CHORE_STATS_APPROVED_TODAY: 0,
    }
),
```

**Work items:**

- [x] Add `DATA_KID_CHORE_DATA` empty container to `build_kid()`
- [x] Add `DATA_KID_CHORE_STATS` with default structure to `build_kid()`
- [x] ChoreManager: Updated `_get_kid_chore_data()` with guard + warning pattern (Phase 3B tenant rule)
- [x] ChoreManager still creates per-chore entries on-demand - existing flow works correctly

##### 3B.4: StatisticsManager Tenant Rule ✅ COMPLETE

**File**: `managers/statistics_manager.py`

**Remove all `setdefault()` calls for containers StatisticsManager doesn't own.**

Pattern to apply:

```python
# BEFORE (creates container if missing - RESURRECTION BUG)
point_stats = kid_info.setdefault(const.DATA_KID_POINT_STATS, {})

# AFTER (tenant rule - skip if landlord hasn't created)
point_stats = kid_info.get(const.DATA_KID_POINT_STATS)
if point_stats is None:
    const.LOGGER.warning(
        "StatisticsManager: point_stats missing for kid '%s' - skipping (Landlord hasn't initialized)",
        kid_id,
    )
    return
```

**Locations fixed:**

- [x] Line ~351: `kid_info.setdefault(DATA_KID_POINT_STATS, {})` → Guard + warning
- [x] Lines ~354-358: `point_stats.setdefault(...)` → Changed to `if key not in point_stats` pattern
- [x] Line ~376-378: `kid_info.setdefault(DATA_KID_POINT_DATA, {}).setdefault(...)` → Guard + warning
- [x] Line ~503: `kid_info.setdefault(DATA_KID_CHORE_DATA, {})` → Guard + warning
- [x] Line ~504-505: `chore_data.setdefault(chore_id, {})` → Guard for per-chore entry (ChoreManager creates on assignment)

##### 3B.5: Validation & Testing ✅ COMPLETE

- [x] Run `./utils/quick_lint.sh --fix` - all checks pass (ruff ✅, mypy ✅, boundaries ✅)
- [x] Run `mypy custom_components/kidschores/` - zero errors
- [x] Run existing tests - **1185 passed**, 2 skipped, 2 deselected
- [ ] Manual test: Create kid → verify point_stats/point_data/chore_stats exist (DEFERRED)
- [ ] Manual test: Delete chore_data → verify StatisticsManager doesn't recreate on stray event (DEFERRED)

---

- **Key issues** (RESOLVED):
  - ~~GamificationManager currently writes multiplier directly~~ → Fixed via signal
  - Existing kids in storage: Genesis pattern in `build_kid()` handles existing case via `.get()` fallback
  - ~~TypedDict definitions~~ → Updated `KidData` to include `point_data`

- **Migration consideration**: Existing kids without `point_stats`/`point_data`/`chore_stats`:
  - Option A: Migration script adds missing structures on load (SCHEMA_VERSION bump)
  - Option B: Genesis logic in `build_kid()` already handles `existing` case
  - **Recommendation**: Option B should suffice (no migration needed if `build_kid()` handles existing correctly)

### Phase 4 – SystemManager Orchestration ✅ COMPLETE

- **Goal**: Implement the orchestration method that service handler calls
- **Steps / detailed work items**

  #### 4A: Add orchestrate_data_reset() Method ✅
  - File: `managers/system_manager.py`
  - Method: `async def orchestrate_data_reset(self, service_data: dict[str, Any]) -> None`
  - [x] Implemented ~200 line orchestration method

  #### 4B: Safety Validation ✅
  - [x] Check `confirm_destructive` is True (exact boolean, not truthy)
  - [x] Raise `ServiceValidationError` if missing/false

  #### 4C: Scope Parsing ✅
  - [x] Default scope to "global" if omitted or empty
  - [x] Extract kid_name, item_type, item_name
  - [x] Validate parameter combinations

  #### 4D: Name→ID Resolution ✅
  - [x] Convert kid_name → kid_id using `get_item_id_or_raise()`
  - [x] Convert item_name + item_type → item_id
  - [x] Raise translated error if not found

  #### 4E: Backup Creation ✅
  - [x] Call `bh.create_timestamped_backup()` with `BACKUP_TAG_DATA_RESET`
  - [x] Log backup name

  #### 4F: Call Managers (Based on Scope) ✅
  - [x] **Global**: Call ALL manager data_reset methods via `_call_data_reset_managers()`
  - [x] **Kid**: Call all managers with kid_id filter
  - [x] **Item Type Filter**: Call only relevant item type manager via `_call_single_domain_reset()`
  - [x] Manager routing: points→economy, chores→chore, rewards→reward, badges/achievements/challenges→gamification, penalties/bonuses→economy
  - [x] **Downstream→Upstream Order**: Gamification → Rewards → Chores → Economy (prevents orphaned data)
  - [x] **Multiplier Trap Fix**: `data_reset_badges()` now calls `update_point_multiplier_for_kid()` after clearing
  - [x] **Belt+Suspenders**: Added `DATA_KID_POINTS_MULTIPLIER` to `_ECONOMY_KID_RUNTIME_FIELDS`
  - [x] **EconomyManager Fix**: `data_reset_points()` resets multiplier to `DEFAULT_KID_POINTS_MULTIPLIER` (1.0, not 0)

  #### 4G: Send Notification ✅
  - [x] Added `broadcast_to_all_parents()` to NotificationManager for system-level notifications
  - [x] Uses appropriate translation key based on scope
  - [x] Supports parent language preferences
  - [x] Concurrent notification sending

- **Validation**: ✅ Lint passed, MyPy zero errors, 1185 tests passed

### Phase 5 – Service Registration ✅ COMPLETE

- **Goal**: Register the unified service with Home Assistant
- **Steps / detailed work items**

  #### 5A: Add Service Schema ✅
  - File: `services.py`
  - [x] Define `RESET_TRANSACTIONAL_DATA_SCHEMA` with confirm_destructive, scope, kid_name, item_type, item_name

  #### 5B: Add Service Handler ✅
  - [x] Function: `async def handle_reset_transactional_data(call: ServiceCall)`
  - [x] Delegates to `coordinator.system_manager.orchestrate_data_reset(call.data)`

  #### 5C: Register Service ✅
  - [x] In `async_setup_services()`, add registration
  - [x] Added to `async_unload_services()` unload list

  #### 5D: Update services.yaml ✅
  - [x] Add comprehensive service definition with all fields and selectors

  #### 5E: Update en.json Translations ✅
  - [x] Add `reset_transactional_data` service translations with all field descriptions

- **Validation**: ✅ Lint passed, MyPy zero errors, 1185 tests passed

### Phase 6 – Testing

- **Goal**: Comprehensive test coverage for all scopes and domains
- **Steps / detailed work items**

  #### 6A: Create Test File ✅ COMPLETE
  - File: `tests/test_data_reset_service.py`
  - Use `scenario_full` fixture for comprehensive data
  - Created 470-line test file with 7 test classes, 14 test methods

  #### 6B: Test Safety Mechanism ✅ COMPLETE (3 tests)
  - [x] `test_fails_without_confirm_destructive` - schema validation catches missing required field
  - [x] `test_fails_with_false_confirm_destructive` - ServiceValidationError when false
  - [x] `test_succeeds_with_true_confirm_destructive` - service executes successfully

  #### 6C: Test Global Scope ✅ COMPLETE (3 tests)
  - [x] `test_global_resets_all_kids_points` - all kids' points → 0
  - [x] `test_global_resets_all_kids_multipliers` - all multipliers → 1.0
  - [x] `test_global_clears_all_kids_ledgers` - all ledgers → []

  #### 6D: Test Per-Kid Scope ✅ COMPLETE (2 tests)
  - [x] `test_kid_scope_resets_only_target_kid` - other kids unaffected
  - [x] `test_kid_scope_requires_kid_name` - error when kid_name missing

  #### 6E: Test Item Type Filter ✅ COMPLETE (1 test)
  - [x] `test_item_type_points_only` - only points reset, chore_data untouched

  #### 6F: Test Validation Errors ✅ COMPLETE (3 tests)
  - [x] `test_invalid_scope_rejected` - schema validation rejects invalid scope
  - [x] `test_invalid_item_type_rejected` - schema validation rejects invalid item_type
  - [x] `test_unknown_kid_name_raises_error` - ServiceValidationError for nonexistent kid

  #### 6G: Test Backup Creation ✅ COMPLETE (1 test)
  - [x] `test_backup_created_before_reset` - create_timestamped_backup() called with BACKUP_TAG_DATA_RESET

  #### 6H: Test Notification ✅ COMPLETE (1 test)
  - [x] `test_notification_sent_after_global_reset` - broadcast_to_all_parents() called

  #### 6I: Additional Tests (TODO - Optional expansion)
  - [ ] `test_data_reset_global_clears_badge_earned_by` - all earned_by → []
  - [ ] `test_data_reset_global_preserves_config` - names, definitions, settings intact
  - [ ] `test_data_reset_item_chore` - single chore reset (if implemented)
  - [ ] `test_data_reset_emits_completion_signals` - verify signals emitted

- **Key issues**: ✅ All essential test scenarios covered (14/14 tests passing)

### Phase 7 – Cleanup

- **Goal**: Remove legacy code and old plan document
- **Steps / detailed work items**

  #### 7A: Remove Stale Functions from data_builders.py ✅ COMPLETE
  - [x] No stale functions exist (already clean)
  - Delete any `data_reset_*_to_defaults()` pure functions
  - Delete `_recalculate_chore_stats_from_chore_data()` if present
  - Keep ONLY the frozenset field definitions

  #### 7B: Delete data_reset_helpers.py ✅ COMPLETE
  - [x] File does not exist (already clean)
  - File: `helpers/data_reset_helpers.py`
  - Remove entire file

  #### 7C: Remove Legacy Services ✅ COMPLETE
  - [x] Deleted `reset_rewards` service (absorbed by reset_transactional_data)
  - [x] Deleted `reset_penalties` service (absorbed by reset_transactional_data)
  - [x] Deleted `reset_bonuses` service (absorbed by reset_transactional_data)
  - [x] Removed constants, handlers, schemas, services.yaml entries, translations
  - **Kept** `reset_overdue_chores` (specialized workflow - reschedules due dates)
  - **Kept** `remove_awarded_badges` (different purpose - selective removal)

  #### 7D: Rename Services ✅ COMPLETE
  - [x] Renamed `reset_all_data` → `factory_reset`
    - Updated constant: `SERVICE_RESET_ALL_DATA` → `SERVICE_FACTORY_RESET`
    - Updated handler name: `handle_reset_all_data()` → `handle_factory_reset()`
    - Updated services.yaml entry
    - Updated translations
  - [x] Renamed `reset_all_chores` → `reset_chores_to_pending_state`
    - Updated constant: `SERVICE_RESET_ALL_CHORES` → `SERVICE_RESET_CHORES_TO_PENDING_STATE`
    - Updated handler, services.yaml, translations
    - This is a STATE reset (pending state), not a DATA reset
  - [x] Updated test helpers (constants.py, **init**.py, test_chore_services.py)

  #### 7E: Migration Cleanup for \_LEGACY Fields ✅ COMPLETE
  - [x] Added `DATA_KID_OVERDUE_CHORES_LEGACY` constant to const.py (line ~3925)
  - [x] Added field to `_remove_legacy_fields()` in migration_pre_v50.py to strip from storage
  - [x] Removed line creating dead code field in `_create_kid()` migration method
  - [x] Updated `_DEPRECATED_KID_FIELDS_FOR_MIGRATION_CLEANUP` comment in data_builders.py (now handled by migration)
  - **Pattern followed**: Used existing PreV50Migrator `_remove_legacy_fields()` method

  #### 7F: Archive Old Plan
  - Delete `DATA_RESET_SERVICE_IN-PROCESS.md` (superseded by V2)
  - Or move to `docs/completed/` with SUPERSEDED suffix if preferred

  #### 7G: Eliminate Stats Redundancy + Centralize Period Updates (Architecture Cleanup)

  **Overview**: Two-part architectural fix:
  1. Eliminate flat `*_stats` structures (consolidate into period buckets)
  2. Centralize ALL period updates through single ownership model

  **Problem**:
  - Flat stats duplicate period data (synchronization bugs, storage bloat)
  - Inconsistent ownership: StatisticsManager updates point/chore periods, but RewardManager/GamificationManager bypass and call StatisticsEngine directly
  - After stats elimination, "StatisticsManager" name misleading (only manages SOME period data)

  **Solution**:
  - Phase 7G.1-3: Eliminate point_stats, chore_stats, reward_stats (consolidate into period buckets)
  - Phase 7G.4: Centralize ALL period updates in StatisticsManager (add reward/badge listeners)
  - Phase 7G.5: Rename StatisticsManager → CacheManager (accurate post-consolidation name)

  ***

  ##### 7G.1: point_stats Consolidation

  **Goal**: Move all-time point data from flat `point_stats` into `point_data.periods.all_time` structure

  **Problem**:
  - `point_stats` has: `points_earned_all_time`, `points_spent_all_time`, `points_net_all_time`, `by_source_all_time`, `highest_balance_all_time`
  - `point_data.periods.all_time` has partial data: `points_total`, `by_source`
  - Creates synchronization issues and storage bloat

  **Why point_stats is Data (MUST persist)**:
  - `points_earned_all_time` incremented on every transaction (cannot recompute after pruning old periods)
  - `points_spent_all_time` incremented on every withdrawal (cannot recompute after pruning)
  - `by_source_all_time` incremented per source (cannot recompute after pruning)
  - `highest_balance_all_time` tracks historical peak (cannot recompute from pruned data)
  - `points_net_all_time` is DERIVED (earned + spent) - can delete

  **Final Structure for Point Data:**

  Standard period buckets (daily/weekly/monthly/yearly):

  ```json
  "daily": {
    "2026-02-02": {
      "points_earned": 2213.0,    // Sum of positive deltas (chores, bonuses, badges, +manual)
      "points_spent": -225.0,     // Sum of negative deltas (rewards, penalties, -manual)
      // points_net: DERIVED (earned + spent) - not stored
      "by_source": {              // Detailed source breakdown
        "manual": 1864.0,
        "bonuses": 225.0,
        "penalties": -101.0
      }
    }
  }
  ```

  all_time bucket (has cumulative high-water marks):

  ```json
  "all_time": {
    "all_time": {
      "points_earned": 6173.0,        // ← FROM point_stats.points_earned_all_time
      "points_spent": -696.0,         // ← FROM point_stats.points_spent_all_time
      // points_net: DERIVED (6173 + -696 = 5477) - not stored
      "by_source": {                  // ← FROM point_stats.points_by_source_all_time
        "other": 2980.0,
        "chores": 329.0,
        "manual": -20.0,
        "rewards": -40.0,
        "bonuses": 15.0,
        "penalties": -7.0,
        "badges": 100.0
      },
      "highest_balance": 2980.0       // ← FROM point_stats.highest_balance_all_time
                                       // ← ONLY in all_time (cumulative peak)
    }
  }
  ```

  **Key Changes:**
  - Split `points_total` → `points_earned` + `points_spent` (explicit sign tracking)
  - Move all `point_stats` fields into `point_data.periods.all_time.all_time`
  - DELETE `point_stats` top-level key (or keep empty dict for backward compat)
  - DERIVE `points_net` on-demand (never store): `points_net = points_earned + points_spent`
  - `highest_balance` ONLY in all_time bucket (period-specific peaks not useful)

  **Migration Steps:**
  1. Update `StatisticsEngine.record_transaction()` to write `points_earned` and `points_spent` separately
  2. Add migration to backfill earned/spent from existing `points_total` and `by_source` data
  3. Move `point_stats` fields into `all_time` bucket
  4. Update all code reading from `point_stats` to read from `point_data.periods.all_time.all_time`
  5. Update PRES*KID*\* cache refresh to derive from new structure
  6. Delete `point_stats` (or leave empty for backward compatibility)

  ***

  ##### 7G.2: chore_stats Cleanup

  **Goal**: Remove derived fields from `chore_stats`, keep only incrementally maintained all-time counters

  **Current Structure:**

  ```json
  "chore_stats": {
    // Incrementally maintained (KEEP - these are DATA)
    "approved_all_time": 28,              // += 1 on each approval
    "completed_all_time": 0,              // += 1 on each completion
    "claimed_all_time": 16,               // += 1 on each claim
    "disapproved_all_time": 9,            // += 1 on each disapproval
    "overdue_count_all_time": 314,        // += 1 on each overdue event
    "longest_streak_all_time": 11,        // max(current, longest) on streak change
    "total_points_from_chores_all_time": 589.0,  // += points on each approval

    // Derived snapshots (DELETE - already in PRES_ cache)
    "current_overdue": 3,                 // count(chore.state == "overdue")
    "current_claimed": 0,                 // count(chore.state == "claimed")
    "current_approved": 3,                // count(chore.state == "approved")

    // Cannot properly track (DELETE)
    "most_completed_chore_all_time": null // no per-chore all-time completion counter exists
  }
  ```

  **Why chore_stats all-time fields are Data (MUST persist)**:
  - Each counter incremented on specific events (cannot recompute after pruning chore period data)
  - `longest_streak_all_time` is historical peak (cannot recompute from current state)
  - `total_points_from_chores_all_time` tracks cumulative points (cannot recompute after pruning)

  **Why current\_\* fields are Derived (DELETE)**:
  - Already computed and cached in PRES_KID_CHORES_CURRENT_OVERDUE, etc.
  - Can ALWAYS recompute by iterating chores and counting by state
  - No pruning risk (chores exist until manually deleted)

  **Final Structure:**

  ```json
  "chore_stats": {
    "approved_all_time": 28,
    "completed_all_time": 0,
    "claimed_all_time": 16,
    "disapproved_all_time": 9,
    "overdue_count_all_time": 314,
    "longest_streak_all_time": 11,
    "total_points_from_chores_all_time": 589.0
  }
  ```

  **Migration Steps:**
  1. Remove `current_overdue`, `current_claimed`, `current_approved` from chore*stats (already in PRES* cache)
  2. Remove `most_completed_chore_all_time` (cannot properly track)
  3. Update code to read current*\* from PRES* cache only (never from storage)
  4. Keep all `*_all_time` counters (incrementally maintained data)

  ***

  ##### 7G.3: reward_stats Cleanup

  **Goal**: Eliminate all temporal snapshots, keep only incrementally maintained all-time counters

  **Current Structure:**

  ```json
  "reward_stats": {
    // Temporal snapshots (DELETE - can derive from reward_data periods)
    "claimed_today": 0,
    "claimed_week": 0,
    "claimed_month": 0,
    "claimed_year": 1,
    "approved_today": 0,
    "approved_week": 0,
    "approved_month": 0,
    "approved_year": 1,
    "points_spent_today": 0.0,
    "points_spent_week": 0.0,
    "points_spent_month": 0.0,
    "points_spent_year": 20.0,

    // Incrementally maintained (KEEP - these are DATA)
    "claimed_all_time": 0,                // += 1 on each claim
    "approved_all_time": 0,               // += 1 on each approval
    "points_spent_all_time": 0.0,         // += points on each redemption

    // "Most redeemed" tracking (EVALUATE)
    "most_redeemed_all_time": "5 Dollars",  // highest redemption count by reward name
    "most_redeemed_week": null,
    "most_redeemed_month": null
  }
  ```

  **Why reward_stats all-time fields are Data (MUST persist)**:
  - Each counter incremented on specific events (cannot recompute after pruning reward period data)
  - `points_spent_all_time` tracks cumulative spending (cannot recompute after pruning)

  **Why temporal fields are Derived (DELETE)**:
  - Can derive from `reward_data.periods.daily/weekly/monthly/yearly` buckets
  - Duplicates data already in period structure
  - Storage bloat with no benefit

  **Why "most redeemed" is Problematic (DELETE or KEEP?)**:
  - `most_redeemed_all_time`: Requires tracking redemption count per reward name (not currently stored per-reward)
  - `most_redeemed_week/month`: Temporal snapshots (derived, no value)
  - **Decision needed**: Keep most_redeemed_all_time if useful, or delete if not properly tracked

  **Final Structure:**

  ```json
  "reward_stats": {
    "claimed_all_time": 0,
    "approved_all_time": 0,
    "points_spent_all_time": 0.0
    // Remove all temporal snapshots (today/week/month/year)
    // Remove or fix most_redeemed tracking
  }
  ```

  **Migration Steps:**
  1. Remove all `*_today`, `*_week`, `*_month`, `*_year` fields
  2. Remove `most_redeemed_*` fields (or fix tracking if deemed valuable)
  3. Keep only `*_all_time` counters (incrementally maintained data)
  4. Update code to derive temporal stats from `reward_data.periods` buckets

  ***

  **Benefits of Stats Cleanup:**
  - Single source of truth for period-based data (point_data/chore_data/reward_data periods)
  - Clear separation: incrementally maintained data vs derived snapshots
  - Eliminates synchronization bugs
  - Reduced storage size
  - Consistent architecture across all stat types

  ***

  ##### 7G.4: Centralize Period Updates (Fix Ownership Inconsistency)

  **Goal**: Move ALL period updates through StatisticsManager (eliminate direct StatisticsEngine calls from domain managers)

  **Problem** (see [DATA_RESET_SERVICE_V2_SUP_PERIOD_OWNERSHIP_ANALYSIS.md](DATA_RESET_SERVICE_V2_SUP_PERIOD_OWNERSHIP_ANALYSIS.md)):
  - Points/Chores: StatisticsManager owns updates (centralized via signals or direct call)
  - Rewards/Badges: Domain managers call StatisticsEngine directly (decentralized - inconsistent)
  - Result: No clear rule on "who updates period data?"

  **Current Violations**:

  **RewardManager** (lines 258, 265 in reward_manager.py):

  ```python
  # WRONG: Direct StatisticsEngine call
  self.coordinator.stats.record_transaction(periods, {counter_key: amount}, ...)
  self.coordinator.stats.prune_history(periods, ...)
  ```

  **GamificationManager** (lines 1463, 1491, 1504 in gamification_manager.py):

  ```python
  # WRONG: Direct StatisticsEngine call
  self.coordinator.stats.record_transaction(periods, {const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1}, ...)
  self.coordinator.stats.prune_history(periods, ...)
  ```

  **Migration Steps**:
  1. **Add StatisticsManager Listeners**:
     - `SIGNAL_SUFFIX_REWARD_APPROVED` → `_on_reward_approved()`
       - Extract period update logic from RewardManager.\_update_reward_period()
       - Update reward_data[reward_id].periods
       - Prune old data
     - `SIGNAL_SUFFIX_BADGE_EARNED` → `_on_badge_earned()`
       - Extract period update logic from GamificationManager.\_update_kid_badges_earned()
       - Update badges_earned[badge_id].periods
       - Prune old data

  2. **Remove Direct Calls from RewardManager**:
     - Delete `_update_reward_period()` method
     - Remove `self.coordinator.stats.record_transaction()` calls (lines 258, 265)
     - Keep reward business logic (claim, approve, track counts)
     - Emit `SIGNAL_SUFFIX_REWARD_APPROVED` after approve (already exists)

  3. **Remove Direct Calls from GamificationManager**:
     - Remove `self.coordinator.stats.record_transaction()` calls (lines 1463, 1491)
     - Remove `self.coordinator.stats.prune_history()` call (line 1504)
     - Keep badge business logic (award, track)
     - Emit `SIGNAL_SUFFIX_BADGE_EARNED` after award (already exists)

  4. **Update Signal Payloads** (if needed):
     - Ensure REWARD_APPROVED includes: kid_id, reward_id, points
     - Ensure BADGE_EARNED includes: kid_id, badge_id

  **Result**:
  - Single gatekeeper: Only StatisticsManager updates period data
  - Consistent pattern: Domain managers emit signals, StatisticsManager updates
  - Clear separation: Business logic (managers) vs data recording (StatisticsManager)

  ***

  ##### 7G.5: Rename StatisticsManager → CacheManager

  **Goal**: Name reflects true purpose after stats elimination

  **Rationale**:
  - Before Phase 7G: Manages flat stats + period data → "StatisticsManager" accurate
  - After Phase 7G: Flat stats eliminated, only manages PRES\_\* cache → "StatisticsManager" misleading
  - Post-consolidation: Listens to domain events, updates period data, refreshes PRES\_\* cache → "CacheManager" accurate

  **Migration Steps**:
  1. Rename class: `StatisticsManager` → `CacheManager`
  2. Rename file: `statistics_manager.py` → `cache_manager.py`
  3. Update coordinator property: `coordinator.statistics_manager` → `coordinator.cache_manager`
  4. Update all imports across codebase
  5. Update docstring to reflect new purpose:

     ```python
     """Manager for event-driven cache and period data updates.

     Responsibilities:
     - Listen to domain events (POINTS_CHANGED, CHORE_APPROVED, REWARD_APPROVED, BADGE_EARNED)
     - Update period-based data (daily/weekly/monthly/yearly/all_time buckets)
     - Maintain ephemeral PRES_* cache (derived temporal stats)
     - Prune old history data
     """
     ```

  6. Update ARCHITECTURE.md documentation

  **Benefits**:
  - Accurate name: "Cache" = ephemeral PRES\_\* data + "Manager" = coordinates period updates
  - Clear distinction: CacheManager (period data + ephemeral cache) vs domain managers (business logic)
  - No confusion: "Statistics" implies aggregates, "Cache" implies derived/computed values

- **Key issues**: Must be done AFTER new service is working

---

## Testing & validation

- **Tests executed**: None yet
- **Outstanding tests**: Full test suite for Phase 6
- **Validation commands**:
  - `./utils/quick_lint.sh --fix` (code quality)
  - `mypy custom_components/kidschores/` (type checking)
  - `pytest tests/ -v` (all tests)
  - `pytest tests/test_data_reset_service.py -v` (specific tests)

---

## Notes & follow-up

### Service API Reference

```yaml
service: kidschores.reset_transactional_data
data:
  # REQUIRED - safety mechanism
  confirm_destructive: true

  # OPTIONAL - scope control (default: global)
  scope: "global" # global | kid | item_type | item

  # For kid scope or item+kid scope
  kid_name: "Alice"

  # For item_type scope (reset ALL of a type)
  item_type: "badges" # kids | chores | rewards | badges | achievements | challenges | penalties | bonuses

  # For item scope (reset ONE specific item)
  item_name: "Star Badge"
  item_type: "badge" # chore | reward | badge | achievement | challenge | penalty | bonus
```

### Scope Examples

```yaml
# 1. Global reset - ALL runtime data for ALL kids
service: kidschores.reset_transactional_data
data:
  confirm_destructive: true
  # scope defaults to "global" when omitted

# 2. Per-kid reset
service: kidschores.reset_transactional_data
data:
  confirm_destructive: true
  scope: "kid"
  kid_name: "Alice"

# 3. Per-item-type reset (all items of a type)
service: kidschores.reset_transactional_data
data:
  confirm_destructive: true
  scope: "item_type"
  item_type: "bonuses"

# 4. Per-item reset (all kids)
service: kidschores.reset_transactional_data
data:
  confirm_destructive: true
  scope: "item"
  item_name: "Wash Dishes"
  item_type: "chore"

# 5. Per-item reset (single kid)
service: kidschores.reset_transactional_data
data:
  confirm_destructive: true
  scope: "item"
  kid_name: "Alice"
  item_name: "Wash Dishes"
  item_type: "chore"
```

### What Gets Reset vs Preserved

| Item Type    | Preserved (Config)                           | Reset (Runtime)                        |
| ------------ | -------------------------------------------- | -------------------------------------- |
| Kids         | name, user_id, notify settings, language     | points, streaks, ledger, all tracking  |
| Chores       | name, points, schedule, assignment, settings | state, claimed_by, completed_by, dates |
| Badges       | name, type, thresholds, awards, schedule     | earned_by list                         |
| Achievements | name, criteria, target, reward points        | progress dict                          |
| Challenges   | name, criteria, dates, target, reward        | progress dict                          |
| Rewards      | name, cost, description, icon                | kid-side reward_data                   |
| Penalties    | name, points_deducted, description           | kid-side penalty_applies               |
| Bonuses      | name, points_awarded, description            | kid-side bonus_applies                 |

### Breaking Changes Summary

| Old Service             | Fate        | New Equivalent                                         |
| ----------------------- | ----------- | ------------------------------------------------------ |
| `reset_rewards`         | **REMOVED** | `reset_transactional_data` with `item_type: rewards`   |
| `reset_penalties`       | **REMOVED** | `reset_transactional_data` with `item_type: penalties` |
| `reset_bonuses`         | **REMOVED** | `reset_transactional_data` with `item_type: bonuses`   |
| `reset_all_data`        | **RENAMED** | `factory_reset` (same behavior)                        |
| `reset_all_chores`      | **RENAMED** | `reset_chores_to_pending_state` (same behavior)        |
| `reset_overdue_chores`  | **KEPT**    | No change                                              |
| `remove_awarded_badges` | **KEPT**    | No change                                              |

---

## Template usage notice

This plan follows the `PLAN_TEMPLATE.md` structure. Once complete, rename to `DATA_RESET_SERVICE_V2_COMPLETE.md` and move to `docs/completed/`.
