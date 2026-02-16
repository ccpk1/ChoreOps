# Entity Helpers Implementation - Rewards First Approach

**Initiative name**: Entity Helpers Architecture (EHA-2026-001)
**Target release**: v0.5.0
**Owner**: TBD
**Status**: In Progress
**Created**: January 20, 2026
**Last Updated**: January 20, 2026

---

## Summary Table

| Phase       | Description                              | % Complete | Quick Notes                                                                        |
| ----------- | ---------------------------------------- | ---------- | ---------------------------------------------------------------------------------- |
| **Phase 1** | Infrastructure (exception + file)        | 100%       | ✅ EntityValidationError + file skeleton created                                   |
| **Phase 2** | Rewards in data_builders.py             | 100%       | ✅ Unified build_reward() function implemented                                     |
| **Phase 3** | Update flow_helpers.py (remove defaults) | 100%       | ✅ Delegates to data_builders, deprecation note added                             |
| **Phase 4** | Update options_flow.py (consume helpers) | 100%       | ✅ add_reward + edit_reward use data_builders                                     |
| **Phase 5** | Create/Update Reward Services            | 100%       | ✅ create_reward + update_reward services using data_builders                     |
| **Phase 6** | Testing & Validation                     | 50%        | ✅ Test analysis complete, service tests prioritized → see `_SUP_TEST_ANALYSIS.md` |

**Estimated Total Effort**: ~280 lines of new code, validates entire architecture pattern

---

## Summary Items

1. **Key objective**: Create `data_builders.py` as the **SINGLE SOURCE OF TRUTH** for entity field defaults and business validation, starting with Rewards as the simplest entity (6 fields). This establishes all architectural patterns before tackling complex entities like Chores (34 fields). **Key innovation: One `build_reward()` function handles both create and update** (unlike current chores pattern which has separate functions).

2. **Summary of recent work**:
   - ✅ Architectural design complete with 3-layer validation model
   - ✅ Double-defaults trap identified and mitigation planned
   - ✅ Field-specific error handling pattern designed (EntityValidationError)
   - ✅ Service exposure opportunity documented (bypasses flow_helpers)
   - ✅ Integration with CREATE_UPDATE_REWARD_SERVICES plan validated
   - ✅ **Consolidated build function**: One `build_reward(user_input, existing=None)` for both create/update

3. **Next steps (short term)**:
   - Phase 1: Create data_builders.py with EntityValidationError class
   - Phase 2: Implement unified `build_reward()` function (handles create AND update)
   - Phase 3: Keep flow*helpers defaults using `const.DEFAULT*\*` constants
   - Phase 4: Update options_flow.py to use data_builders

4. **Risks / blockers**:
   - **LOW RISK**: Rewards are simple (6 fields, no per-kid complexity)
   - **MITIGATED**: Double-defaults trap addressed by removing defaults from flow_helpers
   - **MITIGATED**: Error bubbling addressed with field-specific EntityValidationError
   - Error translations already exist: `TRANS_KEY_CFOF_INVALID_REWARD_NAME`, `TRANS_KEY_CFOF_DUPLICATE_REWARD`

5. **References**:
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and storage patterns
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Constant naming, datetime standards
   - [CREATE_UPDATE_REWARD_SERVICES_IN-PROCESS.md](./CREATE_UPDATE_REWARD_SERVICES_IN-PROCESS.md) - Service implementation plan
   - [flow_helpers.py](../../custom_components/kidschores/flow_helpers.py) lines 2648-2758 - Current reward validation
   - [coordinator.py](../../custom_components/kidschores/coordinator.py) lines 1778-1820 - Current \_create_reward/\_update_reward
   - [type_defs.py](../../custom_components/kidschores/type_defs.py) lines 86-95 - RewardData TypedDict

6. **Decisions & completion check**:
   - [x] Decision: Start with Rewards (simplest entity) to validate all patterns
   - [x] Decision: data_builders.py is a "helper" not "engine" (data structures, not calculations)
   - [x] Decision: Keep flow*helpers defaults using `const.DEFAULT*\*` for consistency
   - [x] Decision: EntityValidationError includes field for form highlighting
   - [x] Decision: Config flow unchanged (only system settings, no entity CRUD)
   - [x] Decision: **One function for create+update** - `build_reward(user_input, existing=None)`
   - [x] Decision: Services require `cost` field (no invisible defaults for automations)
   - [ ] Completion: All phases complete, tests passing, services working

---

## Architectural Foundation

