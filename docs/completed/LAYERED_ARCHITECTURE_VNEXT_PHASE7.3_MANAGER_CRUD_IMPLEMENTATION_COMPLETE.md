# Phase 7.3: Manager-Owned CRUD Implementation Plan

---

status: ✅ COMPLETED
owner: Builder Agent
created: 2025-01-27
completed: 2025-01-27
parent_plan: PHASE7_PLATINUM_ARCHITECTURE_IN-PROCESS.md
handoff_from: Strategist Agent

---

## Executive Summary

**Goal**: Consolidate all CRUD operations (`create`, `update`, `delete`) from `services.py` and `options_flow.py` into Manager classes, establishing Managers as the **single database entry point**.

**Current State**:

- `options_flow.py`: 25 direct `coordinator._data[...]` writes + 25 `_persist()` calls
- `services.py`: 6 direct `coordinator._data[...]` writes + 6 `_persist()` calls
- Delete operations: 9 methods in `coordinator.py` (delete_kid_entity, delete_chore_entity, etc.)

**Target State**:

- **Zero** direct `_data[]` writes in UI/service layers
- **Zero** direct `_persist()` calls in UI/service layers
- All CRUD routed through Manager methods
- Delete methods moved from Coordinator to appropriate Managers

---

## Scope Summary

| Domain          | Create                  | Update                  | Delete      | Manager             | Status           |
| --------------- | ----------------------- | ----------------------- | ----------- | ------------------- | ---------------- |
| **Chore**       | services + options_flow | services + options_flow | coordinator | ChoreManager        | ✅ services done |
| **Reward**      | services + options_flow | services + options_flow | coordinator | RewardManager       | ✅ services done |
| **Badge**       | options_flow            | options_flow            | coordinator | GamificationManager | ✅ Migrated      |
| **Bonus**       | options_flow            | options_flow            | coordinator | EconomyManager      | ✅ Migrated      |
| **Penalty**     | options_flow            | options_flow            | coordinator | EconomyManager      | ✅ Migrated      |
| **Kid**         | options_flow            | options_flow            | coordinator | UserManager         | ✅ Phase 7.3b    |
| **Parent**      | options_flow            | options_flow            | coordinator | UserManager         | ✅ Phase 7.3b    |
| **Achievement** | options_flow            | options_flow            | coordinator | GamificationManager | ✅ Phase 7.3c    |
| **Challenge**   | options_flow            | options_flow            | coordinator | GamificationManager | ✅ Phase 7.3c    |

---

## Phase 7.3a: Core Entity CRUD (Current)

**Status**: ✅ COMPLETE

### Completed ✅

- [x] ChoreManager CRUD methods created
- [x] RewardManager CRUD methods created + options_flow migrated
- [x] GamificationManager badge CRUD methods created + options_flow migrated
- [x] EconomyManager bonus/penalty CRUD methods created + options_flow migrated

### Remaining

- [ ] Chore CRUD migration in options_flow.py (see detailed breakdown below)
- [x] Chore/Reward CRUD migration in services.py ✅ (Phase 7.3d)
- [ ] Remove old coordinator delete methods

---

## Phase 7.3b: UserManager (Kid + Parent CRUD)

**Status**: ✅ COMPLETE

**Goal**: Create `UserManager` to handle Kid and Parent CRUD consistently with other domain managers.

### Completed ✅

- [x] Created `managers/user_manager.py` with full Kid/Parent CRUD
- [x] Added `_data` property for dynamic coordinator data access
- [x] Migrated options_flow.py add_kid, edit_kid, delete_kid
- [x] Migrated options_flow.py add_parent, edit_parent, delete_parent
- [x] Shadow kid creation/update/delete integrated

---

## Phase 7.3c: Achievement/Challenge CRUD

**Status**: ✅ COMPLETE

**Goal**: Add Achievement and Challenge CRUD methods to GamificationManager.

### Completed ✅

