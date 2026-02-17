# Options & Config Flow Test Coverage Initiative

## Initiative snapshot

- **Name / Code**: OPTIONS_CONFIG_FLOW_TEST_COVERAGE
- **Target release / milestone**: v0.5.x (Test Suite Modernization)
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: ✅ Complete

## Summary & immediate steps

| Phase / Step                        | Description                                     | % complete | Quick notes                                                                                             |
| ----------------------------------- | ----------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------- |
| Phase 1 – Config Flow Base Coverage | Add tests for all 9 entity types in config flow | 100%       | ✅ All 9 tested: kids, parents, chores, badges, rewards, penalties, bonuses, achievements, challenges   |
| Phase 2 – Options Flow Add Tests    | Complete add tests for all 9 entity types       | 100%       | ✅ All 9 entity types now have add tests                                                                |
| Phase 3 – FlowTestHelper Completion | Add missing form data builders                  | 100%       | ✅ All 9 builders implemented                                                                           |

1. **Key objective** – Achieve base test coverage for all 9 entity types (kids, parents, chores, badges, rewards, penalties, bonuses, achievements, challenges) in both config flow and options flow add operations.

2. **Summary of recent work**:

   - ✅ Created `test_options_flow_entity_crud.py` with modern patterns (17 tests passing)
   - ✅ Created `FlowTestHelper` class with YAML→form data converters
   - ✅ Verified tests use `tests.helpers` imports (not direct `const.py`)
   - ✅ Verified tests use `setup_from_yaml()` with `scenario_minimal.yaml`
   - ✅ Added options flow add tests for: badges, achievements, challenges
   - ✅ Added `build_achievement_form_data()` to FlowTestHelper
   - ✅ Added `build_challenge_form_data()` to FlowTestHelper
   - ✅ **Phase 1 Complete**: Added 6 config flow tests for badges, rewards, penalties, bonuses, achievements, challenges
   - ✅ **Bug Fix**: Fixed `config_flow.py` line 856 - incorrect `kids_dict` format passed to `build_badge_common_schema`

3. **Next steps (short term)** – Initiative complete, move to `completed/`:

   - [x] Audit `test_config_flow_fresh_start.py` for entity type coverage – DONE
   - [x] Create `_configure_badge_step()` helper function – DONE
   - [x] Create `_configure_reward_step()` helper function – DONE
   - [x] Create `_configure_penalty_step()` helper function – DONE
   - [x] Create `_configure_bonus_step()` helper function – DONE
   - [x] Create `_configure_achievement_step()` helper function – DONE
   - [x] Create `_configure_challenge_step()` helper function – DONE
   - [x] Add `test_fresh_start_with_badge()` – Test single badge in config flow – DONE
   - [x] Add `test_fresh_start_with_reward()` – Test single reward in config flow – DONE
   - [x] Add `test_fresh_start_with_penalty()` – Test single penalty in config flow – DONE
   - [x] Add `test_fresh_start_with_bonus()` – Test single bonus in config flow – DONE
   - [x] Add `test_fresh_start_with_achievement()` – Test single achievement in config flow – DONE
   - [x] Add `test_fresh_start_with_challenge()` – Test single challenge in config flow – DONE

4. **Risks / blockers**:

   - `scenario_minimal.yaml` lacks badges, achievements, challenges – may need to use `scenario_full.yaml` for those tests
   - Achievement/challenge schemas are complex (kid assignments, date ranges, chore linkage)

5. **References**:

   - [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) - Test patterns
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Storage-only architecture
   - [flow_test_helpers.py](../../tests/flow_test_helpers.py) - FlowTestHelper class
   - [test_options_flow_entity_crud.py](../../tests/test_options_flow_entity_crud.py) - Current options flow tests

6. **Decisions & completion check**:
   - **Decisions captured**:
     - Use simple cumulative badge for badge test (complex badge tests in separate initiative)
     - Focus on add operations only; edit/delete tests are out of scope for this initiative
     - All tests must use `tests.helpers` imports and `FlowTestHelper` patterns
   - **Completion confirmation**: `[x]` All follow-up items completed before marking initiative done.

---

## Detailed phase tracking

### Phase 1 – Config Flow Base Coverage

- **Goal**: Verify that `test_config_flow.py` has at least one add test for each of the 9 entity types during initial setup.

- **Steps / detailed work items**:

  1. [x] Read `test_config_flow.py` and inventory existing entity type coverage – DONE
  2. [x] Document which entity types have add tests – DONE
  3. [x] Identify any missing entity types – DONE
  4. [x] Implement missing config flow add tests:
     - [x] `test_fresh_start_with_badge()` – Test individual badge addition – DONE
     - [x] `test_fresh_start_with_reward()` – Test individual reward addition – DONE
     - [x] `test_fresh_start_with_penalty()` – Test individual penalty addition – DONE
     - [x] `test_fresh_start_with_bonus()` – Test individual bonus addition – DONE
     - [x] `test_fresh_start_with_achievement()` – Test individual achievement addition – DONE
     - [x] `test_fresh_start_with_challenge()` – Test individual challenge addition – DONE
  5. [x] Run `pytest tests/test_config_flow_fresh_start.py -v` to verify all 9 entity types tested and pass – DONE (15 passed, 3 skipped)

