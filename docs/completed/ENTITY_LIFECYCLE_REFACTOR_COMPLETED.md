# Entity Lifecycle Refactor Plan

## Initiative snapshot

- **Name / Code**: Entity Lifecycle Hygiene & Best Practices (Unified Registry)
- **Target release / milestone**: v0.5.0
- **Owner / driver(s)**: KidsChores Team
- **Status**: In Progress

## Summary & immediate steps

| Phase / Step                              | Description                                                | % complete | Quick notes                        |
| ----------------------------------------- | ---------------------------------------------------------- | ---------- | ---------------------------------- |
| Phase 1 – Entity Registry (Single Truth)  | Create `ENTITY_REGISTRY` dict with all entity definitions  | 100%       | ✅ Done - 44 entities registered   |
| Phase 2 – Unified Filter Function         | Create `should_create_entity()` using registry             | 100%       | ✅ Done - single filter function   |
| Phase 3A – Unified Cleanup in Coordinator | Create `cleanup_conditional_entities()` in coordinator     | 100%       | ✅ Done - consolidated cleanup     |
| Phase 3B – Unified Creation Logic         | Refactor entity creation to use `should_create_entity()`   | 100%       | ✅ Done - all platforms refactored |
| Phase 3C – Standardize UID Patterns       | Convert midfix/prefix patterns to suffix-only for registry | 100%       | ✅ Done - all UIDs standardized    |
| Phase 4 – Hook Cleanup to Triggers        | Wire cleanup to options flow, startup, migration           | 100%       | ✅ Done - all trigger points wired |
| Phase 5 – Testing & Validation            | Verify stable entity count across reloads                  | 100%       | ✅ Done - 8 tests, all 893 pass    |

1. **Key objective** – Single source of truth for entity definitions. ONE registry, ONE filter function, ONE cleanup function with hybrid triggers.

2. **Design philosophy** (Hybrid Approach):
   - **Proactive creation**: Filter at creation time based on registry (already working)
   - **Targeted cleanup**: Single function handles all conditional entity removal
   - **Hybrid triggers**:
     - **Runtime (event-driven)**: Options flow calls targeted cleanup when flags change
     - **One-time bulk**: Fresh HA restart + post-migration (not on reload)
   - **No speculation**: Don't scan for orphans on every reload

3. **What was working**: Extra entity cleanup (`_cleanup_extra_entities`) with suffix list
4. **What broke it**: Adding multiple scattered cleanup functions for shadow kids

5. **Solution**: Consolidate ALL entity rules into one registry that handles:
   - Extra entity filtering (flag-based, UI calls them "extra", config key is `show_legacy_entities`)
   - Shadow kid filtering (whitelist)
   - Regular kid filtering (default: create all)

6. **Terminology note**: "Extra entities" (UI term) = optional sensors controlled by `show_legacy_entities` config key.
   Config key kept for backward compatibility; code now uses `EXTRA` requirement and `extra_enabled` parameter.

7. **Decisions & completion check**
   - **Decisions captured**:
     - ONE registry dict in const.py defines all entity rules
     - ONE filter function in kc_helpers.py for all creation decisions
     - ONE cleanup function in coordinator.py for all removals
     - Hybrid triggers: targeted (options flow) + one-time bulk (startup/migration)
     - Reload does NOT run bulk cleanup (entities filter at creation)
   - **Completion confirmation**: `[x]` All follow-up items completed before marking done

---

## Current State Analysis

### Problem Statement

After multiple reloads, regular kids accumulate "unavailable" entities (8+ reported). Root cause: bulk "orphan cleanup" functions run on **every reload**, causing timing issues with entity creation.

### Current Entity Creation (Correct ✅)

| Platform | File           | Function              | Shadow Kid Filtering                                                         |
| -------- | -------------- | --------------------- | ---------------------------------------------------------------------------- |
| sensor   | sensor.py:107  | `async_setup_entry()` | `should_create_gamification_entities()`                                      |
| button   | button.py:96   | `async_setup_entry()` | `should_create_workflow_buttons()` + `should_create_gamification_entities()` |
| calendar | calendar.py:30 | `async_setup_entry()` | None (all kids)                                                              |
| datetime | datetime.py:28 | `async_setup_entry()` | None (all kids)                                                              |
| select   | select.py:35   | `async_setup_entry()` | None (all kids)                                                              |