- [x] Added GamificationManager.create_achievement()
- [x] Added GamificationManager.update_achievement()
- [x] Added GamificationManager.delete_achievement()
- [x] Added GamificationManager.create_challenge()
- [x] Added GamificationManager.update_challenge()
- [x] Added GamificationManager.delete_challenge()
- [x] Migrated options_flow.py add_achievement (line 3027)
- [x] Migrated options_flow.py edit_achievement (line 3124)
- [x] Migrated options_flow.py add_challenge (line 3335)
- [x] Migrated options_flow.py edit_challenge (line 3484)
- [x] **ZERO `_persist()` calls remaining in options_flow.py**

---

## Phase 7.3d: services.py CRUD Migration ✅

**Status**: ✅ COMPLETE (2025-01-27)

**Goal**: Complete cleanup and migrate services.py CRUD operations.

### Completed

- [x] Migrate services.py create_chore → `chore_manager.create_chore()`
- [x] Migrate services.py update_chore → `chore_manager.update_chore()`
- [x] Migrate services.py create_reward → `reward_manager.create_reward()`
- [x] Migrate services.py update_reward → `reward_manager.update_reward()`
- [x] **ZERO `_persist()` calls remaining in services.py**

### Approach Used (Option C)

**Principle**: Each Manager method that modifies `_data` must call `_persist()` before returning.

**Key insight**: `set_due_date()` already persists, so the second `_persist()` in services.py was redundant.

**Pattern**:

```python
# services.py now:
chore_data = coordinator.chore_manager.create_chore(data_input)  # Persist 1
if due_date_input:
    await coordinator.chore_manager.set_due_date(...)  # Persist 2 (Manager-owned)
create_chore_entities(coordinator, internal_id)  # No persist needed
# NO _persist() in services.py
```

### Remaining TODO

- [x] Update coordinator delete methods to delegate to managers
- [x] Remove deprecated coordinator delete methods (9 methods removed from coordinator.py)
- [x] Updated tests to use manager delete methods

**Final cleanup completed 2025-01-27**:

- Migrated 4 remaining delete calls (options_flow.py + services.py)
- Removed 9 deprecated coordinator delete methods (~300 lines)
- Updated test_parent_shadow_kid.py to use manager methods

---

## Phase 7.3 COMPLETE ✅

**Summary**:

- **ZERO `_persist()` calls** in options_flow.py ✅
- **ZERO `_persist()` calls** in services.py ✅
- **ZERO coordinator delete\_\*\_entity methods** ✅
- All CRUD operations routed through Manager classes
- 1098 tests passing

### New File: `managers/user_manager.py`

**Required Methods**:

```python
class UserManager(BaseEventManager):
    """Manages Kid and Parent CRUD operations."""

    # KID CRUD
    def create_kid(self, user_input: dict[str, Any]) -> dict[str, Any]
    def update_kid(self, kid_id: str, updates: dict[str, Any]) -> dict[str, Any]
    def delete_kid(self, kid_id: str) -> None

    # PARENT CRUD
    def create_parent(self, user_input: dict[str, Any]) -> dict[str, Any]
    def update_parent(self, parent_id: str, updates: dict[str, Any]) -> dict[str, Any]
    def delete_parent(self, parent_id: str) -> None
```

**Signals to Emit**:

- `SIGNAL_SUFFIX_KID_CREATED`, `SIGNAL_SUFFIX_KID_UPDATED`, `SIGNAL_SUFFIX_KID_DELETED`
- `SIGNAL_SUFFIX_PARENT_CREATED`, `SIGNAL_SUFFIX_PARENT_UPDATED`, `SIGNAL_SUFFIX_PARENT_DELETED`

**options_flow.py Locations to Migrate**:
| Line | Operation | Context |
|------|-----------|---------|
| 385 | CREATE | Add kid |
| 438 | UPDATE | Edit kid |
| 595 | CREATE | Add parent (shadow kid creation) |
| 722 | UPDATE | Edit parent |

**Delete Locations** (coordinator.py):

- `delete_kid_entity()` → `UserManager.delete_kid()`
- `delete_parent_entity()` → `UserManager.delete_parent()`

---

## Detailed Chore CRUD Migration (options_flow.py)

### Current Direct Write Locations (17 remaining)

**Chore Creation Flow** (async_step_add_chore variants):