- **Audit results** (Config Flow Entity Coverage):
  | Entity Type | Has Config Flow Test? | Test Function | Status |
  |-------------|----------------------|---------------|--------|
  | Kids | ✅ YES | test_fresh_start_points_and_kid | PASS |
  | Parents | ✅ YES | test_fresh_start_with_parent_no_notifications | PASS |
  | Chores | ✅ YES | test_fresh_start_with_single_chore | PASS |
  | Badges | ✅ YES | test_fresh_start_with_badge | PASS |
  | Rewards | ✅ YES | test_fresh_start_with_reward | PASS |
  | Penalties | ✅ YES | test_fresh_start_with_penalty | PASS |
  | Bonuses | ✅ YES | test_fresh_start_with_bonus | PASS |
  | Achievements | ✅ YES | test_fresh_start_with_achievement | PASS |
  | Challenges | ✅ YES | test_fresh_start_with_challenge | PASS |

- **Key issues**: ✅ ALL RESOLVED
  - All 9 entity types now have config flow add tests
  - Bug fix in config_flow.py: `build_badge_common_schema` was receiving `{kid_name: kid_id}` format but expected `{kid_id: kid_data_dict}` format

---

### Phase 2 – Options Flow Add Tests

- **Goal**: Complete add tests for all 9 entity types in `test_options_flow_entity_crud.py`.

- **Steps / detailed work items**:

  1. [x] `test_add_kid_via_options_flow` – DONE (line 180)
  2. [x] `test_add_parent_via_options_flow` – DONE (line 210)
  3. [x] `test_add_chore_via_options_flow` – DONE (line 238)
  4. [x] `test_add_reward_via_options_flow` – DONE (line 287)
  5. [x] `test_add_penalty_via_options_flow` – DONE (line 324)
  6. [x] `test_add_bonus_via_options_flow` – DONE (line 356)
  7. [x] `test_add_badge_via_options_flow` – DONE (line 427)
  8. [x] `test_add_achievement_via_options_flow` – DONE (line 481)
  9. [x] `test_add_challenge_via_options_flow` – DONE (line 523)

- **Key issues**:
  - ✅ RESOLVED: Added FlowTestHelper constants for OPTIONS_FLOW_BADGES, OPTIONS_FLOW_ACHIEVEMENTS, OPTIONS_FLOW_CHALLENGES
  - ✅ RESOLVED: Added FlowTestHelper constants for OPTIONS_FLOW_STEP_ADD_BADGE, OPTIONS_FLOW_STEP_ADD_ACHIEVEMENT, OPTIONS_FLOW_STEP_ADD_CHALLENGE

---

### Phase 3 – FlowTestHelper Completion

- **Goal**: Add missing form data builders to `FlowTestHelper` class.

- **Steps / detailed work items**:

  1. [x] `build_kid_form_data()` – DONE (line 82)
  2. [x] `build_parent_form_data()` – DONE (line 107)
  3. [x] `build_chore_form_data()` – DONE (line 136)
  4. [x] `build_reward_form_data()` – DONE (line 175)
  5. [x] `build_penalty_form_data()` – DONE (line 192)
  6. [x] `build_bonus_form_data()` – DONE (line 210)
  7. [x] `build_badge_form_data()` – DONE (line 228)
  8. [x] `build_achievement_form_data()` – DONE (line 278)
  9. [x] `build_challenge_form_data()` – DONE (line 308)

- **Key issues**:
  - ✅ RESOLVED: Achievement schema fields: name, icon, description, type, target_value, assigned_to, reward_points
  - ✅ RESOLVED: Challenge schema fields: name, icon, description, type, start_date, end_date, target_value, assigned_to, reward_points

---

## Testing & validation

- **Tests executed**:

  ```bash
  pytest tests/test_options_flow_entity_crud.py -v --tb=short
  # Result: 17 passed in 1.87s (all 9 entity types now covered)
  ```

- **Outstanding tests**:

  - Config flow entity coverage audit (Phase 1) - Still needed

- **Validation commands**:

  ```bash
  # Run all options flow tests
  pytest tests/test_options_flow*.py -v --tb=short

  # Run config flow tests
  pytest tests/test_config_flow.py -v --tb=short

  # Run specific new test
  pytest tests/test_options_flow_entity_crud.py::test_add_badge_via_options_flow -v
  ```

---

## Notes & follow-up

### Out of Scope (Future Initiatives)

- Edit tests for all entity types
- Delete tests for all entity types
- Complex badge scenarios (periodic badges, chore-specific badges)
- Validation error edge cases
- Options flow navigation edge cases

### Architecture Notes

- All tests use `setup_from_yaml()` for integration setup
- Tests verify entities via `coordinator.{entity}_data` dictionaries
- Options flow returns to `OPTIONS_FLOW_STEP_INIT` after successful add
- After options flow changes, integration reloads → use `hass.data[DOMAIN][entry_id][COORDINATOR]` for fresh coordinator

### Stårblüm Family Convention

- Tests should use family names from scenario files when possible
- Current tests use generic names ("Test Kid", "Test Parent") – acceptable for base coverage
- Future complex tests should use actual scenario characters (Zoë, Max!, Lila, @Astrid, @Leo)
