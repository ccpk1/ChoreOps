# Entity Loading Extension - YAML Key Mapping Reference

**Supporting Document for**: ENTITY_LOADING_EXTENSION_IN-PROCESS.md
**Purpose**: Detailed field mappings for all entity types
**Last Updated**: 2025-06-05

---

## Overview

This document provides exact mappings between:

- **YAML keys** (used in test scenarios)
- **CFOF constants** (config/options flow input keys)
- **DATA constants** (storage format keys)
- **Default values** (when field omitted in YAML)

All mappings derived from `custom_components/kidschores/flow_helpers.py` schema builders.

---

## Simple Entities (Pattern 1: Separate validate/build)

### Rewards

**Schema Function**: `build_reward_schema(default)` (line 2266)
**Data Builder**: `build_rewards_data(user_input)` (line ~2300)
**Validation**: `validate_rewards_inputs(user_input, existing_rewards)` (line ~2340)

| YAML Key      | CFOF Constant                    | DATA Constant             | Type  | Required | Default                    |
| ------------- | -------------------------------- | ------------------------- | ----- | -------- | -------------------------- |
| `name`        | `CFOF_REWARDS_INPUT_NAME`        | `DATA_REWARD_NAME`        | str   | ✅       | SENTINEL_EMPTY             |
| `description` | `CFOF_REWARDS_INPUT_DESCRIPTION` | `DATA_REWARD_DESCRIPTION` | str   | ❌       | SENTINEL_EMPTY             |
| `cost`        | `CFOF_REWARDS_INPUT_COST`        | (internal to schema)      | float | ✅       | DEFAULT_REWARD_COST (10.0) |
| `icon`        | `CFOF_REWARDS_INPUT_ICON`        | `DATA_REWARD_ICON`        | str   | ❌       | SENTINEL_EMPTY             |
| `labels`      | `CFOF_REWARDS_INPUT_LABELS`      | (stored separately)       | list  | ❌       | []                         |

**YAML Example**:

```yaml
rewards:
  - name: "Extra Screen Time"
    description: "30 minutes of extra screen time"
    cost: 50.0
    icon: "mdi:television"
    labels: ["fun", "digital"]
```

**Validation Rules**:

- Name cannot be empty
- Name must be unique across all rewards
- Cost must be ≥ 0

---

### Penalties

**Schema Function**: `build_penalty_schema(default)` (line 2501)
**Data Builder**: `build_penalties_data(user_input)` (line ~2540)
**Validation**: `validate_penalties_inputs(user_input, existing_penalties)` (line ~2580)

| YAML Key      | CFOF Constant                      | DATA Constant              | Type  | Required | Default                      | Notes                                 |
| ------------- | ---------------------------------- | -------------------------- | ----- | -------- | ---------------------------- | ------------------------------------- |
| `name`        | `CFOF_PENALTIES_INPUT_NAME`        | `DATA_PENALTY_NAME`        | str   | ✅       | SENTINEL_EMPTY               |                                       |
| `description` | `CFOF_PENALTIES_INPUT_DESCRIPTION` | `DATA_PENALTY_DESCRIPTION` | str   | ❌       | SENTINEL_EMPTY               |                                       |
| `points`      | `CFOF_PENALTIES_INPUT_POINTS`      | `DATA_PENALTY_POINTS`      | float | ✅       | DEFAULT_PENALTY_POINTS (5.0) | **YAML: positive, Storage: negative** |
| `icon`        | `CFOF_PENALTIES_INPUT_ICON`        | `DATA_PENALTY_ICON`        | str   | ❌       | SENTINEL_EMPTY               |                                       |
| `labels`      | `CFOF_PENALTIES_INPUT_LABELS`      | (stored separately)        | list  | ❌       | []                           |                                       |

**YAML Example**:

```yaml
penalties:
  - name: "Missed Chore"
    description: "Forgot to complete assigned chore"
    points: 10.0 # Positive in YAML, converted to -10.0 in storage
    icon: "mdi:alert-circle"
    labels: ["behavior"]
```

**Validation Rules**:

- Name cannot be empty
- Name must be unique across all penalties
- Points must be ≥ 0 (will be stored as negative)

**Critical Note**: Points stored as NEGATIVE in database but displayed/input as POSITIVE. build_penalties_data() converts: `DATA_PENALTY_POINTS: -abs(points)`

---

### Bonuses

**Schema Function**: `build_bonus_schema(default)` (line 2380)
**Data Builder**: `build_bonuses_data(user_input)` (line ~2420)
**Validation**: `validate_bonuses_inputs(user_input, existing_bonuses)` (line ~2460)

