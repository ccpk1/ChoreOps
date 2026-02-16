# CREATE & UPDATE REWARD SERVICES - Implementation Plan

**Initiative name**: Create & Update Reward Services
**Target release**: v0.5.1
**Owner**: AI Agent
**Status**: ✅ COMPLETED
**Created**: January 18, 2026
**Last Updated**: January 21, 2026
**Completed**: January 21, 2026

---

## Summary Table

| Phase       | Description                  | % Complete  | Quick Notes                                                |
| ----------- | ---------------------------- | ----------- | ---------------------------------------------------------- |
| **Phase 1** | Shared Infrastructure        | 100% ✅     | ~50 lines: schema + mapping helpers (simpler than chores)  |
| **Phase 2** | Create Reward Service        | 100% ✅     | ~40 lines: handler reuses `build_rewards_data()`           |
| **Phase 3** | Update Reward Service        | 100% ✅     | ~40 lines: merge + validate logic (reuses Phase 1)         |
| **Phase 4** | Documentation & Translations | 100% ✅     | services.yaml entries (reuses existing error translations) |
| **Phase 5** | Testing                      | 100% ✅     | Test both services + shared infrastructure                 |
| **BONUS**   | **Delete Reward Service**    | **100% ✅** | **Implemented beyond original scope**                      |

**Estimated Total Effort**: ~170 lines of new code (vs ~500 if writing fresh validation for both)

**ACTUAL DELIVERED**: ~250 lines including bonus delete_reward service + 23 passing tests

---

## Summary Items

1. **Key objective**: Create two Home Assistant services - `kidschores.create_reward` and `kidschores.update_reward` - that allow programmatic reward management by **reusing the existing `build_rewards_data()` validation** from flow_helpers.py. Both services share the same validation infrastructure, providing 100% parity with the Options Flow. Simpler than chores (no recurring schedules, no due dates, no completion criteria).

2. **Summary of recent work**:
   - ✅ Feasibility confirmed - `build_reward_schema()` and `build_rewards_data()` exist
   - ✅ Reward schema has only 5 fields (vs 21 for chores) - much simpler!
   - ✅ Validation via `validate_rewards_inputs()` (name required, duplicate check)
   - ✅ Existing error translations (`TRANS_KEY_CFOF_INVALID_REWARD_NAME`, `TRANS_KEY_CFOF_DUPLICATE_REWARD`)
   - ✅ Implementation approach: Map service input → `CFOF_*` keys → call `build_rewards_data()`

3. **Next steps (short term)**:
   - Phase 1: Define shared schema with user-friendly field names (~20 lines)
   - Phase 1: Implement `_map_reward_input_to_form()` helper (~15 lines)
   - Phase 2: Implement `handle_create_reward()` handler (~40 lines)
   - Phase 3: Implement `handle_update_reward()` handler (~40 lines)
   - Phase 4: Add both services to services.yaml

4. **Risks / blockers**:
   - **LOW RISK**: Validation is simpler than chores (fewer fields, no complex business rules)
   - Need to verify `coordinator._create_reward()` method exists (likely parallel to `_create_chore()`)
   - Error translation: `validate_rewards_inputs()` returns `TRANS_KEY_CFOF_*` keys - already in en.json ✅

5. **References**:
   - [flow_helpers.py](../../custom_components/kidschores/flow_helpers.py):
     - `build_reward_schema()` (line 2648) - UI schema builder
     - `build_rewards_data()` (line 2688) - **Data transformation (REUSE THIS)**
     - `validate_rewards_inputs()` (line 2725) - **Validation logic (REUSE THIS)**
   - [options_flow.py](../../custom_components/kidschores/options_flow.py):
     - `async_step_add_reward()` - Example of calling `build_rewards_data()`
   - [coordinator.py](../../custom_components/kidschores/coordinator.py) - Reward management methods
   - [const.py](../../custom_components/kidschores/const.py) - All CFOF*REWARDS_INPUT*_ and DATA*REWARD*_ constants