| Line | Stage  | Condition                      | Description                          |
| ---- | ------ | ------------------------------ | ------------------------------------ |
| 948  | CREATE | Single-kid INDEPENDENT         | Final save after per-kid details     |
| 976  | CREATE | Multi-kid INDEPENDENT          | Initial save before per-kid helper   |
| 997  | CREATE | DAILY_MULTI any                | Initial save before times collection |
| 1012 | CREATE | Standard (SHARED/SHARED_FIRST) | Direct final save                    |

**Chore Edit Flow** (async_step_edit_chore variants):

| Line | Stage  | Condition                             | Description                      |
| ---- | ------ | ------------------------------------- | -------------------------------- |
| 1101 | UPDATE | Base edit                             | Merge and save after base edit   |
| 1224 | UPDATE | Single-kid INDEPENDENT edit           | Final save after per-kid details |
| 1595 | UPDATE | Per-kid details helper (add)          | Update after per-kid info        |
| 1875 | UPDATE | Per-kid details (edit-add multi-step) | Mid-flow update                  |
| 2068 | UPDATE | Per-kid details (edit-add completion) | Final update                     |

**Chore Delete Flow**:
| Line | Location | Current |
|------|----------|---------|
| N/A | async_step_delete_chore | Uses `coordinator.delete_chore_entity()` |

**Additional Direct Writes** (higher line numbers):
| Line | Context | Description |
|------|---------|-------------|
| 3125 | Chore times collection | DAILY_MULTI times save |
| 3222 | Chore times collection | DAILY_MULTI final save |
| 3433 | Per-kid helper completion | Independent chore finalize |
| 3582 | Per-kid helper completion | Independent chore finalize |

### Migration Strategy for Chore CRUD

**Challenge**: Chore creation is a multi-step wizard with intermediate saves:

1. Base chore data → partial save → per-kid details → final save
2. DAILY_MULTI → partial save → times collection → final save

**Approach 1: Keep Intermediate Saves in Flow** ❌

- Manager called multiple times with partial data
- Manager would need to handle incomplete chores
- Violates "Manager receives validated complete data" principle

**Approach 2: Accumulate in Context, Single Manager Call** ✅

- Options flow accumulates all data across steps in `self.context`
- Only call `ChoreManager.create_chore()` at FINAL step
- Manager receives complete, validated chore data

**Implementation Plan**:

1. **Identify terminal steps** for each chore creation path
2. **Replace only terminal saves** with `ChoreManager.create_chore()`
3. **Keep intermediate saves** BUT mark them as "staging" (not calling Manager)
4. **Alternative**: Refactor to accumulate all in context, then single final call

### Step-by-Step Chore Migration

**Step 1**: Migrate `async_step_delete_chore` (simplest)

- Replace `coordinator.delete_chore_entity(internal_id)` with `coordinator.chore_manager.delete_chore(str(internal_id))`

**Step 2**: Migrate standard CREATE (line 1012)

- This is the simplest CREATE path (SHARED/SHARED_FIRST chores)
- Replace direct write with `coordinator.chore_manager.create_chore(user_input)`

**Step 3**: Migrate single-kid INDEPENDENT CREATE (line 948)

- Final step of single-kid flow
- Needs merged data from base + per-kid details

**Step 4**: Migrate multi-kid INDEPENDENT CREATE (lines 976, 997)

- Initial saves that lead to per-kid helper
- May need to keep as staging OR refactor flow

**Step 5**: Migrate edit flows (lines 1101, 1224, etc.)

- Replace with `coordinator.chore_manager.update_chore(chore_id, updates)`

**Step 6**: Migrate per-kid helper updates (lines 1595, 1875, 2068)

- These update existing chores with per-kid details
- Use `update_chore()` with merged data

**Step 7**: Migrate DAILY_MULTI times collection (lines 3125, 3222)

- Final saves after times collected

**Step 8**: Migrate per-kid helper completion (lines 3433, 3582)

- INDEPENDENT chore finalization

---

## Entity Type Inventory

### CHORES (ChoreManager)