### What Worked Well ✅

**Legacy entity cleanup** (`_cleanup_legacy_entities`) - Simple, reliable pattern:

- Single list of suffixes to remove
- Checks flag, removes if disabled
- Runs on reload - safe because entities are created AFTER cleanup

### What Broke ❌

**Multiple scattered cleanup functions** each scanning all entities:

- `_remove_orphaned_kid_chore_entities()` - Every reload
- `_remove_orphaned_badge_entities()` - Every reload
- `_remove_orphaned_manual_adjustment_buttons()` - Every reload
- `_remove_orphaned_shadow_kid_buttons()` - Every reload

**Problem**: These run on reload but entity creation happens DURING forward_entry_setups(), creating race conditions.

### What We Need

**Single source of truth** defining:

1. What entities exist for each platform
2. What conditions control their creation (always, workflow, gamification, legacy flag)
3. One function that answers: "Should this entity exist for this kid?"

Used for BOTH creation filtering AND targeted cleanup.

---

## Detailed Phase Tracking

### Phase 1 – Entity Registry (Single Source of Truth)

- **Goal**: Create `ENTITY_REGISTRY` in const.py that defines ALL entity rules

- **Steps / detailed work items**
  1. `[x]` Add `EntityRequirement` StrEnum for conditions (ALWAYS, WORKFLOW, GAMIFICATION, LEGACY)
  2. `[x]` Create `ENTITY_REGISTRY` dict mapping suffix → requirement
  3. `[x]` Consolidate existing `SHADOW_KID_*` tuples into registry (derived from registry)
  4. `[x]` Add `LEGACY_ENTITY_SUFFIXES` list referencing registry

- **Implemented Design** (const.py) - FLAG LAYERING DOCUMENTED

```python
from enum import StrEnum

class EntityRequirement(StrEnum):
    """Defines when an entity should be created.

    These are requirement CATEGORIES. The actual evaluation logic considers:
    - Kid type (regular vs shadow)
    - System flags (show_legacy_entities)
    - Parent flags (enable_gamification, enable_chore_workflow) for shadow kids

    LEGACY has compound logic: requires show_legacy_entities AND gamification.
    """
    ALWAYS = "always"           # All kids (regular + shadow base)
    WORKFLOW = "workflow"       # Requires enable_chore_workflow (shadow kids only)
    GAMIFICATION = "gamification"  # Requires enable_gamification (shadow kids only)
    LEGACY = "legacy"           # Requires show_legacy_entities AND gamification

# === FLAG LAYERING LOGIC ===
# | Requirement   | Regular Kid           | Shadow Kid                           |
# |---------------|-----------------------|--------------------------------------|
# | ALWAYS        | Created               | Created                              |
# | WORKFLOW      | Created               | Only if enable_chore_workflow=True   |
# | GAMIFICATION  | Created               | Only if enable_gamification=True     |
# | LEGACY        | If show_legacy flag   | If show_legacy AND gamification=True |

# Single source of truth for ALL entity creation rules
# Key: unique_id suffix, Value: EntityRequirement
ENTITY_REGISTRY: Final[dict[str, EntityRequirement]] = {
    # === SENSORS: Always (base functionality) ===
    SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR: EntityRequirement.ALWAYS,
    SENSOR_KC_UID_SUFFIX_CHORES_SENSOR: EntityRequirement.ALWAYS,
    SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER: EntityRequirement.ALWAYS,

    # === SENSORS: Gamification ===
    SENSOR_KC_UID_SUFFIX_KID_POINTS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_KID_BADGES_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR: EntityRequirement.GAMIFICATION,

    # === SENSORS: Legacy (requires show_legacy_entities AND gamification) ===
    SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR: EntityRequirement.LEGACY,
    SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR: EntityRequirement.LEGACY,
    # ... etc

    # === BUTTONS: Always ===
    BUTTON_KC_UID_SUFFIX_APPROVE: EntityRequirement.ALWAYS,

    # === BUTTONS: Workflow ===
    BUTTON_KC_UID_SUFFIX_CLAIM: EntityRequirement.WORKFLOW,
    BUTTON_KC_UID_SUFFIX_DISAPPROVE: EntityRequirement.WORKFLOW,

    # === BUTTONS: Gamification ===
    BUTTON_KC_UID_MIDFIX_ADJUST_POINTS: EntityRequirement.GAMIFICATION,
    # ... etc

    # === SELECT / DATETIME / CALENDAR: Similar patterns ===
}

# Derived for backward compatibility
LEGACY_ENTITY_SUFFIXES: Final[tuple[str, ...]] = tuple(
    suffix for suffix, req in ENTITY_REGISTRY.items()
    if req == EntityRequirement.LEGACY
)
```

