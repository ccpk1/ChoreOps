# UID Pattern Standardization - Supporting Document

**Plan Reference**: [ENTITY_LIFECYCLE_REFACTOR_IN-PROCESS.md](./ENTITY_LIFECYCLE_REFACTOR_IN-PROCESS.md)
**Phase**: 3C
**Created**: Session Date
**Purpose**: Comprehensive audit of UID patterns, alignment with documented standards, and unified migration proposal

---

## 1. Documented Standards (DEVELOPMENT_STANDARDS.md § 6)

Per [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md), the **Entity ID Construction (Dual-Variant System)** defines:

### 1.1 UNIQUE_ID Standard

> **Format**: `entry_id + [_kid_id] + [_entity_id] + SUFFIX`
> **Example**: `..._kid123_points`
> **Purpose**: Internal, stable registry identifier that persists across renames

### 1.2 ENTITY_ID Standard

> **Format**: `domain.kc_[name] + [MIDFIX] + [name2] + [SUFFIX]`
> **Example**: `sensor.kc_sarah_points`
> **Purpose**: User-visible UI identifier for automations and dashboards

### 1.3 Key Pattern Components

| Component  | Usage                  | Location            |
| ---------- | ---------------------- | ------------------- |
| **SUFFIX** | Appended to end        | Both UID and EID    |
| **MIDFIX** | Embedded between names | EID only (per docs) |

**Critical Observation**: The documented standard shows MIDFIX for EID only, but current implementation uses MIDFIX in UIDs, creating inconsistency.

---

## 2. Current UID Patterns in Codebase

### 2.1 Pattern Type A: SUFFIX (Preferred - 40+ Entities)

**Format**: `{entry_id}_{kid_id}_{item_id}{SUFFIX}`
**Matching**: Works with `endswith()` in `should_create_entity()`
**Status**: ✅ ALIGNED with documented standard

#### Examples by Platform

**Sensors (28 entities)**:

```python
# Always
SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR = "_chore_status"
SENSOR_KC_UID_SUFFIX_CHORES_SENSOR = "_kid_chores_summary"
SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER = "_dashboard_helper"
SENSOR_KC_UID_SUFFIX_SHARED_CHORE_GLOBAL_STATE_SENSOR = "_chore_global_status"
SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG = "_dashboard_lang"

# Gamification
SENSOR_KC_UID_SUFFIX_KID_POINTS_SENSOR = "_kid_points"
SENSOR_KC_UID_SUFFIX_KID_BADGES_SENSOR = "_kid_badges"
SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR = "_badge_progress"
SENSOR_KC_UID_SUFFIX_BADGE_SENSOR = "_badge_status"
SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR = "_reward_status"
SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_SENSOR = "_achievement_status"
SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR = "_achievement_progress"
SENSOR_KC_UID_SUFFIX_CHALLENGE_SENSOR = "_challenge_status"
SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR = "_challenge_progress"

# Extra (optional)
SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR = "_chores_completed_total"
SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR = "_chores_completed_daily"
SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR = "_chores_completed_weekly"
SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR = "_chores_completed_monthly"
SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR = "_chores_pending_approvals"
SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR = "_rewards_pending_approvals"
SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR = "_points_earned_daily"
SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR = "_points_earned_weekly"
SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR = "_points_earned_monthly"
SENSOR_KC_UID_SUFFIX_KID_HIGHEST_STREAK_SENSOR = "_chores_highest_streak"
SENSOR_KC_UID_SUFFIX_KID_MAX_POINTS_EVER_SENSOR = "_points_max_ever"
SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR = "_penalty_status"
SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR = "_bonus_status"
```

**Buttons (6 entities)**:

```python
BUTTON_KC_UID_SUFFIX_CLAIM = "_chore_claim"
BUTTON_KC_UID_SUFFIX_APPROVE = "_chore_approve"
BUTTON_KC_UID_SUFFIX_DISAPPROVE = "_chore_disapprove"
BUTTON_KC_UID_SUFFIX_APPROVE_REWARD = "_reward_approve"
BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD = "_reward_disapprove"
```

**Selects (4 system entities)**:

```python
SELECT_KC_UID_SUFFIX_CHORES_SELECT = "_select_chores"
SELECT_KC_UID_SUFFIX_REWARDS_SELECT = "_select_rewards"
SELECT_KC_UID_SUFFIX_BONUSES_SELECT = "_select_bonuses"
SELECT_KC_UID_SUFFIX_PENALTIES_SELECT = "_select_penalties"
```