**Current Write Locations in options_flow.py**:
| Line | Operation | Context |
|------|-----------|---------|
| 947 | CREATE | Single-kid INDEPENDENT chore final save |
| 975 | CREATE | Multi-kid INDEPENDENT chore initial save |
| 996 | CREATE | Multi-kid INDEPENDENT chore initial save |
| 1011 | CREATE | Standard chore creation |
| 1098 | UPDATE | Edit chore merge save |
| 1222 | UPDATE | Edit chore final save |
| 1873 | UPDATE | Edit chore per-kid details |
| 2066 | UPDATE | Edit chore per-kid details |

**Current Write Locations in services.py**:
| Line | Operation | Function |
|------|-----------|----------|
| 652 | CREATE | handle_create_chore |
| 832 | UPDATE | handle_update_chore |

**Current Delete Location**: `coordinator.py` line 1062 (`delete_chore_entity`)

**Required Manager Methods**:

```python
# ChoreManager
async def create_chore(self, user_input: dict[str, Any]) -> dict[str, Any]:
    """Create a new chore. Returns full chore dict."""

async def update_chore(self, chore_id: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Update existing chore. Returns updated chore dict."""

async def delete_chore(self, chore_id: str) -> None:
    """Delete chore and cleanup references."""
```

---

### REWARDS (RewardManager)

**Current Write Locations in options_flow.py**:
| Line | Operation | Context |
|------|-----------|---------|
| 2619 | CREATE | Add reward |
| 2680 | UPDATE | Edit reward |

**Current Write Locations in services.py**:
| Line | Operation | Function |
|------|-----------|----------|
| 1419 | CREATE | handle_create_reward |
| 1539 | UPDATE | handle_update_reward |

**Current Delete Location**: `coordinator.py` line 1133 (`delete_reward_entity`)

**Required Manager Methods**:

```python
# RewardManager
async def create_reward(self, user_input: dict[str, Any]) -> dict[str, Any]:
    """Create a new reward. Returns full reward dict."""

async def update_reward(self, reward_id: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Update existing reward. Returns updated reward dict."""

async def delete_reward(self, reward_id: str) -> None:
    """Delete reward and cleanup references."""
```

---

### BADGES (GamificationManager)

**Current Write Locations in options_flow.py**:
| Line | Operation | Context |
|------|-----------|---------|
| 2337 | CREATE | Add badge |
| 2337 | UPDATE | Edit badge (same location) |

**Current Delete Location**: `coordinator.py` line 1094 (`delete_badge_entity`)

**Required Manager Methods**:

```python
# GamificationManager
async def create_badge(self, user_input: dict[str, Any], badge_type: str) -> dict[str, Any]:
    """Create a new badge. Returns full badge dict."""

async def update_badge(self, badge_id: str, user_input: dict[str, Any], badge_type: str) -> dict[str, Any]:
    """Update existing badge. Returns updated badge dict."""

async def delete_badge(self, badge_id: str) -> None:
    """Delete badge and cleanup from all kids."""
```

---

### BONUSES (EconomyManager)

**Current Write Locations in options_flow.py**:
| Line | Operation | Context |
|------|-----------|---------|
| 2789 | CREATE | Add bonus |
| 2861 | UPDATE | Edit bonus |

**Current Delete Location**: `coordinator.py` line 1186 (`delete_bonus_entity`)

**Required Manager Methods**:

```python
# EconomyManager
async def create_bonus(self, user_input: dict[str, Any]) -> dict[str, Any]:
    """Create a new bonus. Returns full bonus dict."""

async def update_bonus(self, bonus_id: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Update existing bonus. Returns updated bonus dict."""

async def delete_bonus(self, bonus_id: str) -> None:
    """Delete bonus and cleanup."""
```

---

### PENALTIES (EconomyManager)

**Current Write Locations in options_flow.py**:
| Line | Operation | Context |
|------|-----------|---------|
| 2966 | CREATE | Add penalty |
| 3057 | UPDATE | Edit penalty |

**Current Delete Location**: `coordinator.py` line 1160 (`delete_penalty_entity`)

**Required Manager Methods**:

```python
# EconomyManager
async def create_penalty(self, user_input: dict[str, Any]) -> dict[str, Any]:
    """Create a new penalty. Returns full penalty dict."""

async def update_penalty(self, penalty_id: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Update existing penalty. Returns updated penalty dict."""

async def delete_penalty(self, penalty_id: str) -> None:
    """Delete penalty and cleanup."""
```

---

## Key Implementation Patterns

### Pattern 1: Manager CRUD Method Structure

```python
async def create_chore(self, user_input: dict[str, Any]) -> dict[str, Any]:
    """Create a new chore.

    Single path to database for both UI (options_flow) and Services.

    Args:
        user_input: Validated data from flow/service (DATA_* keys expected)

    Returns:
        The complete chore dict with defaults and metadata applied
    """
    # 1. Build entity using data_builders
    chore_dict = db.build_chore(user_input)
    internal_id = chore_dict[const.DATA_CHORE_INTERNAL_ID]

    # 2. Add audit metadata (Opportunity A from Phase 7 plan)
    chore_dict["_meta"] = {
        "created_at": dt_now_iso(),
        "last_updated_at": dt_now_iso(),
    }

    # 3. Write to storage
    self.coordinator._data[const.DATA_CHORES][internal_id] = dict(chore_dict)

    # 4. Persist
    self.coordinator._persist()

    # 5. Emit event AFTER successful write (Trap C mitigation)
    self.emit(const.SIGNAL_SUFFIX_CHORE_CREATED, chore_id=internal_id)

    # 6. Spawn HA entities (Trap A mitigation)
    await self._spawn_chore_entities(internal_id, chore_dict)

    # 7. Return full dict (Opportunity C: Typed Response)
    return chore_dict
```

### Pattern 2: Update Method Preserving Created Metadata

```python
async def update_chore(self, chore_id: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Update existing chore."""
    existing = self.coordinator._data[const.DATA_CHORES].get(chore_id)
    if not existing:
        raise HomeAssistantError(...)

    # Build updated entity
    chore_dict = db.build_chore(user_input, existing=existing)

    # Preserve created_at, update last_updated_at
    old_meta = existing.get("_meta", {})
    chore_dict["_meta"] = {
        "created_at": old_meta.get("created_at") or dt_now_iso(),
        "last_updated_at": dt_now_iso(),
    }

    self.coordinator._data[const.DATA_CHORES][chore_id] = dict(chore_dict)
    self.coordinator._persist()
    self.emit(const.SIGNAL_SUFFIX_CHORE_UPDATED, chore_id=chore_id)

    return chore_dict
```

### Pattern 3: Delete Method with Cleanup

```python
async def delete_chore(self, chore_id: str) -> None:
    """Delete chore and cleanup all references."""
    chore_data = self.coordinator._data[const.DATA_CHORES].get(chore_id)
    if not chore_data:
        raise HomeAssistantError(...)

    chore_name = chore_data.get(const.DATA_CHORE_NAME, chore_id)

    # 1. Remove from storage
    del self.coordinator._data[const.DATA_CHORES][chore_id]

    # 2. Cleanup HA entities (delegated to helper)
    entity_helpers.remove_entities_by_item_id(
        self.hass, self.coordinator.config_entry.entry_id, chore_id
    )

    # 3. Cleanup references (from coordinator methods)
    self._cleanup_chore_references(chore_id)

    # 4. Persist
    self.coordinator._persist()

    # 5. Emit delete event (for NotificationManager cleanup)
    self.emit(const.SIGNAL_SUFFIX_CHORE_DELETED, chore_id=chore_id, chore_name=chore_name)

    const.LOGGER.info("Deleted chore '%s' (ID: %s)", chore_name, chore_id)
```

### Pattern 4: Entity Spawning in Manager

```python
async def _spawn_chore_entities(self, chore_id: str, chore_dict: dict[str, Any]) -> None:
    """Spawn HA sensor entities for a new chore."""
    # Import locally to avoid circular imports
    from .sensor import create_chore_entities
    create_chore_entities(self.coordinator, chore_id)
```

---

## Signal Constants Status

✅ **All required signal constants already exist in `const.py`** (lines 119-161):

