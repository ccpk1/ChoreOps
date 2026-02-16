# Phase 1 Findings - Data Model Analysis

**Date**: January 29, 2026
**Phase**: Phase 1 - Data Model Analysis
**Status**: Complete

## Executive Summary

Comprehensive audit of all timestamp usage in KidsChores v0.5.0-beta3 reveals:

- **last_claimed**: Currently ONLY used for display/audit, NOT for calculations
- **last_approved**: Primary timestamp for ALL calculations (stats, streaks, scheduling)
- **last_completed**: Chore-level field used ONLY for FREQUENCY_CUSTOM_FROM_COMPLETE scheduling
- **now_iso**: Used 2x in approval flow for timestamp generation
- **StatisticsEngine**: Already supports reference_date parameter (ready for Phase 4)
- **Event payload**: ChoreApprovedEvent lacks effective_date field (needs addition)

## Step 1: `last_claimed` Current Usage

### Storage Locations

1. **Kid-level**: `kid_chore_data[DATA_KID_CHORE_DATA_LAST_CLAIMED]` (line const.py:797)
2. **Kid-level (rewards)**: `kid_reward_data[DATA_KID_REWARD_DATA_LAST_CLAIMED]` (line const.py:989)
3. **Chore-level**: `chore_data[DATA_CHORE_LAST_CLAIMED]` (line const.py:1295) - UNUSED in current code

### Write Operations

1. **ChoreManager claim workflow** (chore_manager.py:242)

   ```python
   kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = dt_now_iso()
   ```

   - Set when kid claims chore

2. **ChoreManager direct approval** (chore_manager.py:2330)

   ```python
   if not has_pending_claim:
       kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = now_iso
   ```

   - Set when parent approves without claim (direct approval)

3. **RewardManager** (reward_manager.py - similar pattern for rewards)

### Read Operations (Display Only)

1. **Dashboard Helper Sensor** (sensor.py:928, 2398)
   - Retrieves for display in state attributes
   - Exposes to dashboard for timeline/display
   - NOT used for any calculations

2. **Chore Sensor** (sensor.py:1001, 2109)
   - Exposed as `ATTR_LAST_CLAIMED` attribute
   - Display only, not used internally

### Key Finding

**❌ CURRENTLY NOT USED FOR ANY CALCULATIONS**

- Statistics: Uses `last_approved` (not claim)
- Streaks: Uses `last_approved` (not claim)
- Scheduling: Uses `last_completed` or `last_approved` (not claim)
- Period bucketing: Uses approval time via StatisticsManager

---

## Step 2: `last_approved` Current Usage

### Storage Locations

1. **Kid-level**: `kid_chore_data[DATA_KID_CHORE_DATA_LAST_APPROVED]` (const.py:796)
2. **Kid-level (rewards)**: `kid_reward_data[DATA_KID_REWARD_DATA_LAST_APPROVED]` (const.py:990)

### Write Operations

1. **ChoreManager approval** (chore_manager.py:2325)
   ```python
   kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso
   ```

   - Primary timestamp set during approval workflow

### Read Operations (Calculations)

#### 1. Approval Period Check (chore_manager.py:1867-1877)

```python
last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
if not last_approved:
    return False
approved_dt = dt_to_utc(last_approved)
return approved_dt >= period_start_dt
```

- Determines if chore approved in current period
- Used for multi-approval reset logic

#### 2. Streak Calculation (chore_manager.py:2279, 2336)

```python
previous_last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
# ... later ...
new_streak = ChoreEngine.calculate_streak(
    current_streak=previous_streak,
    previous_last_approved_iso=previous_last_approved,  # ← USES APPROVAL TIMESTAMP
    now_iso=now_iso,
    chore_data=chore_data,
)
```

- **ChoreEngine.calculate_streak()** (chore_engine.py:795-820)
- Compares previous approval to current approval for streak continuation
- **THIS IS WHERE PARENT LAG BREAKS STREAKS**

#### 3. ChoreEngine approval validation (chore_engine.py:668-677)

```python
last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
if not last_approved:
    return False, const.CFOE_CHORE_NOT_CLAIMED
approved_dt = dt_to_utc(last_approved)
return approved_dt >= period_start_dt
```

- Validates approval state for re-approval blocking

#### 4. Overdue detection (chore_manager.py:3407)

```python
last_approved_str = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
```

- Checks if chore overdue based on last approval time

### Key Finding

**✅ PRIMARY TIMESTAMP FOR ALL CALCULATIONS**