> **Note**: These system selects use `_select_<entity>` pattern (legacy). Since they're already SUFFIX-based
> and registry-compatible, no migration needed. Documented as acceptable variance from `_<entity>_<type>` convention.

**Datetime (1 entity)**:

```python
DATETIME_KC_UID_SUFFIX_DATE_HELPER = "_dashboard_datetime_picker"
```

**Calendar (1 entity)**:

```python
CALENDAR_KC_UID_SUFFIX_CALENDAR = "_kid_calendar"
```

---

### 2.2 Pattern Type B: MIDFIX (Problematic - 2 Entities)

**Format**: `{entry_id}{MIDFIX}{identifier}`
**Matching**: ❌ Breaks `endswith()` in `should_create_entity()`
**Status**: ⚠️ MISALIGNED - Docs say MIDFIX is for EID only

#### Current Usage

| Constant                             | Value               | Current UID Pattern                         | Issue                                 |
| ------------------------------------ | ------------------- | ------------------------------------------- | ------------------------------------- |
| `SELECT_KC_UID_MIDFIX_CHORES_SELECT` | `"_select_chores_"` | `{entry_id}_select_chores_{kid_id}`         | MIDFIX embedded, can't use endswith() |
| `BUTTON_KC_UID_MIDFIX_ADJUST_POINTS` | `"_points_adjust_"` | `{entry_id}_{kid_id}_points_adjust_{delta}` | MIDFIX embedded, can't use endswith() |

#### Actual UID Construction (from code)

**select.py line 352**:

```python
# KidDashboardHelperChoresSelect
self._attr_unique_id = (
    f"{entry.entry_id}{const.SELECT_KC_UID_MIDFIX_CHORES_SELECT}{kid_id}"
)
# Result: "abc123_select_chores_kid456"
```

> **Migration**: → `SELECT_KC_UID_SUFFIX_KID_CHORES_SELECT = "_kid_chores_select"` (see §4.2, Phase 3C-3)

**button.py line 1542**:

```python
# AdjustPointsButton
self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.BUTTON_KC_UID_MIDFIX_ADJUST_POINTS}{delta}"
# Result: "abc123_kid456_points_adjust_+5"
```

> **Migration**: → `BUTTON_KC_UID_SUFFIX_POINTS_ADJUST = "_points_adjust"` (see §4.2, Phase 3C-2)

---

### 2.3 Pattern Type C: PREFIX (Problematic - 3 Entities)

**Format**: `{entry_id}_{PREFIX}{kid_id}_{item_id}`
**Matching**: ❌ Breaks `endswith()` in `should_create_entity()`
**Status**: ⚠️ NOT DOCUMENTED - No prefix pattern in DEVELOPMENT_STANDARDS.md

#### Current Usage

| Constant                | Value               | Current UID Pattern                               | Issue                         |
| ----------------------- | ------------------- | ------------------------------------------------- | ----------------------------- |
| `BUTTON_REWARD_PREFIX`  | `"reward_button_"`  | `{entry_id}_reward_button_{kid_id}_{reward_id}`   | Prefix breaks suffix matching |
| `BUTTON_BONUS_PREFIX`   | `"bonus_button_"`   | `{entry_id}_bonus_button_{kid_id}_{bonus_id}`     | Prefix breaks suffix matching |
| `BUTTON_PENALTY_PREFIX` | `"penalty_button_"` | `{entry_id}_penalty_button_{kid_id}_{penalty_id}` | Prefix breaks suffix matching |

> **Clarification**: These PREFIX constants are used for:
>
> - `BUTTON_REWARD_PREFIX` → **RewardClaimButton only** (approve/disapprove already use SUFFIX ✅)
> - `BUTTON_BONUS_PREFIX` → **BonusApplyButton** (only action for bonuses)
> - `BUTTON_PENALTY_PREFIX` → **PenaltyApplyButton** (only action for penalties)
>
> Chore buttons already follow SUFFIX pattern (`_chore_claim`, `_chore_approve`, `_chore_disapprove`).
> Reward approve/disapprove also use SUFFIX (`_reward_approve`, `_reward_disapprove`).

#### Actual UID Construction (from code)

**button.py line 825** (RewardClaimButton):

```python
self._attr_unique_id = (
    f"{entry.entry_id}_{const.BUTTON_REWARD_PREFIX}{kid_id}_{reward_id}"
)
# Result: "abc123_reward_button_kid456_reward789"
```