6. **Decisions & completion check**:
   - [x] Decision: Reuse `build_rewards_data()` and `validate_rewards_inputs()` for validation
   - [x] Decision: Keep create and update as separate services (HA best practices)
   - [x] Decision: Share mapping helper between both services
   - [x] Decision: Update service supports partial field updates
   - [x] Decision: Simpler than chores - no kid assignment, no scheduling complexity
   - [x] **Completion: All phases complete, tests passing (23/23) ✅**
   - [x] **Bonus: Delete reward service implemented and tested ✅**
   - [x] **Translation fix: Corrected array examples causing test pollution ✅**

7. **Learnings (for chore services):**
   - **Field Name Pattern**: Use simple names (`name`, `cost`, `description`) not entity-prefixed names (`reward_name`, `reward_cost`) in service schemas and services.yaml
   - **Storage vs API Layer**: Storage can use entity-specific keys (`reward_labels`, `chore_labels`) to avoid conflicts, but the public API should use simple names
   - **Testing Pattern**: Dashboard helper retrieval requires: (1) Get kid's dashboard helper sensor, (2) Find entity in helper's list by name, (3) Extract `eid` from that list item, (4) Use eid to access specific entity sensor for detailed validation
   - **Test Assertion Pattern**: Service response uses API field names (`id`, `name`), storage checks use entity-specific keys (`reward_labels`), coordinator methods use DATA\_\* constants
   - **Translation Location**: Add service translations to `translations/en.json` under `services.{service_name}` section with `name`, `description`, and `fields.{field_name}` structure

---

## Feasibility Analysis: Reusing Reward Validation

### What `build_rewards_data()` Already Does (lines 2688-2723)

| Responsibility                    | Complexity | Benefit of Reuse          |
| --------------------------------- | ---------- | ------------------------- |
| Transform CFOF*\* → DATA*\* keys  | Low        | ✅ Already handles        |
| Generate internal_id (UUID)       | Low        | ✅ Already handles        |
| Apply default values              | Low        | ✅ Consistent defaults    |
| Build reward data dict (5 fields) | Low        | ✅ Single source of truth |

### What `validate_rewards_inputs()` Already Does (lines 2725-2758)

| Responsibility          | Complexity | Benefit of Reuse         |
| ----------------------- | ---------- | ------------------------ |
| Validate name not empty | Low        | ✅ Already handles       |
| Check duplicate name    | Medium     | ✅ Already handles       |
| Return translation keys | Low        | ✅ Existing translations |

### Comparison: Reuse vs Fresh Implementation

| Factor                      | Reuse validation                 | Write Fresh in services.py     |
| --------------------------- | -------------------------------- | ------------------------------ |
| **Lines of code**           | ~50 (mapping only)               | ~150 (full validation)         |
| **Validation completeness** | 100% (inherits all)              | Risk of missing edge cases     |
| **Future maintenance**      | Single source of truth           | Dual maintenance burden        |
| **Translation reuse**       | Uses existing `TRANS_KEY_CFOF_*` | Need new `TRANS_KEY_SVC_*`     |
| **Testing effort**          | Test mapping layer only          | Must test all validation again |

### Verdict: **Reuse Is Worth It** ✅

The **only work needed** is a simple field-name mapping (~10 lines):

```python
SERVICE_TO_FORM_MAPPING = {
    "name": const.CFOF_REWARDS_INPUT_NAME,
    "cost": const.CFOF_REWARDS_INPUT_COST,
    "description": const.CFOF_REWARDS_INPUT_DESCRIPTION,
    "icon": const.CFOF_REWARDS_INPUT_ICON,
    "labels": const.CFOF_REWARDS_INPUT_LABELS,
}
```

All validation and data transformation is inherited automatically.

---

## Architecture: Reusing Existing Validation

### Current Options Flow Pattern (options_flow.py)

```python
# 1. Build and validate reward data
reward_data = fh.build_rewards_data(user_input)
errors = fh.validate_rewards_inputs(user_input, existing_rewards)

# 2. If errors, show form again
if errors:
    return self.async_show_form(..., errors=errors)

# 3. Extract internal_id and data
internal_id = list(reward_data.keys())[0]
new_reward_data = reward_data[internal_id]

# 4. Add to coordinator and persist
coordinator.rewards_data[internal_id] = new_reward_data
coordinator._persist()
coordinator.async_update_listeners()
```