- Used by: Approval validation, streak calculation, period checks, overdue detection
- THIS is the timestamp causing "parent lag" issues
- **Must be replaced with `last_claimed` in Phases 3-6**

---

## Step 3: `last_completed` Usage (Chore-Level)

### Storage Location

**Chore-level only**: `chore_data[DATA_CHORE_LAST_COMPLETED]` (const.py:1296)

### Write Operations

1. **UPON_COMPLETION reset** (chore_manager.py:2397)
   ```python
   if should_reset_immediately:
       chore_data[const.DATA_CHORE_LAST_COMPLETED] = now_iso
   ```

   - Set ONLY when chore has `APPROVAL_RESET_UPON_COMPLETION`
   - Set when completion criteria satisfied (all assigned kids approved)
   - **Currently uses approval timestamp `now_iso`** ← NEEDS CHANGE

### Read Operations

1. **Schedule calculation** (chore_manager.py:3305)

   ```python
   last_completed_str = chore_info.get(const.DATA_CHORE_LAST_COMPLETED)
   ```

   - Used by ScheduleEngine for `FREQUENCY_CUSTOM_FROM_COMPLETE`
   - Calculates next due date from completion timestamp
   - **THIS CAUSES SCHEDULE DRIFT WHEN PARENT DELAYS APPROVAL**

2. **Dashboard display** (sensor.py:2110)
   - Exposed as attribute for display
   - Shows when chore last completed as a whole

3. **Migration** (migration_pre_v50.py:697-699)
   - DateTime format migration from pre-v5.0

### Key Finding

**⚠️ CHORE-LEVEL TIMESTAMP FOR SCHEDULING**

- Only used for `FREQUENCY_CUSTOM_FROM_COMPLETE` chore types
- Currently set to approval time (causing drift)
- **Must be set to claim timestamp** (Phase 3 Step 4)
- **SHARED_ALL logic**: Must use latest claim among all assigned kids

---

## Step 4: `now_iso` Usage in Approval Flow

### Locations

1. **ChoreManager.\_approve_chore_locked()** (line 2322)

   ```python
   now_iso = dt_now_iso()
   # Set last_approved timestamp
   kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso
   # ... later ...
   if not has_pending_claim:
       kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = now_iso
   # ... later ...
   new_streak = ChoreEngine.calculate_streak(..., now_iso=now_iso, ...)
   # ... later ...
   chore_data[const.DATA_CHORE_LAST_COMPLETED] = now_iso  # If UPON_COMPLETION
   ```

   - **Used for**: last_approved, last_claimed (direct approval), streak calc, last_completed
   - **Problem**: Single timestamp for all purposes
   - **Solution**: Extract `effective_date` from `last_claimed`, use for calculations

2. **ChoreManager.\_cancel_chore_locked()** (line 3263)
   ```python
   now_iso = dt_now_iso()
   ```

   - Used for cancellation timestamp (not affected by this refactor)

### Key Finding

**🎯 SINGLE TIMESTAMP GENERATION POINT**

- Currently: `now_iso` used for everything
- **Target**: Replace with `effective_date = last_claimed` for calculations
- Keep `now_iso` ONLY for `last_approved` (audit trail)

---

## Step 5: StatisticsEngine Callers

### StatisticsEngine.record_transaction() Signature

```python
def record_transaction(
    self,
    period_data: dict[str, Any],
    increments: Mapping[str, int | float],
    period_key_mapping: Mapping[str, str] | None = None,
    include_all_time: bool = True,
    reference_date: date | datetime | None = None,  # ← ALREADY EXISTS!
) -> None:
```

- **ALREADY SUPPORTS `reference_date` PARAMETER!**
- Defaults to today if not provided
- Used by `get_period_keys()` for bucket generation

### Callers (All in Managers)

#### 1. StatisticsManager.\_record_points_transaction() (line 276)

```python
self._stats_engine.record_transaction(
    periods_data,
    {const.DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL: delta},
    period_key_mapping=period_mapping,  # Generated from dt_now_local()
)
```

- **Currently**: Uses current time for period_mapping
- **Change needed**: Pass `reference_date` from event payload

#### 2. RewardManager.\_update_stats_for_kid() (line 263)

```python
self.coordinator.stats.record_transaction(
    periods,
    {counter_key: amount},
    period_key_mapping=period_mapping,  # Generated from dt_now_local()
)
```

- **Currently**: Uses current time
- **Change needed**: Extract from approval event

#### 3. StatisticsEngine internal calls (lines 82, 190, 197)

- Self-referential calls within StatisticsEngine
- Uses same `reference_date` parameter pattern

### Key Finding

**✅ INFRASTRUCTURE ALREADY IN PLACE**