| YAML Key      | CFOF Constant                    | DATA Constant            | Type  | Required | Default                     | Notes                  |
| ------------- | -------------------------------- | ------------------------ | ----- | -------- | --------------------------- | ---------------------- |
| `name`        | `CFOF_BONUSES_INPUT_NAME`        | `DATA_BONUS_NAME`        | str   | ✅       | SENTINEL_EMPTY              |                        |
| `description` | `CFOF_BONUSES_INPUT_DESCRIPTION` | `DATA_BONUS_DESCRIPTION` | str   | ❌       | SENTINEL_EMPTY              |                        |
| `points`      | `CFOF_BONUSES_INPUT_POINTS`      | `DATA_BONUS_POINTS`      | float | ✅       | DEFAULT_BONUS_POINTS (10.0) | **Stored as positive** |
| `icon`        | `CFOF_BONUSES_INPUT_ICON`        | `DATA_BONUS_ICON`        | str   | ❌       | DEFAULT_BONUS_ICON          |                        |
| `labels`      | `CFOF_BONUSES_INPUT_LABELS`      | (stored separately)      | list  | ❌       | []                          |                        |

**YAML Example**:

```yaml
bonuses:
  - name: "Extra Effort"
    description: "Went above and beyond expectations"
    points: 20.0 # Stored as positive
    icon: "mdi:star-circle"
    labels: ["excellence"]
```

**Validation Rules**:

- Name cannot be empty
- Name must be unique across all bonuses
- Points must be ≥ 0 (stored as-is, unlike penalties)

---

## Medium Complexity Entities (Pattern 2: Kids/Chores Dependencies)

### Achievements

**Schema Function**: `build_achievement_schema(kids_dict, chores_dict, default)` (line 2891)
**Data Builder**: `build_achievements_data(user_input, ...)` (line ~2950)
**Validation**: `validate_achievements_inputs(user_input, ...)` (line ~3000)

| YAML Key        | CFOF Constant                           | DATA Constant                  | Type      | Required | Default        | Notes                                     |
| --------------- | --------------------------------------- | ------------------------------ | --------- | -------- | -------------- | ----------------------------------------- |
| `name`          | `CFOF_ACHIEVEMENTS_INPUT_NAME`          | `DATA_ACHIEVEMENT_NAME`        | str       | ✅       | SENTINEL_EMPTY |                                           |
| `description`   | `CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION`   | `DATA_ACHIEVEMENT_DESCRIPTION` | str       | ❌       | SENTINEL_EMPTY |                                           |
| `assigned_kids` | `CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_KIDS` | (stored as list of UUIDs)      | list[str] | ✅       | []             | **YAML uses kid NAMES, flow needs UUIDs** |
| `criteria`      | `CFOF_ACHIEVEMENTS_INPUT_CRITERIA`      | (internal to schema)           | str       | ❌       | SENTINEL_EMPTY |                                           |
| `icon`          | `CFOF_ACHIEVEMENTS_INPUT_ICON`          | `DATA_ACHIEVEMENT_ICON`        | str       | ❌       | SENTINEL_EMPTY |                                           |
| `labels`        | `CFOF_ACHIEVEMENTS_INPUT_LABELS`        | (stored separately)            | list      | ❌       | []             |                                           |

**YAML Example**:

```yaml
achievements:
  - name: "Early Bird"
    description: "Complete 5 chores before noon"
    assigned_kids: ["Zoë", "Max!"] # Kid NAMES (must exist in kids section)
    criteria: "Complete 5 chores before noon"
    icon: "mdi:weather-sunset-up"
    labels: ["morning", "productivity"]
```

**Validation Rules**:

- Name cannot be empty
- Name must be unique across all achievements
- assigned_kids list cannot be empty
- Each kid name in assigned_kids must exist in kids_dict (setup must validate)

**Critical Requirements**:

1. **Kids must be loaded FIRST** - Schema builder requires `kids_dict` parameter
2. **Name→UUID Conversion** - setup_from_yaml() must convert kid names to UUIDs before submitting
3. **Conversion Pattern**:
   ```python
   kid_names = achievement_data["assigned_kids"]  # ["Zoë", "Max!"]
   kid_uuids = [kid_ids[name] for name in kid_names]  # [uuid1, uuid2]
   user_input[CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_KIDS] = kid_uuids
   ```

---

### Challenges

**Schema Function**: `build_challenge_schema(kids_dict, chores_dict, default)` (line 3015)
**Data Builder**: `build_challenges_data(user_input, ...)` (line ~3074)
**Validation**: `validate_challenges_inputs(user_input, ...)` (line ~3120)