### Service Implementation Pattern (proposed)

```python
async def handle_create_reward(call: ServiceCall) -> ServiceResponse:
    """Handle create_reward service call."""
    coordinator = _get_coordinator(call.hass)

    # Map service input to form input (CFOF_* keys)
    form_input = _map_reward_input_to_form(call.data)

    # Validate
    errors = fh.validate_rewards_inputs(form_input, coordinator.rewards_data)
    if errors:
        raise ServiceValidationError(...)

    # Build reward data
    reward_data = fh.build_rewards_data(form_input)
    internal_id = list(reward_data.keys())[0]

    # Create in coordinator
    coordinator.rewards_data[internal_id] = reward_data[internal_id]
    coordinator._persist()
    coordinator.async_update_listeners()

    return {"reward_id": internal_id}
```

---

## Reward Data Structure Reference

### From build_reward_schema() (flow_helpers.py line 2648-2686)

The reward schema uses these form field constants (CFOF*REWARDS_INPUT*\*):

### All Fields (5 total - much simpler than chores!)

| Form Field Constant              | Service Field | Default             | Type         | Required | Validation        |
| -------------------------------- | ------------- | ------------------- | ------------ | -------- | ----------------- |
| `CFOF_REWARDS_INPUT_NAME`        | `name`        | -                   | string       | ✅ Yes   | Non-empty, unique |
| `CFOF_REWARDS_INPUT_COST`        | `cost`        | DEFAULT_REWARD_COST | number       | ✅ Yes   | >= 0              |
| `CFOF_REWARDS_INPUT_DESCRIPTION` | `description` | ""                  | string       | No       | -                 |
| `CFOF_REWARDS_INPUT_ICON`        | `icon`        | DEFAULT_REWARD_ICON | icon         | No       | mdi:\*            |
| `CFOF_REWARDS_INPUT_LABELS`      | `labels`      | []                  | list[string] | No       | HA labels         |

### Validation Rules (from validate_rewards_inputs())

1. **Name required**: Empty name → `TRANS_KEY_CFOF_INVALID_REWARD_NAME`
2. **Name unique**: Duplicate → `TRANS_KEY_CFOF_DUPLICATE_REWARD`

### Key Differences from Chores

- **No kid assignment** - Rewards available to all kids
- **No recurring schedules** - Rewards are one-time claims
- **No due dates** - No time constraints on rewards
- **No completion criteria** - No independent/shared distinction
- **Simpler validation** - Only name uniqueness check

---

## Detailed Phase Tracking

---

### Phase 1 – Shared Infrastructure (0%)

**Goal**: Define shared schema and mapping helpers that both create_reward and update_reward will use.

**Steps / detailed work items**:

1. - [ ] Add service name constants to [const.py](../../custom_components/kidschores/const.py)

   ```python
   SERVICE_CREATE_REWARD: Final = "create_reward"
   SERVICE_UPDATE_REWARD: Final = "update_reward"
   ```

2. - [ ] Define SERVICE_CREATE_REWARD_SCHEMA in [services.py](../../custom_components/kidschores/services.py)

   ```python
   SERVICE_CREATE_REWARD_SCHEMA = vol.Schema({
       vol.Required("name"): cv.string,
       vol.Required("cost"): vol.All(vol.Coerce(float), vol.Range(min=0)),
       vol.Optional("description"): cv.string,
       vol.Optional("icon"): cv.icon,
       vol.Optional("labels"): vol.All(cv.ensure_list, [cv.string]),
   })
   ```

3. - [ ] Create shared input mapping helper function in services.py:

   ```python
   def _map_reward_input_to_form(service_input: dict[str, Any]) -> dict[str, Any]:
       """Map service input (user-friendly) to form input (CFOF_* keys).

       Used by both create_reward and update_reward services.
       """
       SERVICE_TO_FORM_MAPPING = {
           "name": const.CFOF_REWARDS_INPUT_NAME,
           "cost": const.CFOF_REWARDS_INPUT_COST,
           "description": const.CFOF_REWARDS_INPUT_DESCRIPTION,
           "icon": const.CFOF_REWARDS_INPUT_ICON,
           "labels": const.CFOF_REWARDS_INPUT_LABELS,
       }

       form_input = {}
       for service_key, form_key in SERVICE_TO_FORM_MAPPING.items():
           if service_key in service_input:
               form_input[form_key] = service_input[service_key]

       return form_input
   ```

