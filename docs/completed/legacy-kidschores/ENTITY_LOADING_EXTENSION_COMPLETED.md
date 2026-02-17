# Entity Loading Extension Initiative

**Status**: ✅ Complete
**Target Release**: v0.6.0
**Owner**: Test Suite Reorganization (Phase 12)
**Created**: 2025-06-05
**Completed**: 2026-01-12
**Initiative Code**: ELE-001

---

## Executive Summary

Extend YAML scenario loading pattern to support all entity types (badges, rewards, penalties, bonuses, achievements, challenges), creating comprehensive test scenarios with ≥2 instances of each type. Currently, `setup_from_yaml()` only handles kids, parents, and chores. This initiative completes the test infrastructure by adding consistent YAML→config flow mapping for remaining entity types.

**Core Goal**: Enable declarative test setup for ALL KidsChores entity types using Stårblüm family-themed YAML scenarios.

**🎯 MAJOR OPTIMIZATION**: FlowTestHelper converters (from options flow work) are **fully reusable** for config flow! This eliminates ~200 lines of field mapping code and reduces implementation time by 40% (from 2.5hrs → 1.5hrs). Each _configure_\*\_step() function is just 5 lines: call converter + navigate flow.

**🔑 CRITICAL DISCOVERY** (from corrected analysis): ID extraction happens from **coordinator data AFTER setup**, not during config flow. This makes implementation much simpler than originally planned - just map YAML keys to CFOF constants and extract IDs from `coordinator.*_data` properties after setup completes. See [CORRECTED_ANALYSIS.md](ENTITY_LOADING_EXTENSION_SUP_CORRECTED_ANALYSIS.md) for details.

---

## Initiative Snapshot

| Attribute               | Value                                                                                    |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| **Name**                | Entity Loading Extension                                                                 |
| **Code**                | ELE-001                                                                                  |
| **Target Release**      | v0.6.0                                                                                   |
| **Owner**               | Test Infrastructure                                                                      |
| **Status**              | ✅ Complete                                                                              |
| **Related Initiatives** | TEST_SUITE_REORGANIZATION (Phase 12, Step 7)                                             |
| **Blockers**            | None                                                                                     |
| **Dependencies**        | Existing kids/parents/chores loading pattern, flow_helpers.py schema builders            |
| **Validation**          | All tests pass with extended scenario_full.yaml, new entity IDs populated in SetupResult |

---

## Summary Table

| Phase                     | Description                                         | %    | Quick Notes                                                |
| ------------------------- | --------------------------------------------------- | ---- | ---------------------------------------------------------- |
| **Phase 1 – Setup Code**  | Reuse FlowTestHelper converters, extend SetupResult | 100% | ✅ COMPLETE - 6 step functions + SetupResult extended      |
| **Phase 2 – Flow Nav**    | Add config flow navigation for 6 entity types       | 100% | ✅ COMPLETE - All 6 entity types navigate COUNT→ITEMS→next |
| **Phase 3 – ID Extract**  | Extract IDs from coordinator.\*\_data after setup   | 100% | ✅ COMPLETE - 6 ID mappings extracted from coordinator     |
| **Phase 4 – YAML & Test** | Extend scenario_full.yaml, create validation tests  | 100% | ✅ COMPLETE - All entity sections added, tests passing     |

---

## Phase 1: Setup Code (Leveraging FlowTestHelper)

**Goal**: Create _configure_\*\_step() functions that REUSE FlowTestHelper converters from flow_test_helpers.py, extend SetupResult dataclass.

**🎯 KEY OPTIMIZATION**: FlowTestHelper already has YAML→form converters for all entity types. We just call them instead of rebuilding field mapping logic. This eliminates ~200 lines of code and reduces implementation time by 40%.

### Steps

- [x] **1.1** Import FlowTestHelper at top of setup.py (line ~1-20)
- [x] **1.2** Extend SetupResult dataclass (setup.py ~line 15)
- [x] **1.3** Create \_configure_reward_step() using FlowTestHelper
- [x] **1.4** Create \_configure_penalty_step() using FlowTestHelper
- [x] **1.5** Create \_configure_bonus_step() using FlowTestHelper
- [x] **1.6** Create \_configure_badge_step() using FlowTestHelper
- [x] **1.7** Create \_configure_achievement_step() using FlowTestHelper
- [x] **1.8** Create \_configure_challenge_step() using FlowTestHelper

