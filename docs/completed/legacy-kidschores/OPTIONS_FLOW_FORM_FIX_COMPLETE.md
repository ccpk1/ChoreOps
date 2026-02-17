# Initiative Plan: Options Flow Form Fix (Badges, Achievements, Challenges)

## Initiative snapshot

- **Name / Code**: OPTIONS_FLOW_FORM_FIX
- **Target release / milestone**: v0.5.x patch
- **Owner / driver(s)**: KidsChores team
- **Status**: In Progress

## Summary & immediate steps

| Phase / Step                | Description                                     | % complete | Quick notes                                |
| --------------------------- | ----------------------------------------------- | ---------- | ------------------------------------------ |
| Phase 1 – Achievement Forms | Fix achievement add/edit forms                  | 100%       | ✅ + required assigned_kids validation     |
| Phase 2 – Challenge Forms   | Fix challenge add/edit forms                    | 100%       | ✅ + required assigned_kids + datetime fix |
| Phase 3 – Badge Forms       | Fix all 6 badge type edit forms via common func | 100%       | ✅ Simplified schema + suggested values    |
| Phase 4 – Testing           | Validate all forms work correctly               | 0%         | Manual + unit tests                        |

1. **Key objective** – Apply the proven suggested values pattern (from chores/rewards/kids) to badges, achievements, and challenges to fix:
   - Issue 1: Unable to clear optional fields (defaults always return)
   - Issue 2: Form data lost when validation errors occur

2. **Summary of recent work** – Pattern has been successfully applied to:
   - Kids forms (lines ~430-490)
   - Chores forms (lines ~1037-1200)
   - Rewards forms (lines ~2542-2618)
   - Bonuses/Penalties forms (lines ~2697, ~2786, ~2874, ~2986)
   - **Achievement forms (Phase 1 complete)**: Added suggested values + assigned_kids validation
   - **Challenge forms (Phase 2 complete)**: Added suggested values + assigned_kids validation

3. **Next steps (short term)** – Fix remaining entity types:
   - `async_add_edit_badge_common()` (lines 2253-2398)
   - `async_step_add_achievement()` / `async_step_edit_achievement()` (lines ~3020-3200)
   - `async_step_add_challenge()` / `async_step_edit_challenge()` (lines ~3250-3500)

4. **Risks / blockers**
   - Badge forms have complex type-specific field logic (6 badge types)
   - Achievement/Challenge forms require name↔ID conversions for assigned_kids
   - Challenge forms have date format conversions (ISO ↔ selector format)

5. **References**
   - Working pattern: `async_step_edit_reward()` lines 2542-2618
   - Working pattern: `async_step_edit_kid()` lines 400-495
   - Schema builder: `flow_helpers.py` `build_badge_common_schema()` line 1178

6. **Decisions & completion check**
   - **Decisions captured**:
     - Use suggested values pattern (not schema defaults) for all clearable fields
     - Schema builders should NOT receive existing entity data as `default=`
     - `add_suggested_values_to_schema()` is the single source of truth for form population
   - **Completion confirmation**: `[ ]` All follow-up items completed

---

## Detailed phase tracking

### Phase 1 – Achievement Forms Fix

- **Goal**: Fix `async_step_add_achievement()` and `async_step_edit_achievement()` to use suggested values pattern.

- **Current broken pattern in edit** (lines 3185-3200):

  ```python
  # Build default data from existing achievement
  default_data = {
      **achievement_data,
      const.DATA_ACHIEVEMENT_ASSIGNED_KIDS: assigned_kids_names,
  }

  # On validation error, merge user's attempted input with existing data
  if user_input:
      default_data.update(user_input)  # ❌ Updating defaults, not suggestions

  achievement_schema = fh.build_achievement_schema(
      kids_dict=kids_dict,
      chores_dict=chores_dict,
      default=default_data,  # ❌ Passing directly to schema
  )
  ```

- **Target pattern**:

  ```python
  # Build suggested values for form
  suggested_values = {
      const.CFOF_ACHIEVEMENTS_INPUT_NAME: achievement_data.get(const.DATA_ACHIEVEMENT_NAME),
      const.CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION: achievement_data.get(const.DATA_ACHIEVEMENT_DESCRIPTION),
      const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_KIDS: assigned_kids_names,  # Already converted
      const.CFOF_ACHIEVEMENTS_INPUT_TYPE: achievement_data.get(const.DATA_ACHIEVEMENT_TYPE),
      # ... all other CFOF fields
  }

  # On error, preserve user input
  if user_input:
      suggested_values.update(user_input)

  # Build schema without defaults
  schema = fh.build_achievement_schema(
      kids_dict=kids_dict,
      chores_dict=chores_dict,
      default=None,
  )
  schema = self.add_suggested_values_to_schema(schema, suggested_values)
  ```