| YAML Key        | CFOF Constant                         | DATA Constant                | Type      | Required | Default                                | Notes                                     |
| --------------- | ------------------------------------- | ---------------------------- | --------- | -------- | -------------------------------------- | ----------------------------------------- |
| `name`          | `CFOF_CHALLENGES_INPUT_NAME`          | `DATA_CHALLENGE_NAME`        | str       | ✅       | SENTINEL_EMPTY                         |                                           |
| `description`   | `CFOF_CHALLENGES_INPUT_DESCRIPTION`   | `DATA_CHALLENGE_DESCRIPTION` | str       | ❌       | SENTINEL_EMPTY                         |                                           |
| `assigned_kids` | `CFOF_CHALLENGES_INPUT_ASSIGNED_KIDS` | (stored as list of UUIDs)    | list[str] | ✅       | []                                     | **YAML uses kid NAMES, flow needs UUIDs** |
| `type`          | `CFOF_CHALLENGES_INPUT_TYPE`          | (internal to schema)         | str       | ✅       | DEFAULT_CHALLENGE_TYPE ("chore_count") |                                           |
| `criteria`      | `CFOF_CHALLENGES_INPUT_CRITERIA`      | (internal to schema)         | str       | ❌       | SENTINEL_EMPTY                         |                                           |
| `reward_points` | `CFOF_CHALLENGES_INPUT_REWARD_POINTS` | (internal to schema)         | float     | ❌       | 0.0                                    |                                           |
| `icon`          | `CFOF_CHALLENGES_INPUT_ICON`          | `DATA_CHALLENGE_ICON`        | str       | ❌       | SENTINEL_EMPTY                         |                                           |
| `labels`        | `CFOF_CHALLENGES_INPUT_LABELS`        | (stored separately)          | list      | ❌       | []                                     |                                           |

**YAML Example**:

```yaml
challenges:
  - name: "Weekend Warrior"
    description: "Complete 10 chores this weekend"
    assigned_kids: ["Zoë", "Max!", "Lila"]
    type: "chore_count"
    criteria: "Complete 10 chores"
    reward_points: 50.0
    icon: "mdi:trophy"
    labels: ["weekend", "teamwork"]
```

**Validation Rules**:

- Name cannot be empty
- Name must be unique across all challenges
- assigned_kids list cannot be empty
- Each kid name must exist in kids_dict
- type must be valid challenge type (e.g., "chore_count", "specific_chore")

**Critical Requirements**:

1. **Kids AND Chores must be loaded FIRST** - Schema requires both `kids_dict` and `chores_dict`
2. **Name→UUID Conversion** - Same pattern as achievements for kid names
3. **Chore Reference Support** (Advanced):
   - If challenge type is "specific_chore", may need to convert chore name to UUID
   - Example: "Feed Cats Champion" → references "Feed the cåts" chore
   - Pattern: `chore_ids[chore_name]` lookup in setup

---

## Complex Entities (Pattern 3: Conditional Fields)

### Badges

**Schema Function**: `build_badge_common_schema(badge_type, ...)` (line ~1000)
**Data Builder**: `build_badge_common_data(user_input, internal_id, badge_type)` (line 1053)
**Badge Types**: `cumulative`, `daily`, `periodic`, `special_occasion`

**Common Fields (All Badge Types)**:

| YAML Key      | CFOF Constant                   | DATA Constant            | Type | Required | Default            |
| ------------- | ------------------------------- | ------------------------ | ---- | -------- | ------------------ |
| `name`        | `CFOF_BADGES_INPUT_NAME`        | `DATA_BADGE_NAME`        | str  | ✅       | SENTINEL_EMPTY     |
| `description` | `CFOF_BADGES_INPUT_DESCRIPTION` | `DATA_BADGE_DESCRIPTION` | str  | ❌       | SENTINEL_EMPTY     |
| `icon`        | `CFOF_BADGES_INPUT_ICON`        | `DATA_BADGE_ICON`        | str  | ❌       | DEFAULT_BADGE_ICON |
| `labels`      | `CFOF_BADGES_INPUT_LABELS`      | (stored separately)      | list | ❌       | []                 |
| `badge_type`  | (determines available fields)   | (internal logic)         | str  | ✅       | "cumulative"       |

**Type-Specific Fields**:

#### Cumulative Badge Fields