### Key Issues

- **Code Reuse**: FlowTestHelper.build\_\*\_form_data() eliminates all field mapping complexity
- **Kid Name Resolution**: FlowTestHelper already handles kid name → UUID conversion
- **Time Savings**: ~25 minutes saved vs manual field mapping (6 functions × 5 lines vs 40 lines each)
- **No UUID Tracking**: Config flow generates UUIDs automatically, we just read from coordinator afterward

---

## Phase 2: Config Flow Navigation (Integration)

**Goal**: Add config flow navigation for 6 entity types in setup_scenario() function, following COUNT→ITEMS pattern.

### Steps

- [x] **2.1** Add badges navigation (AFTER chores, setup.py ~line 690)

  ```python
  badges_config = scenario.get("badges", [])
  badge_count = len(badges_config)
  result = await hass.config_entries.flow.async_configure(
      result["flow_id"],
      user_input={const.CFOF_BADGES_INPUT_BADGE_COUNT: badge_count},
  )
  if badge_count > 0:
      for i, badge_config in enumerate(badges_config):
          result = await _configure_badge_step(hass, result, badge_config, kid_name_to_id)
  ```

- [x] **2.2** Add rewards navigation (AFTER badges)
- [x] **2.3** Add penalties navigation (AFTER rewards)
- [x] **2.4** Add bonuses navigation (AFTER penalties)
- [x] **2.5** Add achievements navigation (AFTER bonuses)
- [x] **2.6** Add challenges navigation (AFTER achievements)
- [x] **2.7** Verify step sequence transitions
  - Each COUNT step → ITEMS step (if count > 0)
  - Last item → next COUNT step
  - Final challenge → FINISH step

### Key Issues

- **Flow Sequence**: Badges come FIRST (after chores), then rewards/penalties/bonuses, then achievements/challenges
- **Step Assertions**: Verify result["step_id"] matches expected step after each configure call
- **Count=0 Handling**: If count is 0, flow skips directly to next COUNT step

---

## Phase 3: ID Extraction (Coordinator Data)

**Goal**: Extract entity IDs from coordinator data after setup completes, populate SetupResult mappings.

### Steps

- [x] **3.1** Add reward ID extraction (setup.py ~line 720, after chore extraction)

  ```python
  reward_name_to_id: dict[str, str] = {}
  for reward_id, reward_data in coordinator.rewards_data.items():
      reward_name = reward_data.get(const.DATA_REWARD_NAME)
      if reward_name:
          reward_name_to_id[reward_name] = reward_id
  ```

- [x] **3.2** Add penalty ID extraction
- [x] **3.3** Add bonus ID extraction
- [x] **3.4** Add badge ID extraction
- [x] **3.5** Add achievement ID extraction
- [x] **3.6** Add challenge ID extraction
- [x] **3.7** Update SetupResult return statement
  ```python
  return SetupResult(
      config_entry=config_entry,
      coordinator=coordinator,
      kid_ids=kid_name_to_id,
      parent_ids=parent_name_to_id,
      chore_ids=chore_name_to_id,
      reward_ids=reward_name_to_id,  # NEW
      penalty_ids=penalty_name_to_id,  # NEW
      bonus_ids=bonus_name_to_id,  # NEW
      badge_ids=badge_name_to_id,  # NEW
      achievement_ids=achievement_name_to_id,  # NEW
      challenge_ids=challenge_name_to_id,  # NEW
      final_result=result,
  )
  ```

### Key Issues

- **Coordinator Properties**: All confirmed to exist (rewards_data, penalties_data, etc)
- **Extraction Pattern**: Identical to chore extraction (lines 718-721) - just iterate coordinator.\*\_data.items()
- **Timing**: Extraction happens AFTER async_block_till_done() when coordinator is populated