- `reference_date` parameter exists and functional
- Only need to update callers to pass effective_date
- No changes needed to StatisticsEngine itself
- **Phase 4 will be straightforward**

---

## Step 6: Event Payload Structure

### ChoreApprovedEvent (type_defs.py:903-925)

```python
class ChoreApprovedEvent(TypedDict, total=False):
    kid_id: str  # Required
    chore_id: str  # Required
    parent_name: str  # Required
    points_awarded: float  # Required
    is_shared: bool  # Required
    is_multi_claim: bool  # Required
    chore_name: str
    chore_labels: list[str]
    multiplier_applied: float
    previous_state: str
    update_stats: bool
    # ❌ NO effective_date FIELD
```

### Event Emission (chore_manager.py:2458-2474)

```python
self.emit(
    const.SIGNAL_SUFFIX_CHORE_APPROVED,
    kid_id=kid_id,
    chore_id=chore_id,
    parent_name=parent_name,
    points_awarded=points_to_award,
    is_shared=is_shared,
    is_multi_claim=is_multi_claim,
    chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
    chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
    multiplier_applied=multiplier,
    previous_state=previous_state,
    update_stats=True,
    # ❌ NO effective_date
)
```

### Event Consumers

1. **StatisticsManager.\_on_chore_approved()** (line 139)
   - Listens to SIGNAL_SUFFIX_CHORE_APPROVED
   - Currently uses `dt_now_local()` for period_mapping
   - **Needs**: Extract `effective_date` from event payload

2. **GamificationManager.\_on_chore_approved()** (line 109)
   - Achievement/badge tracking
   - May need effective_date for timestamp-based achievements

### Key Finding

**⚠️ EVENT PAYLOAD MISSING EFFECTIVE_DATE**

- Must add `effective_date: str` field to ChoreApprovedEvent
- Emit in chore_manager approval flow
- Consumers must extract and use for period bucketing
- **Backward compatible**: Optional field, old listeners ignore it

---

## Implementation Roadmap (Based on Findings)

### Phase 2 - Completion Type Logic Design

- Document timestamp resolution for SHARED_ALL (latest claim among all kids)
- Create decision matrix for all completion types

### Phase 3 - ChoreManager Refactor

**Priority 1 Changes**:

1. Extract `effective_date` from `last_claimed` at start of approval (line ~2320)
2. Replace `now_iso` with `effective_date` in streak calculation (line 2336)
3. Use `effective_date` for period bucket keys (line ~2340)
4. Set `last_completed` to claim timestamp(s) based on completion type (line 2397)
5. Add `effective_date` to event payload (line 2458)

### Phase 4 - Statistics Integration

**Low effort** (infrastructure exists):

1. Update StatisticsManager to extract `effective_date` from event
2. Pass `reference_date` to `record_transaction()` calls
3. Add fallback for events without `effective_date` (backward compat)

### Phase 5 - Schedule Integration

**Minimal changes**:

- `last_completed` changes from Phase 3 automatically fix schedule drift
- Verify ScheduleEngine correctly uses updated `last_completed`

### Phase 6 - Streak & Period Logic

**Already covered in Phase 3**:

- Streak calculation uses `effective_date` (Phase 3 Step 2)
- Period bucketing uses `effective_date` (Phase 3 Step 3)

### Phase 7 - Testing & Documentation

- 82 test scenarios
- Documentation updates (6 files)

---

## Risk Assessment

### Low Risk Items

✅ StatisticsEngine already supports reference_date
✅ Event payload backward compatible (optional field)
✅ Chore-level last_completed is isolated (only scheduling)

### Medium Risk Items

⚠️ Streak calculation logic change (must verify schedule-aware logic)
⚠️ SHARED_ALL timestamp resolution (complex multi-kid logic)
⚠️ Period bucketing edge cases (timezone, date boundaries)

### High Risk Items

🔴 Test coverage scope (82 scenarios across 3 completion types)
🔴 Backward compatibility (existing chores without `last_claimed`)
🔴 Dashboard sync (may need updates if timestamp display changes)

---

## Next Steps

✅ **Phase 1 Complete** - All timestamp usage mapped
➡️ **Phase 2 Start** - Design completion type logic (focus on SHARED_ALL)

### Phase 2 Prerequisites Met

- [x] Know all current timestamp usage locations
- [x] Identified infrastructure capabilities (reference_date exists)
- [x] Documented event payload changes needed
- [x] Assessed risk levels per component

### Ready to Proceed

Phase 2 can begin immediately with comprehensive understanding of current architecture.