### 3-Layer Validation Model (Preserved)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            VALIDATION LAYERS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: VOLUPTUOUS SCHEMA (options_flow.py)                              │
│  ─────────────────────────────────────────────                              │
│  • Type checking (str, int, float)                                         │
│  • Required vs optional fields                                             │
│  • Selector UI configuration                                               │
│  • Stays unchanged in options_flow.py                                      │
│                                                                             │
│  Layer 2: UI VALIDATION (flow_helpers.py)                                  │
│  ─────────────────────────────────────────                                  │
│  • Duplicate name checking                                                  │
│  • HA user ID validation                                                    │
│  • Returns: str | None (error translation key)                             │
│  • ❌ NO DEFAULTS (removed per trap fix)                                   │
│  • ❌ NO DATA TRANSFORMATION (validation only)                             │
│                                                                             │
│  Layer 3: BUSINESS LOGIC (data_builders.py) ← NEW                         │
│  ───────────────────────────────────────────────                            │
│  • Cross-field validation (date logic, format validation)                  │
│  • ✅ ALL DEFAULTS DEFINED HERE (single source of truth)                   │
│  • ✅ COMPLETE ENTITY BUILDING                                             │
│  • Raises: EntityValidationError(field, translation_key)                   │
│  • Returns: Complete TypedDict (RewardData, ChoreData, etc.)               │
│                                                                             │
│  Layer 4: STORAGE (coordinator.py)                                          │
│  ─────────────────────────────────                                          │
│  • Thin wrapper: stores dict, calls _persist()                             │
│  • No validation, no defaults, no transformation                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Double-Defaults Trap → Resolution

**Problem Identified**: Defaults in BOTH flow_helpers AND coordinator could drift out of sync.

**Resolution**: Use `const.DEFAULT_*` constants consistently everywhere:

| Where                           | Purpose                           | Pattern                                        |
| ------------------------------- | --------------------------------- | ---------------------------------------------- |
| `const.py`                      | Define default values             | `DEFAULT_REWARD_COST: Final = 10`              |
| `build_reward_schema()`         | Pre-populate form for user to SEE | Uses `const.DEFAULT_REWARD_COST`               |
| `data_builders.build_reward()` | Build complete structure          | Uses `const.DEFAULT_REWARD_COST`               |
| Services                        | Require critical fields           | `vol.Required("cost")` - no invisible defaults |

**The constant IS the single source of truth** - not where it's applied.

**Service Exception**: For automations, require critical fields (like `cost`) so users don't get invisible defaults they never saw in a UI.

### Field-Specific Error Handling

**EntityValidationError** enables form field highlighting:

```python
class EntityValidationError(Exception):
    """Validation error with field-specific information."""

    def __init__(
        self,
        field: str,           # CFOF_* constant (form field name)
        translation_key: str, # TRANS_KEY_* for error message
        placeholders: dict[str, str] | None = None,
    ) -> None:
        self.field = field
        self.translation_key = translation_key
        self.placeholders = placeholders or {}
        super().__init__(translation_key)
```

**Usage in options_flow.py**:

```python
try:
    reward_dict = eh.create_reward(user_input)
except EntityValidationError as err:
    errors[err.field] = err.translation_key  # Field highlights red
```

---

## Reward Entity Reference

### Current Field Inventory (6 fields)

| Storage Key               | Form Key                         | Default                    | Type      | Required |
| ------------------------- | -------------------------------- | -------------------------- | --------- | -------- |
| `DATA_REWARD_NAME`        | `CFOF_REWARDS_INPUT_NAME`        | -                          | str       | ✅ Yes   |
| `DATA_REWARD_COST`        | `CFOF_REWARDS_INPUT_COST`        | `DEFAULT_REWARD_COST` (10) | float     | ✅ Yes   |
| `DATA_REWARD_DESCRIPTION` | `CFOF_REWARDS_INPUT_DESCRIPTION` | `SENTINEL_EMPTY` ("")      | str       | No       |
| `DATA_REWARD_ICON`        | `CFOF_REWARDS_INPUT_ICON`        | `DEFAULT_REWARD_ICON`      | str       | No       |
| `DATA_REWARD_LABELS`      | `CFOF_REWARDS_INPUT_LABELS`      | []                         | list[str] | No       |
| `DATA_REWARD_INTERNAL_ID` | (generated)                      | uuid4()                    | str       | Auto     |

### TypedDict Definition (type_defs.py lines 86-95)

```python
class RewardData(TypedDict):
    """Type definition for a reward entity."""

    internal_id: str
    name: str
    cost: float
    description: str
    icon: str
    labels: list[str]
```

### Existing Validation (flow_helpers.py lines 2733-2758)

1. **Name required**: Empty name → `TRANS_KEY_CFOF_INVALID_REWARD_NAME`
2. **Name unique**: Duplicate → `TRANS_KEY_CFOF_DUPLICATE_REWARD`