**Key issues**:

- Simpler than chores - only 5 fields to map
- No kid assignment validation needed
- Helper is reused by both create and update services

---

### Phase 2 – Create Reward Service (0%)

**Goal**: Implement create_reward service handler that reuses validation.

**Steps / detailed work items**:

1. - [ ] Implement `handle_create_reward()` in [services.py](../../custom_components/kidschores/services.py)

   ```python
   async def handle_create_reward(call: ServiceCall) -> ServiceResponse:
       """Handle create_reward service call."""
       hass = call.hass
       coordinator = _get_coordinator(hass)

       # Map service input to form input (CFOF_* keys)
       form_input = _map_reward_input_to_form(call.data)

       # Validate inputs
       errors = fh.validate_rewards_inputs(form_input, coordinator.rewards_data)

       # Handle validation errors
       if errors:
           error_key = list(errors.values())[0]  # Get first error
           error_msg = coordinator.hass.localize(f"component.kidschores.config.error.{error_key}")
           raise ServiceValidationError(error_msg or error_key)

       # Build reward data (includes UUID generation)
       reward_data = fh.build_rewards_data(form_input)

       # Extract internal_id and data
       internal_id = list(reward_data.keys())[0]
       new_reward_data = reward_data[internal_id]

       # Create reward in coordinator
       coordinator.rewards_data[internal_id] = new_reward_data
       coordinator._persist()
       coordinator.async_update_listeners()

       return {"reward_id": internal_id}
   ```

2. - [ ] Register service in `async_setup_services()`:

   ```python
   hass.services.async_register(
       DOMAIN,
       const.SERVICE_CREATE_REWARD,
       handle_create_reward,
       schema=SERVICE_CREATE_REWARD_SCHEMA,
       supports_response=SupportsResponse.ONLY,
   )
   ```

3. - [ ] Add unregister in `async_unload_services()`:
   ```python
   hass.services.async_remove(DOMAIN, const.SERVICE_CREATE_REWARD)
   ```

**Key issues**:

- Simpler than chores - no kid lookup logic needed
- Error handling reuses existing translations
- Service returns reward_id for use in automations

---

### Phase 3 – Update Reward Service (0%)

**Goal**: Implement update_reward service that supports partial field updates while reusing validation.

**Steps / detailed work items**:

1. - [ ] Add UPDATE_REWARD schema constant to [services.py](../../custom_components/kidschores/services.py)

   ```python
   SERVICE_UPDATE_REWARD_SCHEMA = vol.Schema({
       vol.Required("reward_id"): cv.string,
       # All other fields optional for partial updates
       vol.Optional("name"): cv.string,
       vol.Optional("cost"): vol.All(vol.Coerce(float), vol.Range(min=0)),
       vol.Optional("description"): cv.string,
       vol.Optional("icon"): cv.icon,
       vol.Optional("labels"): vol.All(cv.ensure_list, [cv.string]),
   })
   ```