**button.py line 1242** (BonusApplyButton):

```python
self._attr_unique_id = (
    f"{entry.entry_id}_{const.BUTTON_BONUS_PREFIX}{kid_id}_{bonus_id}"
)
# Result: "abc123_bonus_button_kid456_bonus789"
```

**button.py line 1384** (PenaltyApplyButton):

```python
self._attr_unique_id = (
    f"{entry.entry_id}_{const.BUTTON_PENALTY_PREFIX}{kid_id}_{penalty_id}"
)
# Result: "abc123_penalty_button_kid456_penalty789"
```

---

## 3. Impact Analysis

### 3.1 ENTITY_REGISTRY Compatibility

| Pattern | `endswith()` Match | Registry-Compatible | Count |
| ------- | ------------------ | ------------------- | ----- |
| SUFFIX  | ✅ Works           | ✅ Yes              | 40+   |
| MIDFIX  | ❌ Fails           | ❌ No               | 2     |
| PREFIX  | ❌ Fails           | ❌ No               | 3     |

### 3.2 Affected Functionality

**What breaks with non-SUFFIX patterns**:

1. **`should_create_entity()`** - Cannot match MIDFIX/PREFIX entities via registry lookup
2. **`cleanup_conditional_entities()`** - Cannot identify entities for removal
3. **Future whitelist/blacklist features** - Require consistent suffix matching

**Current workarounds**:

- MIDFIX entities are registered with special handling in ENTITY_REGISTRY
- PREFIX entities (bonus/penalty/reward buttons) are NOT in registry - created unconditionally

---

## 4. Unified Pattern Proposal: Class-Aligned Suffixes

### 4.1 Design Principle

**Suffix = Class Name** (lowercased, underscored)

This eliminates ambiguity and substring conflicts. Every entity's suffix exactly matches its Python class name.

```
UNIQUE_ID = {entry_id}[_{kid_id}][_{item_id}]{_class_name_suffix}
```

| Component  | Description                                    | Example                   |
| ---------- | ---------------------------------------------- | ------------------------- |
| `entry_id` | Config entry identifier                        | `abc123`                  |
| `kid_id`   | Kid UUID (optional for system entities)        | `kid456`                  |
| `item_id`  | Chore/reward/bonus/penalty/etc UUID (optional) | `chore789`                |
| `SUFFIX`   | Lowercased class name                          | `_kid_chore_claim_button` |

**Note**: System entities omit `kid_id` entirely - the "system" scope is indicated by the class name prefix in the suffix (e.g., `_system_badge_sensor`).

### 4.2 Complete Class-Aligned Migration Map

#### SENSORS (14 core + 13 legacy)

| Class Name                         | Current Suffix          | New Class-Aligned Suffix               |
| ---------------------------------- | ----------------------- | -------------------------------------- |
| `KidChoreStatusSensor`             | `_chore_status`         | `_kid_chore_status_sensor`             |
| `KidPointsSensor`                  | `_kid_points`           | `_kid_points_sensor`                   |
| `KidChoresSensor`                  | `_kid_chores_summary`   | `_kid_chores_sensor`                   |
| `KidBadgesSensor`                  | `_kid_badges`           | `_kid_badges_sensor`                   |
| `KidBadgeProgressSensor`           | `_badge_progress`       | `_kid_badge_progress_sensor`           |
| `SystemBadgeSensor`                | `_badge_status`         | `_system_badge_sensor`                 |
| `SystemChoreSharedStateSensor`     | `_chore_global_status`  | `_system_chore_shared_state_sensor`    |
| `KidRewardStatusSensor`            | `_reward_status`        | `_kid_reward_status_sensor`            |
| `SystemAchievementSensor`          | `_achievement_status`   | `_system_achievement_sensor`           |
| `SystemChallengeSensor`            | `_challenge_status`     | `_system_challenge_sensor`             |
| `KidAchievementProgressSensor`     | `_achievement_progress` | `_kid_achievement_progress_sensor`     |
| `KidChallengeProgressSensor`       | `_challenge_progress`   | `_kid_challenge_progress_sensor`       |
| `SystemDashboardTranslationSensor` | `_dashboard_lang`       | `_system_dashboard_translation_sensor` |
| `KidDashboardHelperSensor`         | `_dashboard_helper`     | `_kid_dashboard_helper_sensor`         |