### Current Options Flow Pattern (lines 936-966)

```python
async def async_step_add_reward(self, user_input=None):
    errors = fh.validate_rewards_inputs(user_input, rewards_dict)
    if not errors:
        reward_data = fh.build_rewards_data(user_input, rewards_dict)
        internal_id = list(reward_data.keys())[0]
        new_reward_data = reward_data[internal_id]
        coordinator._create_reward(internal_id, new_reward_data)
```

---

## Detailed Phase Tracking

---

### Phase 1 – Infrastructure (100%) ✅

**Goal**: Create data_builders.py file with EntityValidationError exception class.

**Steps / detailed work items**:

1. - [x] Create new file `custom_components/kidschores/data_builders.py`

   ```python
   """Entity lifecycle management helpers.

   This module is the SINGLE SOURCE OF TRUTH for:
   - Entity field defaults
   - Business logic validation
   - Complete entity structure building

   Consumers:
   - options_flow.py (UI entity management)
   - services.py (programmatic entity management)
   - coordinator.py (thin storage wrapper)

   See Also:
   - flow_helpers.py: UI-specific validation (uniqueness, HA user checks)
   - type_defs.py: TypedDict definitions for type safety
   """

   from __future__ import annotations

   import uuid
   from typing import Any

   from . import const
   from .type_defs import RewardData


   # ==============================================================================
   # EXCEPTIONS
   # ==============================================================================


   class EntityValidationError(Exception):
       """Validation error with field-specific information for form highlighting.

       This exception is raised when business logic validation fails in entity
       creation or update. The field attribute allows options_flow to map the
       error back to the specific form field that caused the failure.

       Attributes:
           field: The CFOF_* constant identifying the form field that failed
           translation_key: The TRANS_KEY_* constant for the error message
           placeholders: Optional dict for translation string placeholders

       Example:
           raise EntityValidationError(
               field=const.CFOF_REWARDS_INPUT_COST,
               translation_key=const.TRANS_KEY_INVALID_REWARD_COST,
               placeholders={"value": str(cost)},
           )
       """

       def __init__(
           self,
           field: str,
           translation_key: str,
           placeholders: dict[str, str] | None = None,
       ) -> None:
           """Initialize EntityValidationError.

           Args:
               field: The CFOF_* constant for the field that failed validation
               translation_key: The TRANS_KEY_* constant for error message
               placeholders: Optional dict for translation placeholders
           """
           self.field = field
           self.translation_key = translation_key
           self.placeholders = placeholders or {}
           super().__init__(translation_key)


   # ==============================================================================
   # REWARDS
   # ==============================================================================

   # Reward functions will be added in Phase 2
   ```

2. - [x] Add import to `__init__.py` if needed (verify integration loads) - **NOT NEEDED** - imported directly by options_flow

3. - [x] Run quality gates: ✅ Lint passed, mypy 0 errors

**Key issues**:

- File must follow existing code organization patterns
- Docstrings required per Silver quality standards
- Type hints required for all parameters and returns

---

### Phase 2 – Rewards in data_builders.py (100%) ✅

**Goal**: Implement unified `build_reward()` function that handles BOTH create and update with zero duplication.

**Comparison with Current Chores Pattern**:

| Aspect     | Current Chores Pattern                                 | New Rewards Pattern                     |
| ---------- | ------------------------------------------------------ | --------------------------------------- |
| Create     | `kh.build_default_chore_data()` (~120 lines)           | `eh.build_reward(user_input)`           |
| Update     | `coordinator._update_chore()` (~140 lines, duplicated) | `eh.build_reward(user_input, existing)` |
| Total      | ~260 lines across 2 functions                          | **~50 lines, 1 function**               |
| Drift risk | High (two functions can diverge)                       | Zero (same function)                    |

**Steps / detailed work items**:

1. - [x] Add unified `build_reward()` function to data_builders.py - **IMPLEMENTED**

   ```python
   def build_reward(
       user_input: dict[str, Any],
       existing: RewardData | None = None,
   ) -> RewardData:
       """Build reward data for create or update operations.

       This is the SINGLE SOURCE OF TRUTH for reward field handling.
       One function handles both create (existing=None) and update (existing=RewardData).

       Args:
           user_input: Form/service data with CFOF_* keys (may have missing fields)
           existing: None for create, existing RewardData for update

       Returns:
           Complete RewardData TypedDict with all 6 fields populated

       Raises:
           EntityValidationError: If business logic validation fails

       Example:
           # Create new reward
           new_reward = build_reward(user_input)

           # Update existing reward
           updated = build_reward(user_input, existing=coordinator.rewards_data[rid])
       """
       is_create = existing is None

       # --- Name validation (shared for create and update) ---
       raw_name = user_input.get(const.CFOF_REWARDS_INPUT_NAME)
       if raw_name is not None:
           name = raw_name.strip() if isinstance(raw_name, str) else raw_name
           if not name:
               raise EntityValidationError(
                   field=const.CFOF_REWARDS_INPUT_NAME,
                   translation_key=const.TRANS_KEY_CFOF_INVALID_REWARD_NAME,
               )
       elif is_create:
           # Name is required for create
           raise EntityValidationError(
               field=const.CFOF_REWARDS_INPUT_NAME,
               translation_key=const.TRANS_KEY_CFOF_INVALID_REWARD_NAME,
           )
       else:
           # Update: keep existing name if not provided
           name = existing[const.DATA_REWARD_NAME]

       # --- Helper: get field value with appropriate fallback ---
       def get_field(cfof_key: str, data_key: str, default: Any) -> Any:
           """Get value from input, or fallback (default for create, existing for update)."""
           if cfof_key in user_input:
               return user_input[cfof_key]
           if existing is not None:
               return existing.get(data_key, default)
           return default

       # --- Build complete reward structure ---
       return RewardData(
           internal_id=(
               existing[const.DATA_REWARD_INTERNAL_ID]
               if existing
               else str(uuid.uuid4())
           ),
           name=name,
           cost=get_field(
               const.CFOF_REWARDS_INPUT_COST,
               const.DATA_REWARD_COST,
               const.DEFAULT_REWARD_COST,
           ),
           description=get_field(
               const.CFOF_REWARDS_INPUT_DESCRIPTION,
               const.DATA_REWARD_DESCRIPTION,
               const.SENTINEL_EMPTY,
           ),
           icon=get_field(
               const.CFOF_REWARDS_INPUT_ICON,
               const.DATA_REWARD_ICON,
               const.DEFAULT_REWARD_ICON,
           ),
           labels=get_field(
               const.CFOF_REWARDS_INPUT_LABELS,
               const.DATA_REWARD_LABELS,
               [],
           ),
       )
   ```

2. - [x] Run quality gates: ✅ Lint passed, mypy 0 errors, 848 tests pass

**Key issues**:

- One function, two modes: `existing=None` for create, `existing=RewardData` for update
- `get_field()` helper handles the create/update fallback logic cleanly
- TypedDict return ensures type safety
- **This pattern is MORE efficient than current chores** - apply to chores later

---

### Phase 3 – Update flow_helpers.py (100%) ✅

**Goal**: Migrate `build_rewards_data()` to delegate to entity*helpers. Keep defaults using `const.DEFAULT*\*` for consistency.

**Steps / detailed work items**:

1. - [x] Modify `build_rewards_data()` in flow_helpers.py - **DELEGATED to data_builders with deprecation notice**

   **BEFORE** (duplicated logic):

   ```python
   def build_rewards_data(user_input, existing_rewards=None) -> dict:
       internal_id = user_input.get(const.CFOF_GLOBAL_INPUT_INTERNAL_ID, str(uuid.uuid4()))
       return {
           internal_id: {
               const.DATA_REWARD_NAME: reward_name,
               const.DATA_REWARD_COST: user_input[const.CFOF_REWARDS_INPUT_COST],
               # ... all fields duplicated here
           }
       }
   ```

   **AFTER** (delegates to data_builders):

   ```python
   def build_rewards_data(
       user_input: dict[str, Any],
       existing_rewards: dict[str, Any] | None = None,
   ) -> dict[str, Any]:
       """Build reward data from user input.

       Delegates to data_builders.build_reward() for consistent field handling.
       This function is maintained for backwards compatibility with existing code.

       Args:
           user_input: Dictionary containing user inputs from the form.
           existing_rewards: Not used, maintained for API compatibility.

       Returns:
           Dictionary with reward data in storage format, keyed by internal_id.
       """
       # Import here to avoid circular dependency during module load
       from . import data_builders as eh

       # Check if this is an update (internal_id provided) or create
       existing_id = user_input.get(const.CFOF_GLOBAL_INPUT_INTERNAL_ID)
       # Note: For flow_helpers, we always create new - updates go through edit step
       # which has access to existing data directly

       reward_dict = eh.build_reward(user_input)
       internal_id = reward_dict[const.DATA_REWARD_INTERNAL_ID]
       return {internal_id: dict(reward_dict)}
   ```

2. - [x] Verify `validate_rewards_inputs()` remains unchanged - ✅ No changes needed

3. - [x] Verify `build_reward_schema()` uses `const.DEFAULT_*` - ✅ Correctly uses const.DEFAULT\_\*