| YAML Key                 | CFOF Constant                              | Included When           | Required | Default                                      |
| ------------------------ | ------------------------------------------ | ----------------------- | -------- | -------------------------------------------- |
| `assigned_to`            | `CFOF_BADGES_INPUT_ASSIGNED_TO`            | badge_type="cumulative" | ✅       | []                                           |
| `target_type`            | `CFOF_BADGES_INPUT_TARGET_TYPE`            | include_target=True     | ✅       | DEFAULT_BADGE_TARGET_TYPE                    |
| `target_threshold_value` | `CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE` | include_target=True     | ✅       | DEFAULT_BADGE_TARGET_THRESHOLD_VALUE (100.0) |
| `maintenance_rules`      | `CFOF_BADGES_INPUT_MAINTENANCE_RULES`      | include_target=True     | ❌       | DEFAULT_BADGE_MAINTENANCE_THRESHOLD          |

**Conditional Field Inclusion Logic** (line 1060-1067):

```python
include_target = badge_type in ["cumulative", "daily", "periodic"]
include_special_occasion = badge_type in ["special_occasion"]
include_achievement_linked = badge_type in ["achievement_linked"]
include_challenge_linked = badge_type in ["challenge_linked"]
include_tracked_chores = badge_type in ["tracked_chores_badge"]
include_assigned_to = badge_type in ["cumulative", "daily"]
include_awards = badge_type in ["cumulative", "daily", "periodic"]
include_reset_schedule = badge_type in ["periodic"]
```

**YAML Example (Cumulative Badge - MVP)**:

```yaml
badges:
  - name: "Chore Stär"
    description: "Earn 100 points this month"
    badge_type: "cumulative"
    assigned_to: ["Zoë"] # Kid NAMES (converted to UUIDs)
    target_type: "points"
    target_threshold_value: 100.0
    icon: "mdi:star-circle-outline"
    labels: ["progress", "achievement"]
```

**Validation Rules**:

- Name cannot be empty
- Name must be unique across all badges
- badge_type must be valid badge type
- assigned_to list cannot be empty (for cumulative/daily badges)
- target_threshold_value must be > 0 (for badges with targets)

**MVP Scope Decision**:

- **Phase 1**: Implement cumulative badges ONLY (simplest type)
- **Future Phases**: Add daily, periodic, special_occasion incrementally
- **Reason**: Badge complexity = 4 types × 15+ fields = 60+ test cases

**Critical Requirements**:

1. **Badge Type Determines Fields** - Different types have different required/optional fields
2. **Assigned To Uses Kid Names** - Must convert to UUIDs like achievements
3. **Awards Deferred** - Badge awards (bonus/reward/penalty) not in MVP scope
4. **Reset Schedules Deferred** - Periodic badge reset schedules not in MVP scope

---

## Config Flow Step Sequences

Based on existing patterns in config_flow.py and flow_helpers.py:

### Expected Step Pattern (All Entity Types)

```
User Flow → ENTITY_COUNT step → ENTITY step (loop) → ENTITY_MENU step
                    ↓                   ↓                    ↓
            How many entities?    Configure entity 1    Add another? Yes/No
                                  Configure entity 2
                                  Configure entity N
```

### Specific Step IDs (To Verify in Implementation)

| Entity Type | COUNT Step ID       | ITEM Step ID  | MENU Step ID        |
| ----------- | ------------------- | ------------- | ------------------- |
| Reward      | `REWARD_COUNT`      | `REWARD`      | `REWARDS_MENU`      |
| Penalty     | `PENALTY_COUNT`     | `PENALTY`     | `PENALTIES_MENU`    |
| Bonus       | `BONUS_COUNT`       | `BONUS`       | `BONUSES_MENU`      |
| Badge       | `BADGE_COUNT`       | `BADGE`       | `BADGES_MENU`       |
| Achievement | `ACHIEVEMENT_COUNT` | `ACHIEVEMENT` | `ACHIEVEMENTS_MENU` |
| Challenge   | `CHALLENGE_COUNT`   | `CHALLENGE`   | `CHALLENGES_MENU`   |

**Note**: Actual step IDs must be verified in config_flow.py implementation. Pattern derived from existing KID_COUNT/KIDS/KIDS_MENU pattern.

---

## Name Resolution Requirements

### Entities Requiring Name→UUID Conversion

| Entity Type | Field Requiring Conversion | Source Dict | Notes                                      |
| ----------- | -------------------------- | ----------- | ------------------------------------------ |
| Badge       | `assigned_to`              | `kid_ids`   | List of kid names → list of kid UUIDs      |
| Achievement | `assigned_kids`            | `kid_ids`   | List of kid names → list of kid UUIDs      |
| Challenge   | `assigned_kids`            | `kid_ids`   | List of kid names → list of kid UUIDs      |
| Challenge   | (optional chore reference) | `chore_ids` | Chore name → chore UUID (advanced feature) |

### Conversion Function Pattern