2. - [ ] Implement `handle_update_reward()` in [services.py](../../custom_components/kidschores/services.py)

   ```python
   async def handle_update_reward(call: ServiceCall) -> ServiceResponse:
       """Handle update_reward service call."""
       hass = call.hass
       coordinator = _get_coordinator(hass)

       reward_id = call.data["reward_id"]

       # Verify reward exists
       if reward_id not in coordinator.rewards_data:
           raise ServiceValidationError(
               f"Reward with ID '{reward_id}' not found"
           )

       # Get existing reward data
       existing_reward = coordinator.rewards_data[reward_id]

       # Build merged input (existing + updates)
       merged_input = {
           "name": existing_reward.get(const.DATA_REWARD_NAME),
           "cost": existing_reward.get(const.DATA_REWARD_COST),
           "description": existing_reward.get(const.DATA_REWARD_DESCRIPTION, ""),
           "icon": existing_reward.get(const.DATA_REWARD_ICON),
           "labels": existing_reward.get(const.DATA_REWARD_LABELS, []),
       }

       # Overlay with service updates (only fields provided)
       for key, value in call.data.items():
           if key != "reward_id":
               merged_input[key] = value

       # Map to form input and validate
       form_input = _map_reward_input_to_form(merged_input)

       # Exclude current reward from duplicate check
       other_rewards = {
           rid: data
           for rid, data in coordinator.rewards_data.items()
           if rid != reward_id
       }

       # Validate merged data
       errors = fh.validate_rewards_inputs(form_input, other_rewards)

       if errors:
           error_key = list(errors.values())[0]
           error_msg = coordinator.hass.localize(f"component.kidschores.config.error.{error_key}")
           raise ServiceValidationError(error_msg or error_key)

       # Build validated data
       reward_data = fh.build_rewards_data(form_input)
       validated_data = reward_data[list(reward_data.keys())[0]]

       # Update reward in coordinator
       coordinator.rewards_data[reward_id].update(validated_data)
       coordinator._persist()
       coordinator.async_update_listeners()

       return {"reward_id": reward_id, "updated": True}
   ```

3. - [ ] Register update service in `async_setup_services()`:

   ```python
   hass.services.async_register(
       DOMAIN,
       const.SERVICE_UPDATE_REWARD,
       handle_update_reward,
       schema=SERVICE_UPDATE_REWARD_SCHEMA,
       supports_response=SupportsResponse.ONLY,
   )
   ```

4. - [ ] Add unregister in `async_unload_services()`:
   ```python
   hass.services.async_remove(DOMAIN, const.SERVICE_UPDATE_REWARD)
   ```

**Key issues**:

- Must merge existing data with updates to support partial field changes
- Exclude current reward from duplicate name check
- Reuses same validation as create and Options Flow
- Simpler than chores - no kid assignment conversion needed

---

### Phase 4 – Documentation & Translations (0%)

**Goal**: Document the services and ensure translations exist.

**Steps / detailed work items**:

1. - [ ] Add create_reward service definition to [services.yaml](../../custom_components/kidschores/services.yaml)

   ```yaml
   create_reward:
     name: Create reward
     description: Create a new reward programmatically
     fields:
       name:
         name: Reward name
         description: Name of the reward
         required: true
         example: "Extra Screen Time"
         selector:
           text:
       cost:
         name: Cost
         description: Points required to claim the reward
         required: true
         default: 10
         example: 10
         selector:
           number:
             min: 0
             max: 1000
             step: 0.1
             mode: box
       description:
         name: Description
         description: Optional description of the reward
         required: false
         example: "30 minutes of extra tablet time"
         selector:
           text:
             multiline: true
       icon:
         name: Icon
         description: Icon to represent the reward
         required: false
         default: "mdi:gift"
         selector:
           icon:
       labels:
         name: Labels
         description: Labels for grouping rewards
         required: false
         example: ["weekend", "special"]
         selector:
           select:
             options: []
             multiple: true
             custom_value: true
   ```

2. - [ ] Add update_reward service definition to [services.yaml](../../custom_components/kidschores/services.yaml)

   ```yaml
   update_reward:
     name: Update reward
     description: Update an existing reward (partial updates supported)
     fields:
       reward_id:
         name: Reward ID
         description: Internal ID of the reward to update
         required: true
         example: "abc123-def456-789..."
         selector:
           text:
       name:
         name: Reward name
         description: New name for the reward
         required: false
         example: "Extra Screen Time (Updated)"
         selector:
           text:
       cost:
         name: Cost
         description: Updated cost value
         required: false
         example: 15
         selector:
           number:
             min: 0
             max: 1000
             step: 0.1
             mode: box
       description:
         name: Description
         description: Updated description
         required: false
         selector:
           text:
             multiline: true
       icon:
         name: Icon
         description: Updated icon
         required: false
         selector:
           icon:
       labels:
         name: Labels
         description: Updated labels
         required: false
         selector:
           select:
             options: []
             multiple: true
             custom_value: true
   ```

3. - [ ] Add translations to [en.json](../../custom_components/kidschores/translations/en.json)
   - Add `create_reward` entry under `services` section
   - Add `update_reward` entry under `services` section
   - Verify error translation keys exist (should already exist from Options Flow)