- **Steps / detailed work items**
  1. `[x]` In `async_step_edit_achievement()`:
     - Create `suggested_values` dict with proper CFOF→DATA mapping
     - Handle assigned_kids name conversion (IDs → names for display)
     - Remove `default=default_data` from schema builder call
     - Add `add_suggested_values_to_schema()` after schema creation
  2. `[x]` In `async_step_add_achievement()`:
     - On error, use `add_suggested_values_to_schema(schema, user_input)`
     - Currently passes `default=user_input` to schema builder
  3. `[x]` Update `build_achievement_schema()` in flow_helpers.py if needed
  4. `[x]` Run lint and verify no errors

- **Key issues**
  - Achievement `assigned_kids` requires ID↔name conversion (display names in UI, UUIDs in storage)
  - Achievement type field affects which other fields are shown/required

---

### Phase 2 – Challenge Forms Fix

- **Goal**: Fix `async_step_add_challenge()` and `async_step_edit_challenge()` to use suggested values pattern.

- **Current broken pattern in edit** (lines 3348-3500):

  ```python
  if user_input is None:
      # First load - builds schema with existing data
      default_data = {
          **challenge_data,
          const.DATA_CHALLENGE_START_DATE: start_date_display,
          const.DATA_CHALLENGE_END_DATE: end_date_display,
          const.DATA_CHALLENGE_ASSIGNED_KIDS: assigned_kids_names,
      }
      schema = fh.build_challenge_schema(
          kids_dict=kids_dict, chores_dict=chores_dict, default=default_data
      )
      return self.async_show_form(...)  # ❌ Early return pattern

  # On error - loses most of the setup logic
  challenge_schema = fh.build_challenge_schema(
      kids_dict=kids_dict, chores_dict=chores_dict, default=user_input  # ❌ Only user_input
  )
  ```

- **Target pattern** (unified flow like rewards/chores):

  ```python
  async def async_step_edit_challenge(self, user_input=None):
      # ... validation and processing if user_input ...

      # Build suggested values (runs for both first load AND error case)
      existing_challenge = challenges_dict[internal_id]

      # Convert dates to selector format
      start_date_display = kh.dt_parse(...) if existing_challenge.get(...) else None
      end_date_display = kh.dt_parse(...) if existing_challenge.get(...) else None

      # Convert assigned_kids IDs to names
      id_to_name = {...}
      assigned_kids_names = [id_to_name.get(kid_id, kid_id) for kid_id in ...]

      suggested_values = {
          const.CFOF_CHALLENGES_INPUT_NAME: existing_challenge.get(const.DATA_CHALLENGE_NAME),
          const.CFOF_CHALLENGES_INPUT_START_DATE: start_date_display,
          const.CFOF_CHALLENGES_INPUT_END_DATE: end_date_display,
          const.CFOF_CHALLENGES_INPUT_ASSIGNED_KIDS: assigned_kids_names,
          # ... all other fields
      }

      # On error, preserve user input
      if user_input:
          suggested_values.update(user_input)

      schema = fh.build_challenge_schema(kids_dict=kids_dict, chores_dict=chores_dict, default=None)
      schema = self.add_suggested_values_to_schema(schema, suggested_values)

      return self.async_show_form(...)
  ```

- **Steps / detailed work items**
  1. `[x]` Refactor `async_step_edit_challenge()` to remove early return pattern:
     - Move `user_input is None` check to be consistent with other forms
     - Build `suggested_values` dict with all CFOF keys
     - Handle date format conversions (ISO → selector datetime format)
     - Handle assigned_kids ID→name conversions
  2. `[x]` In `async_step_add_challenge()`:
     - On error, use `add_suggested_values_to_schema(schema, user_input)`
  3. `[x]` Update `build_challenge_schema()` in flow_helpers.py to not use `default=` for field population
  4. `[x]` Add assigned_kids validation (require at least 1 kid assigned)
     - Added `TRANS_KEY_CFOF_CHALLENGE_NO_KIDS_ASSIGNED` constant
     - Added validation in `data_builders.validate_challenge_data()`
     - Added translation in `en.json` (both error sections)