4. - [x] Run quality gates: ✅ Lint passed, mypy 0 errors

**Key issues**:

- Use local import `from . import data_builders as eh` to avoid circular imports
- flow_helpers becomes thin wrapper calling data_builders
- Validation functions (`validate_rewards_inputs`) unchanged - they're correct
- Schema functions (`build_reward_schema`) unchanged - they're correct

---

### Phase 4 – Update options_flow.py (100%) ✅

**Goal**: Update async_step_add_reward() and async_step_edit_reward() to use unified `build_reward()`.

**Steps / detailed work items**:

1. - [x] Add import to options_flow.py: **ADDED** `from . import data_builders as eh` and `EntityValidationError`

2. - [x] Update `async_step_add_reward()` - **UPDATED** to use `eh.build_reward()` with EntityValidationError handling

3. - [x] Update `async_step_edit_reward()` - **UPDATED** to use `eh.build_reward(user_input, existing)` with EntityValidationError handling

4. - [x] Run quality gates: ✅ Lint passed, mypy 0 errors, 848 tests pass

**Key issues**:

- **Same function**: `build_reward(input)` for create, `build_reward(input, existing)` for update
- EntityValidationError caught and mapped to form field for highlighting
- Direct storage write (bypass coordinator methods for clarity)

---

### Phase 5 – Create/Update Reward Services (0%)

```python
async def async_step_add_reward(self, user_input=None):
    """Add a new reward."""
    coordinator = self._get_coordinator()
    errors: dict[str, str] = {}
    rewards_dict = coordinator.rewards_data

    if user_input is not None:
        # Layer 2: UI validation (uniqueness check)
        errors = fh.validate_rewards_inputs(user_input, rewards_dict)

        if not errors:
            try:
                # Layer 3: Entity helper builds complete structure
                # build_reward(user_input) - no existing = create mode
                reward_dict = eh.build_reward(user_input)
                internal_id = reward_dict[const.DATA_REWARD_INTERNAL_ID]

                # Layer 4: Coordinator stores (thin wrapper)
                coordinator._data[const.DATA_REWARDS][internal_id] = dict(reward_dict)
                coordinator._persist()
                coordinator.async_update_listeners()

                const.LOGGER.debug(
                    "Added Reward '%s' with ID: %s",
                    reward_dict[const.DATA_REWARD_NAME],
                    internal_id,
                )
                self._mark_reload_needed()
                return await self.async_step_init()

            except EntityValidationError as err:
                # Map field-specific error for form highlighting
                errors[err.field] = err.translation_key

    schema = fh.build_reward_schema()
    return self.async_show_form(
        step_id=const.OPTIONS_FLOW_STEP_ADD_REWARD,
        data_schema=schema,
        errors=errors,
    )
```

3. - [ ] Update `async_step_edit_reward()` similarly:

   ```python
   async def async_step_edit_reward(self, user_input=None):
       """Edit an existing reward."""
       coordinator = self._get_coordinator()
       errors: dict[str, str] = {}
       reward_id = self._selected_reward_id
       existing_reward = coordinator.rewards_data[reward_id]

       if user_input is not None:
           # Validate: exclude current reward from duplicate check
           other_rewards = {
               rid: r for rid, r in coordinator.rewards_data.items()
               if rid != reward_id
           }
           errors = fh.validate_rewards_inputs(user_input, other_rewards)

           if not errors:
               try:
                   # build_reward(user_input, existing) - with existing = update mode
                   reward_dict = eh.build_reward(user_input, existing=existing_reward)

                   # Store updated reward
                   coordinator._data[const.DATA_REWARDS][reward_id] = dict(reward_dict)
                   coordinator._persist()
                   coordinator.async_update_listeners()

                   const.LOGGER.debug(
                       "Updated Reward '%s' with ID: %s",
                       reward_dict[const.DATA_REWARD_NAME],
                       reward_id,
                   )
                   self._mark_reload_needed()
                   return await self.async_step_init()

               except EntityValidationError as err:
                   errors[err.field] = err.translation_key

       # Pre-populate form with existing values
       schema = fh.build_reward_schema(default=existing_reward)
       return self.async_show_form(
           step_id=const.OPTIONS_FLOW_STEP_EDIT_REWARD,
           data_schema=schema,
           errors=errors,
       )
   ```

4. - [ ] Run quality gates:
   ```bash
   ./utils/quick_lint.sh --fix
   mypy custom_components/kidschores/options_flow.py
   python -m pytest tests/ -x -v --tb=line
   ```

**Key issues**:

- **Same function, different modes**: `build_reward(input)` vs `build_reward(input, existing=data)`
- Must import EntityValidationError for catch block
- Convert TypedDict to dict for storage: `dict(reward_dict)`
- Edit step excludes current reward from duplicate check