4. - [ ] Verify these error translation keys exist in en.json:
   - `TRANS_KEY_CFOF_INVALID_REWARD_NAME` - "Reward name is required"
   - `TRANS_KEY_CFOF_DUPLICATE_REWARD` - "A reward with this name already exists"

**Key issues**:

- services.yaml selectors should be user-friendly
- Error messages from validation already have translations ✅
- Both services share error translations (no duplication needed)

---

### Phase 5 – Testing (0%)

**Goal**: Comprehensive tests covering both create and update service functionality.

**Steps / detailed work items**:

1. - [ ] Create test file: [tests/test_service_reward_management.py](../../tests/test_service_reward_management.py)

2. - [ ] Test create_reward minimal (happy path):

   ```python
   async def test_create_reward_minimal(hass, coordinator):
       """Test minimal reward creation."""
       result = await hass.services.async_call(
           DOMAIN,
           "create_reward",
           {"name": "Test Reward", "cost": 10},
           blocking=True,
           return_response=True,
       )
       assert "reward_id" in result
       assert result["reward_id"] in coordinator.rewards_data
       assert coordinator.rewards_data[result["reward_id"]][const.DATA_REWARD_COST] == 10
   ```

3. - [ ] Test create_reward validation errors:
   - [ ] `test_create_reward_empty_name` - Expect ServiceValidationError
   - [ ] `test_create_reward_duplicate_name` - Expect ServiceValidationError
   - [ ] `test_create_reward_negative_cost` - Expect schema validation error

4. - [ ] Test create_reward full (all optional fields)

5. - [ ] Test update_reward partial update (happy path):

   ```python
   async def test_update_reward_partial(hass, coordinator):
       """Test partial reward update."""
       # Create a reward first
       create_result = await hass.services.async_call(
           DOMAIN, "create_reward",
           {"name": "Original", "cost": 10},
           blocking=True, return_response=True,
       )
       reward_id = create_result["reward_id"]

       # Update only cost
       update_result = await hass.services.async_call(
           DOMAIN, "update_reward",
           {"reward_id": reward_id, "cost": 20},
           blocking=True, return_response=True,
       )

       assert update_result["updated"] is True
       assert coordinator.rewards_data[reward_id][const.DATA_REWARD_COST] == 20
       assert coordinator.rewards_data[reward_id][const.DATA_REWARD_NAME] == "Original"  # Unchanged
   ```

6. - [ ] Test update_reward validation errors:
   - [ ] `test_update_reward_not_found` - Invalid reward_id
   - [ ] `test_update_reward_duplicate_name` - Name conflicts with another reward
   - [ ] `test_update_reward_empty_name` - Cleared name should fail

7. - [ ] Test update_reward full (all fields changed)

8. - [ ] Test service responses return correct data

**Key issues**:

- Use existing test fixtures from conftest.py
- Tests should verify cost values, names, descriptions
- Simpler than chores - no kid assignment complexity
- Verify partial updates don't affect unchanged fields

---

## Testing & Validation

**Test Coverage Target**: 95%+ for new service code

**Test Commands**:

```bash
# Run reward management service tests
python -m pytest tests/test_service_reward_management.py -v

# Run full suite
python -m pytest tests/ -v --tb=line

# Lint check
./utils/quick_lint.sh --fix
```

**Validation Checklist**:

- [ ] All tests pass for both services
- [ ] Lint passes
- [ ] Both services appear in Developer Tools
- [ ] Create minimal works (name + cost)
- [ ] Update partial works (only specified fields change)
- [ ] All validation errors handled with clear messages
- [ ] Duplicate name detection works for both services

---

## Usage Examples

### Create Reward - Minimal

```yaml
service: kidschores.create_reward
data:
  name: "Extra Screen Time"
  cost: 10
```

Creates a reward with defaults:

- Default icon (mdi:gift)
- No description
- No labels

### Create Reward - Full

```yaml
service: kidschores.create_reward
data:
  name: "Movie Night"
  cost: 25
  description: "Watch a movie of your choice with family"
  icon: "mdi:movie"
  labels:
    - "weekend"
    - "special"
```

### Create Reward - Seasonal