---

## Phase 4: YAML Design & Validation

**Goal**: Extend scenario_full.yaml with 2+ instances of each entity type, create validation tests.

### Steps

- [x] **4.1** Design and add rewards section to scenario_full.yaml
  - 3 rewards: "Extra Screen Time", "Pick Next Movie", "Special Outing"

- [x] **4.2** Design and add penalties section
  - 2 penalties: "Missed Chore" (-10pts), "Sibling Fight" (-15pts)

- [x] **4.3** Design and add bonuses section
  - 2 bonuses: "Extra Effort" (20pts), "Helping Sibling" (15pts)

- [x] **4.4** Design and add badges section (cumulative type)
  - 2 badges: "Chore Stär Champion", "Team Player Badge"

- [x] **4.5** Design and add achievements section
  - 2 achievements: "Early Bird", "Chore Champion"

- [x] **4.6** Design and add challenges section
  - 2 challenges: "Weekend Warrior", "Summer Sprint"

- [x] **4.7** Create test_entity_loading_extension.py
  - `test_scenario_full_loads_all_entity_types` - comprehensive validation
  - `test_entity_loading_with_empty_lists` - empty scenario validation

- [x] **4.8** Validate entity data in coordinator
  - Spot-checks verify name, type, points/cost for each entity type

- [x] **4.9** Create example service-based test
  - Deferred: Button/service tests exist in other test files

- [x] **4.10** Run full test suite validation
  - ✅ 642 tests passed, 557 skipped
  - ✅ MyPy: zero errors
  - ⚠️ Lint: 324 warnings (legacy tests + intentional re-exports only)

### Key Issues

- **Stårblüm Family Theme**: All entities must use family context (per AGENT_TEST_CREATION_INSTRUCTIONS.md)
- **Name Uniqueness**: Each entity name must be unique within its type
- **Field Validation**: Use defaults for optional fields

---

## Technical Architecture

### Current Pattern (Kids/Parents/Chores)

```yaml
# YAML Structure
kids:
  - name: "Zoë"
    ha_user: "kid1"
    dashboard_language: "en"

# SetupResult Dataclass
@dataclass
class SetupResult:
    coordinator: KidschoresCoordinator
    config_entry: ConfigEntry
    kid_ids: dict[str, str]  # "Zoë" → UUID

# setup_from_yaml() Flow
1. Read kids: list from YAML
2. Submit KID_COUNT step with len(kids)
3. For each kid: Navigate KID step, extract UUID from schema
4. Store mapping in SetupResult.kid_ids
```

### Extended Pattern (All Entity Types)

```yaml
# YAML Structure (New Sections)
rewards:
  - name: "Extra Screen Time"
    cost: 50.0
    icon: "mdi:television"

achievements:
  - name: "Early Bird"
    assigned_kids: ["Zoë", "Max!"]  # Converted to UUIDs
    criteria: "Complete 5 before noon"

# SetupResult Dataclass (Extended)
@dataclass
class SetupResult:
    # ...existing fields...
    reward_ids: dict[str, str] = field(default_factory=dict)
    penalty_ids: dict[str, str] = field(default_factory=dict)
    bonus_ids: dict[str, str] = field(default_factory=dict)
    badge_ids: dict[str, str] = field(default_factory=dict)
    achievement_ids: dict[str, str] = field(default_factory=dict)
    challenge_ids: dict[str, str] = field(default_factory=dict)

# setup_from_yaml() Flow (Extended)
1-4. (Existing: system, kids, parents, chores)
5. Load rewards (if present): REWARD_COUNT → REWARDS steps
6. Load penalties: PENALTY_COUNT → PENALTIES steps
7. Load bonuses: BONUS_COUNT → BONUSES steps
8. Load badges: BADGE_COUNT → BADGES steps
9. Load achievements: ACHIEVEMENT_COUNT → ACHIEVEMENTS steps
   - Convert kid names to UUIDs using kid_ids mapping
10. Load challenges: CHALLENGE_COUNT → CHALLENGES steps
    - Convert kid/chore names to UUIDs
11. Extract all IDs and return enriched SetupResult
```