- **44 entities registered** with proper flag layering documented

---

### Phase 2 – Unified Filter Function

- **Goal**: Create `should_create_entity()` that answers creation questions

- **Steps / detailed work items**
  1. `[x]` Add `should_create_entity()` to kc_helpers.py
  2. `[x]` Update `_cleanup_legacy_entities()` to use registry (`LEGACY_ENTITY_SUFFIXES`)
  3. `[x]` Remove scattered `SHADOW_KID_*` tuples (no longer needed)
  4. `[x]` Update `is_entity_allowed_for_shadow_kid()` to delegate to `should_create_entity()`

- **Proposed Implementation** (kc_helpers.py)

```python
def should_create_entity(
    unique_id_suffix: str,
    *,
    is_shadow_kid: bool = False,
    workflow_enabled: bool = True,
    gamification_enabled: bool = True,
    legacy_enabled: bool = False,
) -> bool:
    """Determine if an entity should be created based on its suffix and context.

    Single source of truth for entity creation decisions. Uses ENTITY_REGISTRY.

    === FLAG LAYERING LOGIC ===
    | Requirement   | Regular Kid           | Shadow Kid                           |
    |---------------|-----------------------|--------------------------------------|
    | ALWAYS        | Created               | Created                              |
    | WORKFLOW      | Created               | Only if workflow_enabled=True        |
    | GAMIFICATION  | Created               | Only if gamification_enabled=True    |
    | LEGACY        | If legacy_enabled     | If legacy_enabled AND gamification   |

    Args:
        unique_id_suffix: The entity's unique_id suffix (e.g., "_chore_status")
        is_shadow_kid: Whether this is a shadow kid
        workflow_enabled: Whether workflow is enabled (for shadow kids)
        gamification_enabled: Whether gamification is enabled (for shadow kids)
        legacy_enabled: Whether show_legacy_entities system flag is enabled

    Returns:
        True if entity should be created, False otherwise
    """
    # Find the matching registry entry
    requirement = None
    for suffix, req in const.ENTITY_REGISTRY.items():
        if unique_id_suffix.endswith(suffix):
            requirement = req
            break

    # Unknown suffix - default to gamification (safer for shadow kids)
    if requirement is None:
        return not is_shadow_kid or gamification_enabled

    # Check requirement against context
    match requirement:
        case const.EntityRequirement.ALWAYS:
            return True
        case const.EntityRequirement.WORKFLOW:
            return not is_shadow_kid or workflow_enabled
        case const.EntityRequirement.GAMIFICATION:
            return not is_shadow_kid or gamification_enabled
        case const.EntityRequirement.LEGACY:
            # LEGACY requires BOTH legacy flag AND gamification
            # Regular kids: always have gamification, so just check flag
            # Shadow kids: need flag AND gamification_enabled
            if not legacy_enabled:
                return False
            return not is_shadow_kid or gamification_enabled

    return False


def cleanup_entities_for_flag_change(
    hass: HomeAssistant,
    entry_id: str,
    kid_id: str,
    *,
    workflow_enabled: bool,
    gamification_enabled: bool,
) -> int:
    """Remove entities that are no longer allowed after flag change.

    Called when shadow kid's workflow or gamification flags change.
    Uses ENTITY_REGISTRY to determine what should be removed.
    """
    ent_reg = er.async_get(hass)
    prefix = f"{entry_id}_{kid_id}"
    removed_count = 0

    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry_id):
        unique_id = str(entity_entry.unique_id)
        if prefix not in unique_id:
            continue

        if not should_create_entity(
            unique_id,
            is_shadow_kid=True,
            workflow_enabled=workflow_enabled,
            gamification_enabled=gamification_enabled,
        ):
            ent_reg.async_remove(entity_entry.entity_id)
            removed_count += 1

    return removed_count
```