```python
def _resolve_kid_names_to_uuids(
    kid_names: list[str],
    kid_ids: dict[str, str]
) -> list[str]:
    """Convert kid names from YAML to UUIDs for config flow.

    Args:
        kid_names: List of kid names from YAML (e.g., ["Zoë", "Max!"])
        kid_ids: Mapping of kid name → UUID from SetupResult

    Returns:
        List of kid UUIDs

    Raises:
        ValueError: If kid name not found in kid_ids mapping
    """
    try:
        return [kid_ids[name] for name in kid_names]
    except KeyError as err:
        available = ", ".join(kid_ids.keys())
        raise ValueError(
            f"Kid '{err.args[0]}' not found. Available kids: {available}"
        ) from err
```

**Usage in setup_from_yaml()**:

```python
# In achievement configuration step
achievement_data = scenario_yaml["achievements"][0]
kid_names = achievement_data.get("assigned_kids", [])
kid_uuids = _resolve_kid_names_to_uuids(kid_names, setup_result.kid_ids)

user_input = {
    const.CFOF_ACHIEVEMENTS_INPUT_NAME: achievement_data["name"],
    const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_KIDS: kid_uuids,  # UUIDs not names
    # ...other fields...
}
```

---

## Default Value Reference

Constants from `custom_components/kidschores/const.py`:

```python
# Rewards
DEFAULT_REWARD_COST: Final = 10.0

# Penalties
DEFAULT_PENALTY_POINTS: Final = 5.0
DEFAULT_PENALTY_ICON: Final = "mdi:alert-circle"

# Bonuses
DEFAULT_BONUS_POINTS: Final = 10.0
DEFAULT_BONUS_ICON: Final = "mdi:star-circle"

# Badges
DEFAULT_BADGE_ICON: Final = "mdi:shield-star"
DEFAULT_BADGE_TARGET_TYPE: Final = "points"
DEFAULT_BADGE_TARGET_THRESHOLD_VALUE: Final = 100.0
DEFAULT_BADGE_MAINTENANCE_THRESHOLD: Final = "maintain_70"

# Achievements
# (no specific defaults, inherits SENTINEL_EMPTY for most fields)

# Challenges
DEFAULT_CHALLENGE_TYPE: Final = "chore_count"
```

---

## Validation Error Translation Keys

When validation fails, use these translation keys:

| Entity Type | Error Scenario      | Translation Key                           |
| ----------- | ------------------- | ----------------------------------------- |
| Reward      | Name empty          | `TRANS_KEY_CFOF_INVALID_REWARD_NAME`      |
| Reward      | Name duplicate      | `TRANS_KEY_CFOF_DUPLICATE_REWARD`         |
| Penalty     | Name empty          | `TRANS_KEY_CFOF_INVALID_PENALTY_NAME`     |
| Penalty     | Name duplicate      | `TRANS_KEY_CFOF_DUPLICATE_PENALTY`        |
| Bonus       | Name empty          | `TRANS_KEY_CFOF_INVALID_BONUS_NAME`       |
| Bonus       | Name duplicate      | `TRANS_KEY_CFOF_DUPLICATE_BONUS`          |
| Badge       | Name empty          | `TRANS_KEY_CFOF_INVALID_BADGE_NAME`       |
| Badge       | Name duplicate      | `TRANS_KEY_CFOF_DUPLICATE_BADGE`          |
| Achievement | Name empty          | `TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_NAME` |
| Achievement | assigned_kids empty | `TRANS_KEY_CFOF_NO_KIDS_SELECTED`         |
| Challenge   | Name empty          | `TRANS_KEY_CFOF_INVALID_CHALLENGE_NAME`   |
| Challenge   | assigned_kids empty | `TRANS_KEY_CFOF_NO_KIDS_SELECTED`         |

---

## Summary: Implementation Priorities

### Phase 2.1: Implement First (Simple)

1. **Rewards** - 5 fields, simple validation
2. **Penalties** - 5 fields, points sign conversion
3. **Bonuses** - 5 fields, similar to rewards

### Phase 2.2: Implement Second (Medium)

4. **Achievements** - 6 fields, requires kid name resolution
5. **Challenges** - 8 fields, requires kid name resolution

### Phase 2.3: Implement Third (Complex)

6. **Badges (Cumulative Only)** - ~10 fields, conditional inclusion, kid name resolution

### Deferred to Future

- Daily badges (different reset logic)
- Periodic badges (custom schedules)
- Special occasion badges (date-based)
- Badge awards (bonus/reward/penalty integration)
- Challenge chore-specific criteria (chore name resolution)

---

**End of Mapping Reference Document**