---

### Phase 5 – Create/Update Reward Services (0%)

**Goal**: Integrate with CREATE_UPDATE_REWARD_SERVICES plan using unified `build_reward()`.

**Steps / detailed work items**:

This phase implements the services from [CREATE_UPDATE_REWARD_SERVICES_IN-PROCESS.md](./CREATE_UPDATE_REWARD_SERVICES_IN-PROCESS.md), now using data_builders.

1. - [ ] Add service schemas to services.py (from CREATE_UPDATE_REWARD_SERVICES Phase 1):

   ```python
   # Service schemas - user-friendly field names
   # NOTE: cost is REQUIRED for services - no invisible defaults
   SERVICE_CREATE_REWARD_SCHEMA = vol.Schema(
       {
           vol.Required("name"): cv.string,
           vol.Required("cost"): vol.Coerce(float),  # Required - user must see the value
           vol.Optional("description"): cv.string,
           vol.Optional("icon"): cv.icon,
           vol.Optional("labels"): vol.All(cv.ensure_list, [cv.string]),
       }
   )

   SERVICE_UPDATE_REWARD_SCHEMA = vol.Schema(
       {
           vol.Required("reward_id"): cv.string,
           vol.Optional("name"): cv.string,
           vol.Optional("cost"): vol.Coerce(float),
           vol.Optional("description"): cv.string,
           vol.Optional("icon"): cv.icon,
           vol.Optional("labels"): vol.All(cv.ensure_list, [cv.string]),
       }
   )
   ```

2. - [ ] Add service-to-form field mapping:

   ```python
   # Map service fields to CFOF_* form field names
   SERVICE_TO_REWARD_FORM_MAPPING: dict[str, str] = {
       "name": const.CFOF_REWARDS_INPUT_NAME,
       "cost": const.CFOF_REWARDS_INPUT_COST,
       "description": const.CFOF_REWARDS_INPUT_DESCRIPTION,
       "icon": const.CFOF_REWARDS_INPUT_ICON,
       "labels": const.CFOF_REWARDS_INPUT_LABELS,
   }


   def _map_service_to_form_input(
       service_data: dict[str, Any],
       mapping: dict[str, str],
   ) -> dict[str, Any]:
       """Convert service field names to CFOF_* form field names."""
       return {
           mapping[key]: value
           for key, value in service_data.items()
           if key in mapping
       }
   ```

3. - [ ] Implement `handle_create_reward()` service handler:

   ```python
   async def handle_create_reward(call: ServiceCall) -> ServiceResponse:
       """Handle kidschores.create_reward service call."""
       from . import data_builders as eh
       from .data_builders import EntityValidationError

       coordinator = _get_coordinator_for_service(call)
       if not coordinator:
           raise ServiceValidationError(
               translation_domain=const.DOMAIN,
               translation_key=const.TRANS_KEY_SVC_NO_COORDINATOR,
           )

       # Map service fields to form fields
       form_input = _map_service_to_form_input(
           dict(call.data),
           SERVICE_TO_REWARD_FORM_MAPPING,
       )

       # Check for duplicate name (Layer 2 validation)
       errors = fh.validate_rewards_inputs(form_input, coordinator.rewards_data)
       if errors:
           field, trans_key = next(iter(errors.items()))
           raise ServiceValidationError(
               translation_domain=const.DOMAIN,
               translation_key=trans_key,
           )

       try:
           # build_reward(input) - create mode (no existing)
           reward_dict = eh.build_reward(form_input)
           internal_id = reward_dict[const.DATA_REWARD_INTERNAL_ID]

           coordinator._data[const.DATA_REWARDS][internal_id] = dict(reward_dict)
           coordinator._persist()
           coordinator.async_update_listeners()

           const.LOGGER.info(
               "Service created reward '%s' with ID: %s",
               reward_dict[const.DATA_REWARD_NAME],
               internal_id,
           )

           return {"reward_id": internal_id}

       except EntityValidationError as err:
           raise ServiceValidationError(
               translation_domain=const.DOMAIN,
               translation_key=err.translation_key,
               translation_placeholders=err.placeholders,
           ) from err
   ```