---

### Phase 3A – Unified Cleanup in Coordinator

- **Goal**: Create single `cleanup_conditional_entities()` function using ENTITY_REGISTRY

- **Design**: All destructive entity operations handled in coordinator. Single function with
  flexible parameters for targeted (per-kid) or bulk (all kids) operation.

- **Steps / detailed work items**
  1. `[x]` Add `cleanup_conditional_entities()` to coordinator.py
  2. `[x]` Add runtime key constant `RUNTIME_KEY_ENTITY_CLEANUP_DONE` to const.py
  3. `[x]` Remove `_cleanup_extra_entities()` from `__init__.py` (consolidated)
  4. `[x]` Replace `_remove_orphaned_shadow_kid_buttons()` with new function (consolidated)
  5. `[x]` Keep existing data-driven cleanup functions (delete_kid, delete_chore, etc.)

- **Proposed Implementation** (coordinator.py)

```python
async def cleanup_conditional_entities(
    self,
    *,
    kid_ids: list[str] | None = None,  # Target specific kids, None = all kids
    check_extra: bool = True,           # Check EXTRA entities
    check_workflow: bool = True,        # Check WORKFLOW entities
    check_gamification: bool = True,    # Check GAMIFICATION entities
) -> int:
    """Unified cleanup using ENTITY_REGISTRY.

    Removes entities that are no longer allowed based on current flag settings.
    Uses should_create_entity() from kc_helpers as single source of truth.

    Args:
        kid_ids: List of kid IDs to check, or None for all kids
        check_extra: Whether to evaluate EXTRA entities (show_legacy_entities flag)
        check_workflow: Whether to evaluate WORKFLOW entities (shadow kid workflow)
        check_gamification: Whether to evaluate GAMIFICATION entities (shadow kid gamification)

    Returns:
        Count of removed entities

    Call patterns:
        - Options flow (extra flag): check_extra=True, others=False
        - Options flow (parent flags): kid_ids=[shadow_kid], targeted flags
        - Unlink service: kid_ids=[shadow_kid], all checks
        - Fresh startup: None (all kids), all checks
        - Post-migration: None (all kids), all checks
    """
```

---

### Phase 3B – Unified Creation Logic

- **Goal**: Refactor entity creation to use `should_create_entity()` for consistency

- **Design**: Both creation and cleanup use the same registry-based function. Ensures they
  can never get out of sync. Entity's suffix clearly indicates its requirement.

- **Steps / detailed work items**
  1. `[x]` Refactor sensor.py to use `should_create_entity()` for per-kid entity decisions
  2. `[x]` Refactor button.py to use `should_create_entity()` for chore buttons (claim/approve/disapprove)
  3. `[x]` Refactor select.py to use `should_create_entity()` for extra entities
  4. `[x]` Refactor datetime.py to use `should_create_entity()` for future flexibility
  5. `[x]` Refactor calendar.py to use `should_create_entity()` for future flexibility
  6. `[x]` Remove scattered `if show_legacy_entities and create_gamification:` patterns (sensor.py)
  7. `[x]` Update tests to verify creation uses registry (validated by 884/885 passing tests)

- **Note**: Reward/bonus/penalty buttons use PREFIX patterns not in registry - deferred to Phase 3C

- **Before/After Example**

```python
# BEFORE (scattered flags):
if show_legacy_entities and create_gamification:
    entities.append(KidPointsEarnedDailySensor(...))

# AFTER (unified check):
suffix = const.SENSOR_KC_UID_SUFFIX_POINTS_EARNED_DAILY
if kh.should_create_entity(suffix, is_shadow_kid=is_shadow,
                           gamification_enabled=gamification,
                           extra_enabled=show_legacy_entities):
    entities.append(KidPointsEarnedDailySensor(...))
```

- **Benefits**:
  - Single source of truth for both creation and cleanup
  - Can't create entity that cleanup doesn't know about
  - Self-documenting via suffix constants
  - Easier testing

---