| Domain  | Created     | Updated     | Deleted     |
| ------- | ----------- | ----------- | ----------- |
| CHORE   | ✅ Line 129 | ✅ Line 130 | ✅ Line 131 |
| REWARD  | ✅ Line 139 | ✅ Line 140 | ✅ Line 141 |
| BADGE   | ✅ Line 134 | ✅ Line 135 | ✅ Line 136 |
| BONUS   | ✅ Line 159 | ✅ Line 160 | ✅ Line 161 |
| PENALTY | ✅ Line 154 | ✅ Line 155 | ✅ Line 156 |

**No changes needed to const.py for CRUD signals.**

---

## Existing Delete Method Migration

The following coordinator methods need to be **MOVED** to their respective Managers:

| Current Method                        | Target Manager      | Logic to Migrate |
| ------------------------------------- | ------------------- | ---------------- |
| `coordinator.delete_chore_entity()`   | ChoreManager        | Line 1062-1092   |
| `coordinator.delete_reward_entity()`  | RewardManager       | Line 1133-1157   |
| `coordinator.delete_badge_entity()`   | GamificationManager | Line 1094-1130   |
| `coordinator.delete_bonus_entity()`   | EconomyManager      | Line 1186-1207   |
| `coordinator.delete_penalty_entity()` | EconomyManager      | Line 1160-1183   |

**Keep in Coordinator** (system entities):

- `delete_kid_entity()` - Line 960-1025
- `delete_parent_entity()` - Line 1027-1060
- `delete_achievement_entity()` - Line 1210-1233
- `delete_challenge_entity()` - Line 1236-1260

---

## NotificationManager Integration (Opportunity B)

Add event listeners to clear notifications when entities are deleted:

```python
# NotificationManager.async_setup()
self.listen(const.SIGNAL_SUFFIX_CHORE_DELETED, self._on_entity_deleted)
self.listen(const.SIGNAL_SUFFIX_REWARD_DELETED, self._on_entity_deleted)
self.listen(const.SIGNAL_SUFFIX_BADGE_DELETED, self._on_entity_deleted)

def _on_entity_deleted(self, payload: dict[str, Any]) -> None:
    """Clear notifications for deleted entity."""
    entity_id = payload.get("chore_id") or payload.get("reward_id") or payload.get("badge_id")
    if entity_id:
        # Clear any pending notifications involving this entity
        self._clear_notifications_for_entity(entity_id)
```

---

## Implementation Order (Critical Path)

### Phase A: Manager CRUD Methods (Foundation) - MUST DO FIRST

1. **Step 7.3.1**: Add ChoreManager CRUD methods (`create_chore`, `update_chore`, `delete_chore`)
2. **Step 7.3.2**: Add RewardManager CRUD methods
3. **Step 7.3.3**: Add GamificationManager CRUD methods (for badges)
4. **Step 7.3.4**: Add EconomyManager CRUD methods (for bonus/penalty)
5. **Step 7.3.5**: Add NotificationManager delete listeners

### Phase B: Update services.py (6 locations)

6. **Step 7.3.6**: `handle_create_chore` → `chore_manager.create_chore()`
7. **Step 7.3.7**: `handle_update_chore` → `chore_manager.update_chore()`
8. **Step 7.3.8**: `handle_delete_chore` → `chore_manager.delete_chore()`
9. **Step 7.3.9**: `handle_create_reward` → `reward_manager.create_reward()`
10. **Step 7.3.10**: `handle_update_reward` → `reward_manager.update_reward()`
11. **Step 7.3.11**: `handle_delete_reward` → `reward_manager.delete_reward()`

### Phase C: Update options_flow.py (21+ locations) - THE BIG WIN

12. **Step 7.3.12**: Chore creates (4 locations: lines 947, 975, 996, 1011)
13. **Step 7.3.13**: Chore updates (4 locations: lines 1098, 1222, 1873, 2066)
14. **Step 7.3.14**: Badge create/update (line 2337)
15. **Step 7.3.15**: Reward create (line 2619)
16. **Step 7.3.16**: Reward update (line 2680)
17. **Step 7.3.17**: Bonus create (line 2789)
18. **Step 7.3.18**: Bonus update (line 2861)
19. **Step 7.3.19**: Penalty create (line 2966)
20. **Step 7.3.20**: Penalty update (line 3057)