4. - [ ] Implement `handle_update_reward()` service handler:

   ```python
   async def handle_update_reward(call: ServiceCall) -> ServiceResponse:
       """Handle kidschores.update_reward service call."""
       from . import data_builders as eh
       from .data_builders import EntityValidationError

       coordinator = _get_coordinator_for_service(call)
       reward_id = call.data["reward_id"]

       if reward_id not in coordinator.rewards_data:
           raise ServiceValidationError(
               translation_domain=const.DOMAIN,
               translation_key=const.TRANS_KEY_SVC_REWARD_NOT_FOUND,
           )

       existing_reward = coordinator.rewards_data[reward_id]
       form_input = _map_service_to_form_input(
           dict(call.data),
           SERVICE_TO_REWARD_FORM_MAPPING,
       )

       # Validate name uniqueness (exclude current reward)
       if const.CFOF_REWARDS_INPUT_NAME in form_input:
           other_rewards = {
               rid: r for rid, r in coordinator.rewards_data.items()
               if rid != reward_id
           }
           errors = fh.validate_rewards_inputs(form_input, other_rewards)
           if errors:
               raise ServiceValidationError(
                   translation_domain=const.DOMAIN,
                   translation_key=list(errors.values())[0],
               )

       try:
           # build_reward(input, existing) - update mode
           reward_dict = eh.build_reward(form_input, existing=existing_reward)

           coordinator._data[const.DATA_REWARDS][reward_id] = dict(reward_dict)
           coordinator._persist()
           coordinator.async_update_listeners()

           return {"reward_id": reward_id}

       except EntityValidationError as err:
           raise ServiceValidationError(
               translation_domain=const.DOMAIN,
               translation_key=err.translation_key,
           ) from err
   ```

5. - [ ] Register services in `async_setup_services()`

6. - [ ] Add service constants to const.py:

   ```python
   SERVICE_CREATE_REWARD: Final = "create_reward"
   SERVICE_UPDATE_REWARD: Final = "update_reward"
   ```

7. - [ ] Add to services.yaml for documentation

8. - [ ] Run quality gates

**Key issues**:

- **Same function**: `build_reward(input)` for create, `build_reward(input, existing)` for update
- Services require `cost` field (no invisible defaults for automations)
- Both services use identical data_builders as Options Flow

---

### Phase 6 – Testing & Validation (50%)

**Goal**: Validate data_builders through E2E service tests (more valuable than unit tests).

**Analysis Complete**: See [ENTITY_HELPERS_REWARDS_FIRST_SUP_TEST_ANALYSIS.md](./ENTITY_HELPERS_REWARDS_FIRST_SUP_TEST_ANALYSIS.md)

**Key Decision**: User feedback determined that **service tests provide better E2E coverage** than unit testing `build_reward()` directly. Service tests exercise the full path: `Schema → Mapping → build_reward() → Storage → Response`.

**Steps / detailed work items**:

1. - [x] Analyze existing test coverage
2. - [x] Create test analysis document (`_SUP_TEST_ANALYSIS.md`)
3. - [x] Update strategy: prioritize service tests over unit tests
4. - [x] Add SERVICE*FIELD*\* constants to const.py
5. - [x] Update services.py schemas to use constants
6. - [x] Update DEVELOPMENT*STANDARDS.md with SERVICE_FIELD*\* pattern
7. - [x] Create test template in analysis document
8. - [ ] Implement TestCreateRewardService (3 tests)
9. - [ ] Implement TestUpdateRewardService (4 tests)
10. - [ ] Run full validation suite

**Test Implementation Target**: Extend `tests/test_reward_services.py` with:

| Class                   | Tests | Priority |
| ----------------------- | ----- | -------- |
| TestCreateRewardService | 3     | HIGH     |
| TestUpdateRewardService | 4     | HIGH     |

**Validation Checklist**:

- [x] All quality gates passed (lint, mypy, tests)
- [ ] Service tests implemented and passing
- [ ] Manual validation complete

**Key issues**:

- Test template ready in supporting document
- SERVICE*FIELD*\* constants added for schema consistency
- Existing TestApproveRewardCostOverride provides pattern reference

---