**SENSORS - Legacy/Extra (from sensor_legacy.py)**

⚠️ **Class Name Corrections Required**: 4 classes are named "System\*" but are actually PER-KID (they use `kid_id` in UID and `create_kid_device_info`). These classes must be renamed before UID alignment.

| Current Class Name                      | Actual Scope | RENAME TO                         | Current Suffix               | New Class-Aligned Suffix                  |
| --------------------------------------- | ------------ | --------------------------------- | ---------------------------- | ----------------------------------------- |
| ~~`SystemChoreApprovalsSensor`~~        | PER-KID      | `KidChoreCompletionSensor`        | `_chores_completed_total`    | `_kid_chore_completion_sensor`            |
| ~~`SystemChoreApprovalsDailySensor`~~   | PER-KID      | `KidChoreCompletionDailySensor`   | `_chores_completed_daily`    | `_kid_chore_completion_daily_sensor`      |
| ~~`SystemChoreApprovalsWeeklySensor`~~  | PER-KID      | `KidChoreCompletionWeeklySensor`  | `_chores_completed_weekly`   | `_kid_chore_completion_weekly_sensor`     |
| ~~`SystemChoreApprovalsMonthlySensor`~~ | PER-KID      | `KidChoreCompletionMonthlySensor` | `_chores_completed_monthly`  | `_kid_chore_completion_monthly_sensor`    |
| `SystemChoresPendingApprovalSensor`     | SYSTEM ✓     | _(no change)_                     | `_chores_pending_approvals`  | `_system_chores_pending_approval_sensor`  |
| `SystemRewardsPendingApprovalSensor`    | SYSTEM ✓     | _(no change)_                     | `_rewards_pending_approvals` | `_system_rewards_pending_approval_sensor` |
| `KidPointsEarnedDailySensor`            | PER-KID ✓    | _(no change)_                     | `_points_earned_daily`       | `_kid_points_earned_daily_sensor`         |
| `KidPointsEarnedWeeklySensor`           | PER-KID ✓    | _(no change)_                     | `_points_earned_weekly`      | `_kid_points_earned_weekly_sensor`        |
| `KidPointsEarnedMonthlySensor`          | PER-KID ✓    | _(no change)_                     | `_points_earned_monthly`     | `_kid_points_earned_monthly_sensor`       |
| `KidPointsMaxEverSensor`                | PER-KID ✓    | _(no change)_                     | `_points_max_ever`           | `_kid_points_max_ever_sensor`             |
| `KidChoreStreakSensor`                  | PER-KID ✓    | _(no change)_                     | `_chores_highest_streak`     | `_kid_chore_streak_sensor`                |
| `KidPenaltyAppliedSensor`               | PER-KID ✓    | _(no change)_                     | `_penalty_status`            | `_kid_penalty_applied_sensor`             |
| `KidBonusAppliedSensor`                 | PER-KID ✓    | _(no change)_                     | `_bonus_status`              | `_kid_bonus_applied_sensor`               |

#### BUTTONS (9 total)

| Class Name                     | Current Suffix/Pattern    | New Class-Aligned Suffix           |
| ------------------------------ | ------------------------- | ---------------------------------- |
| `KidChoreClaimButton`          | `_chore_claim`            | `_kid_chore_claim_button`          |
| `ParentChoreApproveButton`     | `_chore_approve`          | `_parent_chore_approve_button`     |
| `ParentChoreDisapproveButton`  | `_chore_disapprove`       | `_parent_chore_disapprove_button`  |
| `KidRewardRedeemButton`        | PREFIX: `reward_button_`  | `_kid_reward_redeem_button`        |
| `ParentRewardApproveButton`    | `_reward_approve`         | `_parent_reward_approve_button`    |
| `ParentRewardDisapproveButton` | `_reward_disapprove`      | `_parent_reward_disapprove_button` |
| `ParentBonusApplyButton`       | PREFIX: `bonus_button_`   | `_parent_bonus_apply_button`       |
| `ParentPenaltyApplyButton`     | PREFIX: `penalty_button_` | `_parent_penalty_apply_button`     |
| `ParentPointsAdjustButton`     | MIDFIX: `_points_adjust_` | `_parent_points_adjust_button`     |

#### SELECTS (5 total)