- **Key issues**
  - ~~Challenge dates require format conversion (stored as ISO UTC, displayed as selector datetime dict)~~ ✅ Handled
  - ~~Challenge `assigned_kids` requires ID↔name conversion~~ ✅ Handled
  - ~~Current early return pattern (`if user_input is None: return`) makes error handling inconsistent~~ ✅ Fixed

---

### Phase 3 – Badge Forms Fix

- **Goal**: Fix `async_add_edit_badge_common()` to use suggested values pattern. Apply lessons learned from Phase 1-2 to handle all 6 badge types.

- **Steps / detailed work items**
  1. `[x]` Create `suggested_values` dict with CFOF→DATA key mapping for all badge fields
  2. `[x]` Modify schema building section to NOT pass `default_data` to schema builder
  3. `[x]` Add `add_suggested_values_to_schema()` call after schema creation
  4. `[x]` Simplify `build_badge_common_schema()` to use static defaults (not dynamic lookup)
  5. `[x]` Update config_flow.py to use same pattern for consistency
  6. `[x]` Run lint and verify no errors

- **Key changes made**:
  - `options_flow.py` (`async_add_edit_badge_common()`):
    - Added comprehensive `suggested_values` dict that flattens nested badge data (target, awards, tracked_chores, reset_schedule)
    - Build schema with `default=None`
    - Apply `add_suggested_values_to_schema()` for form population
  - `flow_helpers.py` (`build_badge_common_schema()`):
    - Simplified all field defaults to use static constants instead of complex `default.get(CFOF_*, default.get(DATA_*, ...))` lookups
    - Updated docstring to reflect new pattern
    - Removed dead code for dynamic default lookups
  - `config_flow.py` (`async_add_badge_common()`):
    - Updated to use `add_suggested_values_to_schema()` for error case

---

### Phase 4 – Testing & Validation

- **Goal**: Verify all forms work correctly for both issues.

- **Test scenarios**:
  1. **Clear field test**: Edit entity → clear an optional field → save → verify field is empty
  2. **Error preservation test**: Edit entity → enter invalid data → verify form shows user's input (not original defaults)
  3. **All badge types**: Test each of the 6 badge types separately
  4. **Date handling**: Test challenge date fields can be cleared and preserved on error

- **Steps / detailed work items**
  1. `[ ]` Manual testing checklist:
     - [ ] Badge cumulative: clear description, trigger error, verify data preserved
     - [ ] Badge daily: clear description, trigger error, verify data preserved
     - [ ] Badge periodic: clear description, trigger error, verify data preserved
     - [ ] Badge achievement-linked: edit, trigger error, verify data preserved
     - [ ] Badge challenge-linked: edit, trigger error, verify data preserved
     - [ ] Badge special_occasion: edit, trigger error, verify data preserved
     - [ ] Achievement: clear optional fields, trigger error, verify data preserved
     - [ ] Challenge: clear dates, trigger error, verify data preserved
  2. `[ ]` Run existing tests: `pytest tests/test_config_flow.py -v`
  3. `[ ]` Run lint: `./utils/quick_lint.sh --fix`
  4. `[ ]` Run mypy: `mypy custom_components/kidschores/`

- **Key issues**
  - Need to test all 6 badge types due to different field configurations
  - Date field testing is complex (selector format vs ISO format)

---

## Schema Builder Modifications Required

### `build_badge_common_schema()` (flow_helpers.py line 1178)

**Current pattern** (problematic):

```python
vol.Required(
    const.CFOF_BADGES_INPUT_NAME,
    default=default.get(
        const.CFOF_BADGES_INPUT_NAME,
        default.get(const.DATA_BADGE_NAME, const.SENTINEL_EMPTY),
    ),
): str,
```

**Target pattern**:

```python
vol.Required(const.CFOF_BADGES_INPUT_NAME): str,
# OR for optional fields with true empty defaults:
vol.Optional(const.CFOF_BADGES_INPUT_DESCRIPTION, default=""): str,
```

**Note**: The schema builder should define field structure only. Actual values come from `add_suggested_values_to_schema()`.

### Similar changes needed for:

- `build_achievement_schema()` (line 2478)
- `build_challenge_schema()` (line 2647)

---

## Testing & validation

- Tests executed: (to be filled during implementation)
- Outstanding tests: (to be filled during implementation)

## Notes & follow-up

- The `add_suggested_values_to_schema()` method is inherited from Home Assistant's config flow and handles the conversion of suggested values to the schema format.
- This pattern separates concerns: schema defines structure, suggested values provide current state.
- All clearable fields must use suggested values (not schema defaults) to allow clearing.
- The pattern is proven in chores, rewards, kids, bonuses, penalties forms.