## Service Path vs Options Flow Path Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OPTIONS FLOW PATH                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User fills form in UI                                                      │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ Voluptuous Schema       │ ← Type checking, selectors                     │
│  │ (options_flow.py)       │   (Schema defaults = UI hints only)            │
│  └─────────────────────────┘                                                │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ flow_helpers            │ ← Uniqueness validation only                   │
│  │ .validate_rewards_inputs│   Returns: dict[str, str] (errors)            │
│  │ ❌ NO DEFAULTS          │                                                │
│  └─────────────────────────┘                                                │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ data_builders          │ ← ✅ SINGLE SOURCE OF DEFAULTS                │
│  │ .build_reward()         │   Returns: RewardData TypedDict               │
│  │ (existing=None)         │   Mode: CREATE (uses const.DEFAULT_*)         │
│  └─────────────────────────┘                                                │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ coordinator._data       │ ← Thin storage                                 │
│  │ + _persist()            │                                                │
│  └─────────────────────────┘                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            SERVICE PATH                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Automation calls kidschores.create_reward                                  │
│  { name: "Quick Reward" }  ← Only name provided                            │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ Service schema          │ ← Basic validation                             │
│  │ + field mapping         │   service names → CFOF_* keys                  │
│  └─────────────────────────┘                                                │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ flow_helpers            │ ← Uniqueness validation (reused)               │
│  │ .validate_rewards_inputs│                                                │
│  └─────────────────────────┘                                                │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ data_builders          │ ← ✅ SAME FUNCTION AS OPTIONS FLOW            │
│  │ .build_reward()         │   Fills ALL defaults automatically             │
│  │ (existing=None)         │   Mode: CREATE (uses const.DEFAULT_*)         │
│  └─────────────────────────┘                                                │
│      │                                                                      │
│      ▼                                                                      │
│  ┌─────────────────────────┐                                                │
│  │ coordinator._data       │ ← Same storage path                            │
│  │ + _persist()            │                                                │
│  └─────────────────────────┘                                                │
│                                                                             │
│  ✅ PROVES ARCHITECTURE: Same data_builders used by both paths            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Future Entity Expansion

After Rewards validates the unified `build_X(user_input, existing=None)` pattern, apply same approach to:

| Entity       | Complexity | Fields | Per-Kid | Current Pattern                            | Priority |
| ------------ | ---------- | ------ | ------- | ------------------------------------------ | -------- |
| ✅ Rewards   | Simple     | 6      | No      | **NEW: unified** ~50 lines                 | Phase 1  |
| Bonuses      | Simple     | 6      | No      | Separate funcs                             | Next     |
| Penalties    | Simple     | 6      | No      | Separate funcs                             | Next     |
| Kids         | Medium     | 22     | No      | Separate funcs                             | After    |
| Parents      | Medium     | 14     | No      | Separate funcs                             | After    |
| Badges       | Complex    | 20+    | No      | Separate funcs                             | Later    |
| Chores       | Complex    | 34     | Yes     | **~260 lines** (kh.build + coord.\_update) | Later    |
| Achievements | Complex    | 15+    | Yes     | Separate funcs                             | Later    |
| Challenges   | Complex    | 15+    | Yes     | Separate funcs                             | Later    |

### Pattern Improvement (Rewards vs Current Chores)

**Current Chores Pattern** (drift risk, duplicated logic):

```
kc_helpers.build_default_chore_data()  → ~120 lines (CREATE only)
coordinator._update_chore()            → ~140 lines (UPDATE, SEPARATE)
                                       ═══════════════════════════════
                                       ~260 lines total, field lists duplicated
```

**New Rewards Pattern** (unified, zero drift):

```
data_builders.build_reward(input, existing=None) → ~50 lines (BOTH modes)
                                       ═══════════════════════════════
                                       ~50 lines total, single field list
```

**Projected Chores Refactor Savings**:

- After validating Rewards pattern, apply to `build_chore(input, existing=None)`
- Expected reduction: ~260 lines → ~100 lines (complex due to 34 fields + per_kid structures)
- Eliminates drift risk between create/update field handling

---

## Testing & Validation Summary

| Test Category                    | Expected Outcome                          | Status |
| -------------------------------- | ----------------------------------------- | ------ |
| Unit tests (data_builders)      | All functions return correct TypedDict    | ⬜     |
| Integration tests (Options Flow) | Add/Edit reward works with new helpers    | ⬜     |
| Integration tests (Services)     | create_reward/update_reward services work | ⬜     |
| Manual validation (UI)           | Rewards manageable via Options Flow       | ⬜     |
| Manual validation (Services)     | Rewards creatable via Developer Tools     | ⬜     |
| Quality gates (lint/type)        | ./utils/quick_lint.sh passes, mypy clean  | ⬜     |

---

## Notes & Follow-up

1. **Architecture Proof Point**: Rewards service + Options Flow both using `build_reward()` proves pattern works
2. **Unified Function Benefit**: Same function handles create AND update - see Phase 2 comparison table
3. **Pattern Documentation**: After Rewards complete, document `build_X(input, existing=None)` pattern for other entity types
4. **Coordinator Simplification**: Remove \_create_reward/\_update_reward methods (direct storage is cleaner)
5. **Chores Refactor**: Apply unified pattern to chores next - biggest win (260 lines → ~100 lines)
6. **TypedDict Benefits**: Type checking catches field name mismatches at development time

---

> **Template usage notice:** This plan follows [PLAN_TEMPLATE.md](../PLAN_TEMPLATE.md). Save as `ENTITY_HELPERS_REWARDS_FIRST_IN-PROCESS.md` in `docs/in-process/`. Move to `docs/completed/` when all phases complete.