| Class Name                       | Current Suffix/Pattern    | New Class-Aligned Suffix              |
| -------------------------------- | ------------------------- | ------------------------------------- |
| `SystemChoresSelect`             | `_select_chores`          | `_system_chores_select`               |
| `SystemRewardsSelect`            | `_select_rewards`         | `_system_rewards_select`              |
| `SystemBonusesSelect`            | `_select_bonuses`         | `_system_bonuses_select`              |
| `SystemPenaltiesSelect`          | `_select_penalties`       | `_system_penalties_select`            |
| `KidDashboardHelperChoresSelect` | MIDFIX: `_select_chores_` | `_kid_dashboard_helper_chores_select` |

#### DATETIME (1 total)

| Class Name                         | Current Suffix               | New Class-Aligned Suffix                |
| ---------------------------------- | ---------------------------- | --------------------------------------- |
| `KidDashboardHelperDateTimePicker` | `_dashboard_datetime_picker` | `_kid_dashboard_helper_datetime_picker` |

#### CALENDAR (1 total)

| Class Name            | Current Suffix  | New Class-Aligned Suffix |
| --------------------- | --------------- | ------------------------ |
| `KidScheduleCalendar` | `_kid_calendar` | `_kid_schedule_calendar` |

### 4.3 Migration Script Update

The migration script maps **ORIGINAL** → **CLASS-ALIGNED** (single transformation):

```python
uid_migration_map: dict[str, str] = {
    # === SENSORS (core) ===
    "_status": "_kid_chore_status_sensor",
    "_points": "_kid_points_sensor",
    "_chores": "_kid_chores_sensor",
    "_kid_badges": "_kid_badges_sensor",
    "_badge_progress": "_kid_badge_progress_sensor",
    "_badge_status": "_system_badge_sensor",
    "_chore_global_status": "_system_chore_shared_state_sensor",
    "_reward_status": "_kid_reward_status_sensor",
    "_achievement_status": "_system_achievement_sensor",
    "_challenge_status": "_system_challenge_sensor",
    "_achievement_progress": "_kid_achievement_progress_sensor",
    "_challenge_progress": "_kid_challenge_progress_sensor",
    "_dashboard_lang": "_system_dashboard_translation_sensor",
    "_dashboard_helper": "_kid_dashboard_helper_sensor",

    # === SENSORS (legacy/extra) ===
    # NOTE: 4 classes will be renamed from System* to Kid* (see table above)
    "_chores_completed_total": "_kid_chore_approvals_sensor",
    "_chores_completed_daily": "_kid_chore_approvals_daily_sensor",
    "_chores_completed_weekly": "_kid_chore_approvals_weekly_sensor",
    "_chores_completed_monthly": "_kid_chore_approvals_monthly_sensor",
    "_chores_pending_approvals": "_system_chores_pending_approval_sensor",
    "_rewards_pending_approvals": "_system_rewards_pending_approval_sensor",
    "_points_earned_daily": "_kid_points_earned_daily_sensor",
    "_points_earned_weekly": "_kid_points_earned_weekly_sensor",
    "_points_earned_monthly": "_kid_points_earned_monthly_sensor",
    "_chores_highest_streak": "_kid_chore_streak_sensor",
    "_points_max_ever": "_kid_points_max_ever_sensor",
    "_bonus_status": "_kid_bonus_applied_sensor",
    "_penalty_status": "_kid_penalty_applied_sensor",

    # === BUTTONS ===
    "_claim": "_kid_chore_claim_button",
    "_approve": "_parent_chore_approve_button",
    "_chore_disapprove": "_parent_chore_disapprove_button",  # NOTE: "disapprove", not "unclaim"
    "_reward_approve": "_parent_reward_approve_button",
    "_reward_disapprove": "_parent_reward_disapprove_button",
    # Note: PREFIX buttons (reward_redeem, bonus_apply, penalty_apply) and
    # MIDFIX buttons (points_adjust) need pattern-based migration, not suffix

    # === SELECTS ===
    "_chores_select": "_system_chores_select",
    "_rewards_select": "_system_rewards_select",
    "_bonuses_select": "_system_bonuses_select",
    "_penalties_select": "_system_penalties_select",
    # Note: MIDFIX select (kid_dashboard_helper_chores) needs pattern-based migration

    # === DATETIME ===
    "_date_helper": "_kid_dashboard_helper_datetime_picker",

    # === CALENDAR ===
    "_calendar": "_kid_schedule_calendar",
}
```

### 4.4 Conflict Analysis

With class-aligned suffixes, **no substring conflicts exist**:

```python
# Example: System vs Kid chores select
"abc123_system_chores_select".endswith("_system_chores_select")  # True
"abc123_kid456_kid_dashboard_helper_chores_select".endswith("_system_chores_select")  # False ✅

# All suffixes are unique class names - no ambiguity
```

### 4.5 Summary of Changes

| Category                | Count  | Change Type                          |
| ----------------------- | ------ | ------------------------------------ |
| **Class Renames**       | **4**  | **sensor_legacy.py: System* → Kid*** |
| Sensors (core)          | 14     | Suffix update                        |
| Sensors (legacy)        | 13     | Suffix update                        |
| Buttons (suffix)        | 6      | Suffix update                        |
| Buttons (PREFIX→SUFFIX) | 3      | Clean break (pattern migration)      |
| Buttons (MIDFIX→SUFFIX) | 1      | Clean break (pattern migration)      |
| Selects (suffix)        | 4      | Suffix update                        |
| Selects (MIDFIX→SUFFIX) | 1      | Clean break (pattern migration)      |
| Datetime                | 1      | Suffix update                        |
| Calendar                | 1      | Suffix update                        |
| **TOTAL ENTITIES**      | **44** |                                      |

**Implementation Scope:**

1. ✅ Rename 4 classes in `sensor_legacy.py` (System* → Kid*)
2. ✅ Update all UID SUFFIX constants in `const.py` (~44 values)
3. ✅ PREFIX/MIDFIX entities: Clean break (no migration script needed)
4. ✅ SUFFIX entities: Migration script maps old → new
5. ✅ "disapprove" confirmed (not "unclaim" - that's a kid feature)

---

## 5. Migration Considerations

### 5.1 Breaking Changes

⚠️ **UID changes break entity history**

Changing `unique_id` creates a new entity in Home Assistant registry:

- Old entity's history is orphaned
- User customizations (names, icons, areas) are lost
- Automations referencing `entity_id` still work (entity_id unchanged)

### 5.2 Migration Options

**Option A: Clean Break (Recommended for v1.0)**

- Change UIDs directly
- Document breaking change in release notes
- Users get clean entity registry

**Option B: Parallel Support (Gradual)**

- Keep old UID patterns working during transition
- Add migration logic to update registry
- More complex, but preserves history

**Option C: Registry Migration Script**

- One-time script to migrate entity registry entries
- Complex, requires HA internals knowledge

### 5.3 Recommendation

For KidsChores (pre-1.0), **Option A (Clean Break)** is recommended:

- Simpler implementation
- Entity history for chore tracking is not critical
- Can be done as part of major version bump

---

## 6. Implementation Phases

### Phase 3C-1: Add New SUFFIX Constants

- [x] Add 5 new `*_KC_UID_SUFFIX_*` constants
- [x] Update ENTITY_REGISTRY with new entries
- [x] Mark old PREFIX/MIDFIX constants as deprecated with comments

### Phase 3C-2: Update Button UID Construction

- [x] Update `KidRewardRedeemButton.__init__()` to use new suffix pattern
- [x] Update `ParentBonusApplyButton.__init__()` to use new suffix pattern
- [x] Update `ParentPenaltyApplyButton.__init__()` to use new suffix pattern
- [x] Update `ParentPointsAdjustButton.__init__()` to use new suffix pattern

### Phase 3C-3: Update Select UID Construction

- [x] Update `KidDashboardHelperChoresSelect.__init__()` to use new suffix pattern

### Phase 3C-4: Cleanup & Validation

- [x] Run full test suite
- [x] Verify all entities use SUFFIX pattern
- [x] Update DEVELOPMENT_STANDARDS.md to explicitly prohibit MIDFIX/PREFIX in UIDs
- [x] Remove deprecated constants (or mark for future removal)

---

## 7. Summary

| Category                          | Count | Status      |
| --------------------------------- | ----- | ----------- |
| SUFFIX entities (aligned)         | 40+   | ✅ Ready    |
| MIDFIX entities (needs migration) | 2     | ⚠️ Phase 3C |
| PREFIX entities (needs migration) | 3     | ⚠️ Phase 3C |
| **Total requiring migration**     | **5** |             |

**Key Insight**: The documented standard in DEVELOPMENT_STANDARDS.md is correct (SUFFIX for UID, MIDFIX for EID only). The 5 non-compliant entities are implementation bugs that pre-date the standard documentation.