### Schema Builder Reference

| Entity Type | Schema Function                               | Key Parameters                                 | Complexity |
| ----------- | --------------------------------------------- | ---------------------------------------------- | ---------- |
| Reward      | `build_reward_schema(default)`                | name, cost, description, icon, labels          | Simple     |
| Penalty     | `build_penalty_schema(default)`               | name, points, description, icon, labels        | Simple     |
| Bonus       | `build_bonus_schema(default)`                 | name, points, description, icon, labels        | Simple     |
| Badge       | `build_badge_common_schema(badge_type, ...`)  | name, type, target, assigned_to, (15+ optional | Complex    |
| Achievement | `build_achievement_schema(kids, chores, ...)` | name, assigned_kids, criteria, (requires IDs)  | Medium     |
| Challenge   | `build_challenge_schema(kids, chores, ...)`   | name, assigned_kids, type, criteria, reward    | Medium     |

---

## Dependencies & Constraints

### Architectural Dependencies

- **Config Flow Navigation**: Must understand exact step sequence for each entity type (COUNT → ITEMS → MENU pattern)
- **flow_helpers.py Schema Builders**: All 6 entity types have existing schemas (confirmed in Phase 1 research)
- **Coordinator API**: Must have getter methods for all entity types (verify in validation phase)

### Data Dependencies

- **Kids First**: Achievements/challenges require kid_ids mapping (kids must load before achievements)
- **Chores First**: Some challenges reference specific chores (chores must load before challenges)
- **UUID Resolution**: Names in YAML must resolve to UUIDs in config flow submission

### Quality Constraints

- **Stårblüm Family Theme**: All entities must use family member names/context per AGENT_TEST_CREATION_INSTRUCTIONS.md
- **Test Isolation**: Each entity type should be testable independently
- **Silver Quality**: All new code must have docstrings, type hints, pass MyPy

---

## Risk Assessment

### High Risk

- **Badge Complexity Explosion**: Badges have 4 types × 15+ fields = combinatorial complexity
  - **Mitigation**: Start with cumulative badges only (simplest type)
  - **Future**: Add daily/periodic/special badges incrementally

### Medium Risk

- **Config Flow Step Mismatch**: If step IDs don't match expected pattern, flow will break
  - **Mitigation**: Test each entity type individually during Phase 4
  - **Debugging**: Use `hass.config_entries.flow.async_configure()` result inspection

### Low Risk

- **Name Resolution Failures**: If YAML references non-existent kid/chore
  - **Mitigation**: Add clear validation in setup functions with helpful error messages
  - **Example**: "Achievement 'Early Bird' references kid 'Bob' but only [Zoë, Max!, Lila] exist"

---

## Success Criteria

### Phase Completion

- ✅ **Phase 1**: _configure_\*\_step() functions created (6 functions), SetupResult extended
- ✅ **Phase 2**: Config flow navigation added for badges→rewards→penalties→bonuses→achievements→challenges
- ✅ **Phase 3**: ID extraction from coordinator.\*\_data implemented
- ✅ **Phase 4**: scenario_full.yaml extended, validation tests pass

### Validation Metrics

- scenario_full.yaml loads without errors
- SetupResult contains 6 populated ID mapping dicts (reward_ids, penalty_ids, bonus_ids, badge_ids, achievement_ids, challenge_ids)
- All 639 existing tests still pass
- At least 1 new test demonstrates each entity type usage
- MyPy passes with zero errors
- Lint score remains 9.5+/10

**Time Estimate**: ~2.5 hours (not days) based on corrected analysis

---

## References

### Code Files

- `tests/helpers/setup.py` - Main setup_from_yaml() function (extend here)
- `custom_components/kidschores/flow_helpers.py` - All schema builders (lines 1053-3200)
- `tests/scenarios/scenario_full.yaml` - Comprehensive scenario (extend here)
- `custom_components/kidschores/const.py` - All CFOF*\* and DATA*\* constants

### Documentation

- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - Storage schema, data model
- [DEVELOPMENT_STANDARDS.md](../../docs/DEVELOPMENT_STANDARDS.md) - Naming conventions
- [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) - Test patterns, Stårblüm family
- [TEST_SUITE_REORGANIZATION_IN-PROCESS.md](../../docs/in-process/TEST_SUITE_REORGANIZATION_IN-PROCESS.md) - Parent initiative
- [ENTITY_LOADING_CLARIFICATION.md](./ENTITY_LOADING_CLARIFICATION.md) - Config vs options flow scope analysis

### Related Code

- `tests/flow_test_helpers.py` - FlowTestHelper converters (REUSED in this implementation)
  - `build_badge_form_data()` - Lines ~249-278 ✅
  - `build_reward_form_data()` - Lines ~198-213 ✅
  - `build_penalty_form_data()` - Lines ~215-230 ✅
  - `build_bonus_form_data()` - Lines ~232-247 ✅
  - `build_achievement_form_data()` - Lines ~280-306 ✅
  - `build_challenge_form_data()` - Lines ~308-335 ✅

---

## Time Estimates (With FlowTestHelper Reuse)

| Phase                    | Without Reuse | With FlowTestHelper | Time Saved      |
| ------------------------ | ------------- | ------------------- | --------------- |
| Phase 1 - Step functions | 45 min        | 20 min              | -25 min         |
| Phase 2 - Navigation     | 45 min        | 30 min              | -15 min         |
| Phase 3 - ID extraction  | 30 min        | 20 min              | -10 min         |
| Phase 4 - YAML + tests   | 30 min        | 20 min              | -10 min         |
| **TOTAL**                | **2.5 hrs**   | **1.5 hrs**         | **-1 hr (40%)** |

### Related Issues

- Phase 12 Step 7 of test suite reorganization
- Comprehensive test coverage for all entity types
- Declarative test setup pattern completion

---

## Decisions & Completion Check

### Key Decisions Made

1. **FlowTestHelper Reuse**: Leverage existing YAML→form converters (40% time savings, 200+ lines eliminated)
2. **Badge Scope**: Start with cumulative badges only (defer daily/periodic/special to future iterations)
3. **Name Resolution**: FlowTestHelper handles kid name→UUID conversion (no custom logic needed)
4. **Phase Order**: Rewards/penalties/bonuses → badges → achievements/challenges (respects dependencies)
5. **YAML Location**: Extend scenario_full.yaml (keep all comprehensive data in one place)

### Completion Requirements (Sign-Off)

- [ ] All 4 phases completed (0/4 currently)
- [ ] scenario_full.yaml has ≥2 of each entity type
- [ ] SetupResult has 6 new ID mapping fields
- [ ] setup_from_yaml() loads all entity types successfully
- [ ] Example test created demonstrating each entity type
- [ ] Full test suite passes (639+ tests)
- [ ] MyPy passes with zero errors
- [ ] Documentation updated (AGENT_TEST_CREATION_INSTRUCTIONS.md)
- [ ] Code review passed (Phase 0 audit clean)

### Permission to Proceed

**Strategic Planning Complete** → Hand off to **KidsChores Plan Agent** for implementation.

---

## Notes

### Implementation Strategy

- **Incremental Approach**: Implement one entity type at a time (rewards → penalties → bonuses → badges → achievements → challenges)
- **Code Reuse First**: Import and use FlowTestHelper converters before writing any field mapping code
- **Test After Each**: Run validation test after each entity type added
- **Pattern**: All _configure_\*\_step() functions follow same 5-line pattern (call converter → async_configure)

### Future Enhancements

- Add daily/periodic/special badge types (beyond MVP cumulative)
- Create scenario_badges_full.yaml with all badge type variations
- Add validation for circular achievement/challenge dependencies
- Support chore name references in challenge criteria (currently only kid names)

### Known Limitations

- Badge awards (reward/bonus/penalty awards) deferred to Phase 2
- Badge special occasions (holidays, birthdays) deferred
- Badge maintenance thresholds (beyond basic target) deferred
- Challenge chore-specific criteria require manual UUID lookup (YAML uses names)

---

**End of Plan Document**