### Phase D: Cleanup Coordinator Delete Methods

21. **Step 7.3.21**: Remove migrated delete methods from coordinator
22. **Step 7.3.22**: Update options_flow delete steps to use Manager methods

### Phase E: Validation

23. **Step 7.3.23**: Run `./utils/quick_lint.sh --fix`
24. **Step 7.3.24**: Run `mypy custom_components/kidschores/`
25. **Step 7.3.25**: Run `python -m pytest tests/ -v --tb=line`

---

## Files Modified

| File                               | Changes                                                                                                  |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `managers/chore_manager.py`        | Add `create_chore`, `update_chore`, `delete_chore`                                                       |
| `managers/reward_manager.py`       | Add `create_reward`, `update_reward`, `delete_reward`                                                    |
| `managers/gamification_manager.py` | Add `create_badge`, `update_badge`, `delete_badge`                                                       |
| `managers/economy_manager.py`      | Add `create_bonus`, `update_bonus`, `delete_bonus`, `create_penalty`, `update_penalty`, `delete_penalty` |
| `managers/notification_manager.py` | Add delete event listeners                                                                               |
| `services.py`                      | Replace 6 direct writes with manager calls                                                               |
| `options_flow.py`                  | Replace 25 direct writes with manager calls                                                              |
| `coordinator.py`                   | Remove 5 migrated delete methods                                                                         |

**Note**: `const.py` already has all required signal constants - no changes needed.

---

## Testing Strategy

### Unit Tests

- Test each new Manager CRUD method in isolation
- Mock `_persist()` and `emit()` to verify they're called
- Test error cases (not found, validation errors)

### Integration Tests

- Test full flow: UI input → Manager → Storage → Entity creation
- Test delete cascade: Manager delete → HA entity removal → notification cleanup
- Test services work identically before/after refactor

### Regression Tests

- Run existing test suite to verify no behavioral changes
- Snapshot tests for entity attributes should remain unchanged

---

## Risk Mitigation

### Risk 1: Breaking Changes in Options Flow

**Mitigation**: Commit after each options_flow location is updated and tests pass

### Risk 2: Entity Spawning Race Condition

**Mitigation**: Manager methods call `create_*_entities()` directly, not relying on reload

### Risk 3: Delete Cleanup Gaps

**Mitigation**: Copy exact cleanup logic from coordinator delete methods

### Risk 4: Signal Loop

**Mitigation**: Delete signals are terminal - no manager listens to trigger further writes

---

## Definition of Done

- [ ] All signal constants added to `const.py`
- [ ] All Manager CRUD methods implemented with type hints
- [ ] All services.py direct writes replaced
- [ ] All options_flow.py direct writes replaced
- [ ] Coordinator delete methods removed (migrated 5)
- [ ] NotificationManager listening to delete events
- [ ] `grep "coordinator._data\[" services.py options_flow.py` returns 0 matches
- [ ] `grep "coordinator._persist\(" services.py options_flow.py` returns 0 matches
- [ ] `./utils/quick_lint.sh` passes (9.5+/10)
- [ ] `mypy` passes with 0 errors
- [ ] `pytest tests/` passes (1098+ tests)
- [ ] No behavioral changes to existing functionality

---

## Handoff Notes for Builder

1. **Start with signal constants** - They're needed by all Manager methods
2. **Implement all Manager methods before touching UI/services** - Compile everything first
3. **Test after each domain** - Don't refactor all of options_flow at once
4. **Keep validation in flows/services** - Managers trust validated input
5. **Use `existing=` parameter** for update operations in `db.build_*()` functions
6. **Copy cleanup logic exactly** from coordinator delete methods
7. **Entity spawning via local import** - Avoid circular imports

**Expected Duration**: 4-6 hours of focused work

---

## Approval Checklist

- [x] Scope defined and bounded
- [x] All write locations identified with line numbers
- [x] Manager method signatures specified
- [x] Implementation patterns documented
- [x] Signal constants listed
- [x] Test strategy defined
- [x] Risks identified with mitigations
- [x] Definition of done explicit

**Ready for Builder handoff: ✅**