```yaml
service: kidschores.create_reward
data:
  name: "Summer Ice Cream Trip"
  cost: 15
  description: "Ice cream outing to favorite shop"
  icon: "mdi:ice-cream"
  labels:
    - "summer"
    - "seasonal"
```

### Update Reward - Change Cost

```yaml
service: kidschores.update_reward
data:
  reward_id: "abc123-def456-789..."
  cost: 20
```

### Update Reward - Add Description

```yaml
service: kidschores.update_reward
data:
  reward_id: "abc123-def456-789..."
  description: "Updated description with more details"
```

### Update Reward - Change Icon & Labels

```yaml
service: kidschores.update_reward
data:
  reward_id: "abc123-def456-789..."
  icon: "mdi:star"
  labels:
    - "premium"
    - "special"
```

---

## Integration with Cost Override Feature

These services complement the `approve_reward(cost_override)` feature from the REWARD_COST_OVERRIDE plan:

**Workflow Example**:

```yaml
# 1. Create base reward template
- service: kidschores.create_reward
  data:
    name: "Extra Screen Time"
    cost: 10 # Base weekday cost
  response_variable: reward_create

# 2. Kid redeems at base cost
# (uses standard redeem_reward service)

# 3. Parent approves with dynamic cost
- service: kidschores.approve_reward
  data:
    parent_name: "Mom"
    kid_name: "Alice"
    reward_name: "Extra Screen Time"
    cost_override: 5 # Weekend discount
```

**Alternative - Season-based pricing**:

```yaml
# Update reward cost seasonally
- service: kidschores.update_reward
  data:
    reward_id: "{{ reward_id }}"
    cost: 8 # Summer pricing
```

---

## Key Differences from Options Flow

| Aspect             | Options Flow                | Create Service                  | Update Service                                   |
| ------------------ | --------------------------- | ------------------------------- | ------------------------------------------------ |
| Input keys         | `CFOF_REWARDS_INPUT_*`      | User-friendly names             | User-friendly names                              |
| Validation         | `validate_rewards_inputs()` | Same (via mapping)              | Same (via mapping)                               |
| Data building      | `build_rewards_data()`      | Same (via mapping)              | Same (via mapping)                               |
| Persistence        | Direct dict assignment      | Same                            | `.update()` method                               |
| Response           | Shows updated form          | Returns `{"reward_id": "uuid"}` | Returns `{"reward_id": "uuid", "updated": true}` |
| Field requirements | All fields shown            | Only provided fields            | Only provided fields (partial update)            |

---

## Key Differences from Chore Services

| Aspect                | Chore Services                     | Reward Services                |
| --------------------- | ---------------------------------- | ------------------------------ |
| Field count           | 21 fields                          | 5 fields (simpler!)            |
| Required fields       | 3 (name, points, assigned_kids)    | 2 (name, cost)                 |
| Kid assignment        | Required (list of names)           | N/A (rewards available to all) |
| Recurring schedules   | Yes (daily/weekly/etc)             | No                             |
| Due dates             | Yes (optional)                     | No                             |
| Completion criteria   | Yes (independent/shared)           | No                             |
| Validation complexity | High (dates, overdue/reset combos) | Low (name + uniqueness only)   |
| Lines of code         | ~200 lines                         | ~170 lines                     |

---

## Future Enhancements (Out of Scope)

- `kidschores.delete_reward` service for removing rewards
- `kidschores.bulk_create_rewards` for creating multiple rewards at once
- Reward visibility control (specific kids only)
- Reward expiration dates
- Reward quantity limits (claim X times max)

---

## Synergy with Other Features

**Complements existing v0.5.1 features**:

- **Cost Override**: Create templates, apply dynamic pricing at approval
- **Chore Services**: Complete programmatic API for all entity types
- **Badges**: Can award dynamically created rewards as badge prizes

**Automation possibilities**:

- Seasonal reward creation/deletion
- Dynamic cost adjustments based on behavior
- Event-triggered special rewards (birthdays, holidays)
- Integration with external systems (school reports, fitness trackers)

---

**Template Usage Notice**: _Created following KidsChores planning standards, modeled after CREATE_CHORE_SERVICE plan._