### Phase 3C – Standardize UID Patterns (Migration)

- **Goal**: Convert all entity unique_id patterns to use SUFFIX-only format for consistent registry matching

- **Supporting Document**: [ENTITY_LIFECYCLE_REFACTOR_SUP_UID_STANDARDIZATION.md](./ENTITY_LIFECYCLE_REFACTOR_SUP_UID_STANDARDIZATION.md)
  (Comprehensive audit of all 45+ entities, pattern analysis, migration proposal)

- **Problem**: Current codebase has inconsistent UID patterns:
  - **SUFFIX** (preferred): `{entry_id}_{kid_id}_{item_id}{SUFFIX}` → suffix matching works
  - **MIDFIX** (problematic): `{entry_id}{MIDFIX}{kid_id}` → suffix matching fails
  - **PREFIX** (problematic): `{entry_id}_{PREFIX}{kid_id}_{item_id}` → suffix matching fails

- **Inconsistent Patterns Found** (to be migrated):

| Current Constant                     | Current Pattern                                   | New Suffix Pattern                               |
| ------------------------------------ | ------------------------------------------------- | ------------------------------------------------ |
| `SELECT_KC_UID_MIDFIX_CHORES_SELECT` | `{entry_id}_select_chores_{kid_id}`               | `{entry_id}_{kid_id}_kid_chores_select`          |
| `BUTTON_KC_UID_MIDFIX_ADJUST_POINTS` | `{entry_id}_{kid_id}_points_adjust_{delta}`       | `{entry_id}_{kid_id}_{delta}_points_adjust`      |
| `BUTTON_REWARD_PREFIX`               | `{entry_id}_reward_button_{kid_id}_{reward_id}`   | `{entry_id}_{kid_id}_{reward_id}_reward_redeem`  |
| `BUTTON_BONUS_PREFIX`                | `{entry_id}_bonus_button_{kid_id}_{bonus_id}`     | `{entry_id}_{kid_id}_{bonus_id}_bonus_apply`     |
| `BUTTON_PENALTY_PREFIX`              | `{entry_id}_penalty_button_{kid_id}_{penalty_id}` | `{entry_id}_{kid_id}_{penalty_id}_penalty_apply` |

- **Standard UID Format** (target):

  ```
  {entry_id}_{kid_id}_{item_id}{SUFFIX}
  ```

  - Always ends with suffix constant
  - Suffix is unique per entity type
  - `should_create_entity()` uses `endswith()` matching

- **Steps / detailed work items**
  1. `[ ]` Add new SUFFIX constants for reward/bonus/penalty buttons
  2. `[ ]` Add new SUFFIX constant for kid dashboard helper select (replace midfix)
  3. `[ ]` Add new SUFFIX constant for points adjust button (replace midfix)
  4. `[ ]` Update ENTITY_REGISTRY with new suffix constants
  5. `[ ]` Add migration logic to rename entity unique_ids in registry
  6. `[ ]` Update entity classes to use new suffix patterns
  7. `[ ]` Remove deprecated PREFIX/MIDFIX constants after migration period

- **Migration Strategy**:
  - Schema migration will rename existing entity unique_ids
  - Old entities get new unique_ids automatically
  - No entity duplication or orphaned entities
  - Handled in existing migration framework

- **New Constants to Add** (const.py):

  ```python
  # Standardized SUFFIX constants (Phase 3C)
  BUTTON_KC_UID_SUFFIX_REWARD_REDEEM: Final = "_reward_redeem"
  BUTTON_KC_UID_SUFFIX_BONUS_APPLY: Final = "_bonus_apply"
  BUTTON_KC_UID_SUFFIX_PENALTY_APPLY: Final = "_penalty_apply"
  BUTTON_KC_UID_SUFFIX_POINTS_ADJUST: Final = "_points_adjust"
  SELECT_KC_UID_SUFFIX_KID_CHORES_SELECT: Final = "_kid_chores_select"
  ```

- **Blocked By**: Phase 3B completion (need unified creation first)
- **Blocks**: Full registry-based cleanup (can't match prefix/midfix patterns)

---

### Phase 4 – Hook Cleanup to Triggers

- **Goal**: Wire cleanup function to appropriate trigger points

- **Steps / detailed work items**
  1. `[x]` Add fresh-startup cleanup to `__init__.py` (runtime key pattern)
  2. `[x]` Add post-migration cleanup call after schema migration (covered by fresh startup)
  3. `[x]` Add cleanup call to options flow when `show_legacy_entities` changes
  4. `[x]` Add cleanup call to options flow when parent `enable_workflow` changes
  5. `[x]` Add cleanup call to options flow when parent `enable_gamification` changes
  6. `[x]` Add cleanup call to unlink service (NOT NEEDED - unlinking enables all entities)
  7. `[x]` Remove all bulk cleanup calls from reload path (already done - runtime key pattern)

- **Cleanup Trigger Matrix** (Hybrid Approach)

| Trigger                                        | Mode              | Parameters                                           |
| ---------------------------------------------- | ----------------- | ---------------------------------------------------- |
| **Fresh HA restart** (not reload)              | Bulk              | `kid_ids=None` (all), all checks                     |
| **Post-migration**                             | Bulk              | `kid_ids=None` (all), all checks                     |
| **Options flow**: `show_legacy_entities`       | Bulk              | `kid_ids=None`, `check_extra=True`, others=False     |
| **Options flow**: Parent `enable_workflow`     | Targeted          | `kid_ids=[shadow_kid_id]`, `check_workflow=True`     |
| **Options flow**: Parent `enable_gamification` | Targeted          | `kid_ids=[shadow_kid_id]`, `check_gamification=True` |
| **Unlink service**: Shadow kid unlinked        | Targeted          | `kid_ids=[shadow_kid_id]`, all checks                |
| **Delete kid**                                 | Existing function | `delete_kid_entity()` (already handles)              |
| **Delete chore**                               | Existing function | `delete_chore_entity()` (already handles)            |

- **Fresh Startup Detection** (same pattern as backup)

```python
# In __init__.py async_setup_entry(), after platform setup
cleanup_key = f"{const.DOMAIN}{const.RUNTIME_KEY_ENTITY_CLEANUP_DONE}{entry.entry_id}"
if not hass.data.get(cleanup_key, False):
    hass.data[cleanup_key] = True
    removed = await coordinator.cleanup_conditional_entities()
    if removed > 0:
        const.LOGGER.info("Fresh startup entity cleanup: removed %d entities", removed)
```

- **Reload Behavior**: NO bulk cleanup. Entities filter at creation time (already working).

---

### Phase 5 – Testing & Validation

- **Goal**: Verify stable entity count across reloads

- **Steps / detailed work items**
  1. `[x]` Test: Count entities → Reload → Count entities (must match)
  2. `[x]` Test: Triple reload → Count entities (must be stable)
  3. `[x]` Test: No unavailable (orphan) entities after setup
  4. `[x]` Test: No unavailable entities after reload
  5. `[x]` Test: Full scenario (3 kids, 18 chores) stable after reload

- **Test File**: `tests/test_entity_lifecycle_stability.py`
  - 8 tests covering STAB-_, ORPHAN-_, FLAG-\* categories
  - All 893 tests pass including new stability tests

---

## Notes & Follow-up

### Simplification Summary

**Before** (scattered logic):

- 4+ orphan scan functions running on every reload
- 5+ `SHADOW_KID_*` tuples
- Legacy suffix list in **init**.py
- Multiple places to update when adding entities
- Race conditions from bulk scans during entity creation

**After** (unified hybrid approach):

- 1 registry dict in const.py (`ENTITY_REGISTRY`)
- 1 filter function in kc_helpers.py (`should_create_entity()`)
- 1 cleanup function in coordinator.py (`cleanup_conditional_entities()`)
- Hybrid triggers:
  - Targeted (options flow, unlink service) - per-kid
  - One-time bulk (fresh startup, post-migration) - all kids
- NO bulk scans on reload (entities filter at creation)

### Migration Notes

- No storage migration needed
- Entity unique_ids unchanged
- Backward compatible
- Orphan functions consolidated (not just removed)

### Future Enhancements

- Add entity count metrics to dashboard helper
- Add entity health diagnostic sensor
- Consider entity creation/removal events for automations
- CRUD services can call targeted cleanup as they expand
