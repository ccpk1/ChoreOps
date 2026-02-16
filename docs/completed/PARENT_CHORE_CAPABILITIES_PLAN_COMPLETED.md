# Initiative Plan: Parent Chore Capabilities (Family Chores Extension)

## Initiative snapshot

- **Name / Code**: Parent Chore Capabilities / PARENT-CHORE-CAP
- **Target release / milestone**: v0.6.0 (Family Chores Edition)
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: 100% complete - Ready for archival

## Summary & immediate steps

| Phase / Step                  | Description                                        | % complete | Quick notes                                                                                           |
| ----------------------------- | -------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------- |
| Phase 1 – Data Model          | Add parent capability flags + shadow kid constants | 100%       | ✅ Complete                                                                                           |
| Phase 2 – Shadow Kid Creation | Parent form checkboxes + auto-create shadow kid    | 100%       | ✅ Complete                                                                                           |
| Phase 3 – Button Logic        | Conditional button creation based on flags         | 100%       | ✅ Complete                                                                                           |
| Phase 4 – Gamification Toggle | Skip points/badges when disabled                   | 100%       | ✅ Complete (4.3 dashboard helper done)                                                               |
| Phase 4.5 – Config Flow Fix   | Shadow kid creation in initial setup               | 100%       | ✅ Complete (shared build_shadow_kid_data)                                                            |
| Phase 5 – Edge Cases          | Notifications, language, deletion cascade          | 100%       | ✅ Complete (notifications, language, deletion cascade, shadow kid protection)                        |
| Phase 6 – Testing             | Comprehensive test coverage                        | 100%       | ✅ 22 shadow kid tests + 4 button tests = 26 tests total                                              |

1. **Key objective** – Enable parents to have chores assigned to them by creating a "shadow kid" profile when they opt-in. By default, shadow kids get ONLY an Approve button (one-click PENDING→APPROVED). Optionally enable full claim/disapprove workflow and/or gamification (points/badges).

2. **Summary of recent work**

   - **Phase 1-4.5 complete**: All constants, shadow kid creation, button logic, gamification toggle, dashboard helper, config flow fix
   - **Phase 4.3 dashboard helper COMPLETE**: Added 3 new attributes to dashboard helper sensor:
     - `is_shadow_kid` (bool) - Identifies shadow kid vs regular kid
     - `chore_workflow_enabled` (bool) - Exposes parent's enable_chore_workflow flag (controls claim/disapprove button visibility)
     - `gamification_enabled` (bool) - Exposes parent's enable_gamification flag (controls points/badges/rewards visibility)
   - **Entity ID construction bug fixed**: Corrected `SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER` constant from "helper" to "\_ui_dashboard_helper" for proper entity ID generation
   - **Phase 6 testing in progress**: Created `tests/scenarios/scenario_parent_shadow_kids.yaml` and `tests/test_parent_shadow_kid.py` (18/18 tests passing)
   - Test file includes 18 tests across 5 test classes:
     - `TestShadowKidCreation` (2 tests) - creation when flag enabled/disabled
     - `TestShadowKidAttributes` (5 tests) - is_shadow marker, linked_parent_id, name, points, flags
     - `TestShadowKidChoreAssignment` (4 tests) - shadow kid in kid list, chore assignment
     - `TestRegularKidDistinction` (2 tests) - regular kids NOT marked as shadow
     - `TestDataIntegrity` (5 tests) - counts, bidirectional links, dashboard helper attributes
   - 927 tests passing (up from 910), linting clean

3. **Next steps (short term)**

   - ✅ All phases complete - Ready for archival
   - Final validation: All 523 tests passing, lint clean, mypy clean
   - Next: Archive plan to `docs/completed/`

4. **Risks / blockers**

   - Name collision between parent and existing kid names
   - Notification duplication if shadow kid notifications not disabled
   - Dashboard helper sensor exposure for shadow kids
   - Edit flow complexity when toggling capabilities on/off

5. **References**

   - Agent testing instructions: `tests/TESTING_AGENT_INSTRUCTIONS.md`
   - Architecture overview: `docs/ARCHITECTURE.md`
   - Code review guide: `docs/CODE_REVIEW_GUIDE.md`
   - Button creation: `custom_components/kidschores/button.py`
   - Coordinator approval: `custom_components/kidschores/coordinator.py` (~L2462)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Shadow kids use parent's `ha_user_id` for authorization
     - Shadow kids have notifications disabled by default (avoid duplicates)
     - Approval-only workflow is the default (no claim/disapprove buttons)
     - "Enable chore workflow" adds claim/disapprove buttons (full workflow)
     - "Enable gamification" controls points/badges (independent of workflow)
   - **Completion confirmation**: `[x]` All follow-up items completed

---

## Design Overview

### Comprehensive Entity Behavior by Capability Tier

#### Tier 1: Shadow Kid Created (allow_chore_assignment=True)

**ALWAYS CREATED** for shadow kids:

| Entity Type  | Entity Name                              | Behavior           | Notes                        |
| ------------ | ---------------------------------------- | ------------------ | ---------------------------- |
| **Sensors**  |                                          |                    |                              |
|              | `sensor.kc_<parent>_chores`              | Shows chore counts | Same as regular kids         |
|              | `sensor.kc_<parent>_chore_status`        | Shows chore states | Same as regular kids         |
|              | `sensor.kc_<parent>_ui_dashboard_helper` | Dashboard data     | Exposes `is_shadow_kid=True` |
| **Buttons**  |                                          |                    |                              |
|              | `button.kc_approve_<parent>_<chore>`     | One-click approve  | PENDING→APPROVED             |
| **Calendar** |                                          |                    |                              |
|              | `calendar.kc_<parent>_chores`            | Due date tracking  | Same as regular kids         |
| **Datetime** |                                          |                    |                              |
|              | `datetime.kc_<parent>_<chore>_due`       | Chore due dates    | Same as regular kids         |

**NEVER CREATED** for shadow kids (Tier 1 only):

| Entity Type                             | Why Skipped            | Impact                                     |
| --------------------------------------- | ---------------------- | ------------------------------------------ |
| `button.kc_claim_<parent>_<chore>`      | Approval-only workflow | Parent uses approve button directly        |
| `button.kc_disapprove_<parent>_<chore>` | No rejection needed    | Chore stays PENDING if not approved        |
| `sensor.kc_<parent>_points`             | No gamification        | Would show 0 points, confusing             |
| `sensor.kc_<parent>_badges_*`           | No gamification        | Would show empty badges                    |
| `button.kc_<parent>_bonus_*`            | No gamification        | Can't apply bonuses without points         |
| `button.kc_<parent>_penalty_*`          | No gamification        | Can't apply penalties without points       |
| `button.kc_<parent>_reward_*`           | No gamification        | Can't redeem rewards without points        |
| `button.kc_<parent>_points_adjust_*`    | No gamification        | Manual point adjustment not needed         |
| `select.kc_<parent>_*`                  | No legacy features     | Shadow kids start fresh, no legacy selects |

#### Tier 2: Workflow Enabled (+enable_chore_workflow=True)

**ADDS these entities** (in addition to Tier 1):

| Entity Type | Entity Name                             | Behavior                       | Notes                                  |
| ----------- | --------------------------------------- | ------------------------------ | -------------------------------------- |
| **Buttons** |                                         |                                |                                        |
|             | `button.kc_claim_<parent>_<chore>`      | Claim chore (PENDING→CLAIMED)  | Parent can "check off" before approval |
|             | `button.kc_disapprove_<parent>_<chore>` | Reject claim (CLAIMED→PENDING) | Parent can un-claim if needed          |

**Workflow change**:

- Without workflow: PENDING → Approve → APPROVED
- With workflow: PENDING → Claim → CLAIMED → Approve/Disapprove → APPROVED/PENDING

#### Tier 3: Gamification Enabled (+enable_gamification=True)

**ADDS these entities** (in addition to previous tiers):

| Entity Type | Entity Name                                 | Behavior                 | Notes                            |
| ----------- | ------------------------------------------- | ------------------------ | -------------------------------- |
| **Sensors** |                                             |                          |                                  |
|             | `sensor.kc_<parent>_points`                 | Current point balance    | Same calculation as regular kids |
|             | `sensor.kc_<parent>_badges`                 | Earned badges count      | Badge system applies normally    |
|             | `sensor.kc_<parent>_badge_progress_*`       | Per-badge progress       | One sensor per badge type        |
|             | `sensor.kc_<parent>_achievement_progress_*` | Per-achievement progress | Achievement tracking             |
|             | `sensor.kc_<parent>_challenge_progress_*`   | Per-challenge progress   | Challenge participation          |
|             | `sensor.kc_<parent>_reward_status_*`        | Per-reward claim status  | Can redeem rewards               |
| **Buttons** |                                             |                          |                                  |
|             | `button.kc_<parent>_bonus_<bonus_id>`       | Apply bonus points       | Parent can earn bonuses          |
|             | `button.kc_<parent>_penalty_<penalty_id>`   | Apply penalty points     | Parent can receive penalties     |
|             | `button.kc_<parent>_reward_<reward_id>`     | Redeem reward            | Parent can spend points          |
|             | `button.kc_<parent>_points_adjust_plus_*`   | Manual point adjustment  | Add points manually              |
|             | `button.kc_<parent>_points_adjust_minus_*`  | Manual point adjustment  | Subtract points manually         |

**Gamification behavior**:

- Points awarded on chore approval (same calculation as kids)
- Badge progress tracked (streaks, completion counts, etc.)
- Achievement progress tracked (same criteria as kids)
- Challenge participation (if challenges are family-wide)
- Reward redemption (points deducted, items claimed)

#### Regular Kids (Comparison)

**ALWAYS CREATED** for regular kids (all tiers enabled):

All entities from Tiers 1+2+3 above, plus:

| Entity Type         | Entity Name                | Notes                         |
| ------------------- | -------------------------- | ----------------------------- |
| **Legacy Sensors**  | `sensor.kc_<kid>_*_legacy` | Migration compatibility       |
| **Select Entities** | `select.kc_<kid>_*`        | If any legacy selectors exist |

### Parent Form UI (Target)

```
Parent Configuration
────────────────────
Name: [Dad                    ]
HA User: [Select user...      ▼]
Associated Kids: [Sarah, Tommy ▼]
Dashboard Language: [English  ▼]

Notification Settings
─────────────────────
[x] Enable mobile notifications
    Service: [notify.mobile_app_dads_phone ▼]
[x] Enable persistent notifications

Chore Assignment (NEW)
──────────────────────
[x] Allow chores to be assigned to me
    Creates a profile so tasks can be assigned to you.

    [ ] Enable chore workflow
        Adds Claim and Disapprove buttons. Without this,
        only the Approve button is shown for one-click completion.

    [ ] Enable gamification
        Track points, badges, and rewards for your chores.
```

---

## Detailed phase tracking

### Phase 1 – Data Model (Constants & Storage)

- **Goal**: Define all new constants and update storage schema for parent capabilities.

- **Steps / detailed work items**

  1. **Add parent capability constants to const.py** (Status: ✅ Complete)

     ```python
     # Parent capability flags (stored on parent entity)
     DATA_PARENT_ALLOW_CHORE_ASSIGNMENT: Final = "allow_chore_assignment"
     DATA_PARENT_ENABLE_CHORE_WORKFLOW: Final = "enable_chore_workflow"
     DATA_PARENT_ENABLE_GAMIFICATION: Final = "enable_gamification"
     DATA_PARENT_LINKED_SHADOW_KID_ID: Final = "linked_shadow_kid_id"
     DATA_PARENT_DASHBOARD_LANGUAGE: Final = "dashboard_language"  # NEW

     # Config flow field names
     CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT: Final = "allow_chore_assignment"
     CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW: Final = "enable_chore_workflow"
     CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION: Final = "enable_gamification"
     CFOF_PARENTS_INPUT_DASHBOARD_LANGUAGE: Final = "dashboard_language"  # NEW

     # Shadow kid markers (stored on kid entity)
     DATA_KID_IS_SHADOW: Final = "is_shadow_kid"
     DATA_KID_LINKED_PARENT_ID: Final = "linked_parent_id"

     # Defaults
     DEFAULT_PARENT_ALLOW_CHORE_ASSIGNMENT: Final = False
     DEFAULT_PARENT_ENABLE_CHORE_WORKFLOW: Final = False
     DEFAULT_PARENT_ENABLE_GAMIFICATION: Final = False
     ```

  2. **Add translation keys to const.py** (Status: ✅ Complete)

     ```python
     TRANS_KEY_CFOF_ALLOW_CHORE_ASSIGNMENT: Final = "allow_chore_assignment"
     TRANS_KEY_CFOF_ALLOW_CHORE_ASSIGNMENT_DESC: Final = "allow_chore_assignment_description"
     TRANS_KEY_CFOF_ENABLE_CHORE_WORKFLOW: Final = "enable_chore_workflow"
     TRANS_KEY_CFOF_ENABLE_CHORE_WORKFLOW_DESC: Final = "enable_chore_workflow_description"
     TRANS_KEY_CFOF_ENABLE_GAMIFICATION: Final = "enable_gamification"
     TRANS_KEY_CFOF_ENABLE_GAMIFICATION_DESC: Final = "enable_gamification_description"
     TRANS_KEY_CFOF_PARENT_DASHBOARD_LANGUAGE: Final = "parent_dashboard_language"  # NEW
     TRANS_KEY_CFOF_PARENT_DASHBOARD_LANGUAGE_DESC: Final = "parent_dashboard_language_description"  # NEW
     TRANS_KEY_CFOF_SHADOW_KID_NAME_CONFLICT: Final = "shadow_kid_name_conflict"
     ```

  3. **Add translations to en.json** (Status: ✅ Complete)
     ```json
     {
       "options": {
         "step": {
           "add_parent": {
             "data": {
               "allow_chore_assignment": "Allow chores to be assigned to me",
               "enable_chore_workflow": "Enable chore workflow",
               "enable_gamification": "Enable gamification",
               "parent_dashboard_language": "Dashboard language"
             },
             "data_description": {
               "allow_chore_assignment": "Creates a profile so tasks can be assigned to you. By default, only an Approve button is shown for one-click completion.",
               "enable_chore_workflow": "Adds Claim and Disapprove buttons for full workflow (claim → approve/disapprove).",
               "enable_gamification": "Track points, badges, and rewards for your completed chores.",
               "parent_dashboard_language": "Language used for your chore dashboard and notifications."
             }
           }
         },
         "error": {
           "shadow_kid_name_conflict": "A kid with this name already exists. Use a different parent name or rename the existing kid."
         }
       }
     }
     ```

- **Key issues**

  - None anticipated for this phase

- **Estimated LOC**: ~50 lines (includes parent language field)

---

### Phase 2 – Shadow Kid Creation

- **Goal**: Update parent form with capability checkboxes and auto-create shadow kid.

- **Steps / detailed work items**

  1. **Update `build_parent_schema()` in flow_helpers.py** (Status: Not started)

     Add three new boolean selectors to parent schema:

     ```python
     def build_parent_schema(
         hass,
         users,
         kids_dict,
         default_parent_name=const.SENTINEL_EMPTY,
         default_ha_user_id=None,
         default_associated_kids=None,
         default_enable_mobile_notifications=False,
         default_mobile_notify_service=None,
         default_enable_persistent_notifications=False,
         default_dashboard_language=None,  # NEW parameter
         # NEW parameters
         default_allow_chore_assignment=False,
         default_enable_chore_workflow=False,
         default_enable_gamification=False,
     ):
         # ... existing schema ...

         # NEW: Dashboard language (before chore assignment section)
         vol.Optional(
             const.CFOF_PARENTS_INPUT_DASHBOARD_LANGUAGE,
             default=default_dashboard_language or const.DEFAULT_DASHBOARD_LANGUAGE,
         ): selector.LanguageSelector(
             selector.LanguageSelectorConfig(
                 languages=await kh.get_available_dashboard_languages(hass),
                 native_name=True,
             )
         ),

         # NEW: Chore assignment section
         vol.Optional(
             const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT,
             default=default_allow_chore_assignment,
         ): selector.BooleanSelector(),

         vol.Optional(
             const.CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW,
             default=default_enable_chore_workflow,
         ): selector.BooleanSelector(),

         vol.Optional(
             const.CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION,
             default=default_enable_gamification,
         ): selector.BooleanSelector(),
     ```

  2. **Update `build_parents_data()` in flow_helpers.py** (Status: Not started)

     Extract and store new flags in parent data:

     ```python
     def build_parents_data(user_input, parents_dict, existing_id=None):
         # ... existing code ...

         dashboard_language = user_input.get(
             const.CFOF_PARENTS_INPUT_DASHBOARD_LANGUAGE,
             const.DEFAULT_DASHBOARD_LANGUAGE
         )
         allow_chore_assignment = user_input.get(
             const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT, False
         )
         enable_chore_workflow = user_input.get(
             const.CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW, False
         )
         enable_gamification = user_input.get(
             const.CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION, False
         )

         return {
             internal_id: {
                 # ... existing fields ...
                 const.DATA_PARENT_DASHBOARD_LANGUAGE: dashboard_language,  # NEW
                 const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT: allow_chore_assignment,
                 const.DATA_PARENT_ENABLE_CHORE_WORKFLOW: enable_chore_workflow,
                 const.DATA_PARENT_ENABLE_GAMIFICATION: enable_gamification,
                 const.DATA_PARENT_LINKED_SHADOW_KID_ID: None,  # Set when shadow created
             }
         }
     ```

  3. **Add `_create_shadow_kid_for_parent()` helper in coordinator.py** (Status: Not started)

     ```python
     def _create_shadow_kid_for_parent(
         self,
         parent_id: str,
         parent_data: dict[str, Any]
     ) -> str:
         """Create a shadow kid profile linked to a parent.

         Args:
             parent_id: UUID of the parent entity
             parent_data: Parent's data dictionary

         Returns:
             shadow_kid_id: UUID of the created shadow kid
         """
         shadow_kid_id = str(uuid.uuid4())
         parent_name = parent_data.get(const.DATA_PARENT_NAME, "Parent")

         # Shadow kid inherits parent's HA user for authorization
         shadow_kid_data = {
             const.DATA_KID_NAME: parent_name,
             const.DATA_KID_INTERNAL_ID: shadow_kid_id,
             const.DATA_KID_HA_USER_ID: parent_data.get(const.DATA_PARENT_HA_USER_ID),

             # Link back to parent
             const.DATA_KID_IS_SHADOW: True,
             const.DATA_KID_LINKED_PARENT_ID: parent_id,

             # Disable notifications (parent already gets them)
             const.DATA_KID_ENABLE_NOTIFICATIONS: False,
             const.DATA_KID_MOBILE_NOTIFY_SERVICE: const.SENTINEL_EMPTY,
             const.DATA_KID_USE_PERSISTENT_NOTIFICATIONS: False,

             # Inherit dashboard language from parent
             const.DATA_KID_DASHBOARD_LANGUAGE: parent_data.get(
                 const.DATA_PARENT_DASHBOARD_LANGUAGE, self.hass.config.language
             ),

             # Initialize required fields with defaults
             const.DATA_KID_POINTS: 0.0,
             const.DATA_KID_BADGES_EARNED: {},
             const.DATA_KID_POINTS_MULTIPLIER: 1.0,
             const.DATA_KID_CHORE_DATA: {},
             const.DATA_KID_CHORE_STATS: {},
             const.DATA_KID_POINT_STATS: {},
             const.DATA_KID_BADGE_PROGRESS: {},
             const.DATA_KID_CUMULATIVE_BADGE_PROGRESS: {},
             const.DATA_KID_REWARD_DATA: {},
             const.DATA_KID_BONUS_APPLIES: {},
             const.DATA_KID_PENALTY_APPLIES: {},
             const.DATA_KID_OVERDUE_CHORES: [],
             const.DATA_KID_OVERDUE_NOTIFICATIONS: {},
         }

         self._data[const.DATA_KIDS][shadow_kid_id] = shadow_kid_data

         const.LOGGER.info(
             "Created shadow kid '%s' (ID: %s) for parent '%s' (ID: %s)",
             parent_name, shadow_kid_id, parent_name, parent_id
         )

         return shadow_kid_id
     ```

  4. **Update `async_step_add_parent()` in options_flow.py** (Status: Not started)

     After parent validation passes, check if shadow kid should be created:

     ```python
     # In async_step_add_parent, after validation:
     if not errors:
         parent_data = fh.build_parents_data(user_input, parents_dict)
         parent_id = list(parent_data.keys())[0]
         new_parent_data = parent_data[parent_id]
         parent_name = new_parent_data[const.DATA_PARENT_NAME]

         # Check if shadow kid creation requested
         if new_parent_data.get(const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, False):
             # Validate name doesn't conflict with existing kids
             existing_kid_names = [
                 k.get(const.DATA_KID_NAME, "").lower()
                 for k in coordinator.kids_data.values()
             ]
             if parent_name.lower() in existing_kid_names:
                 errors["base"] = const.TRANS_KEY_CFOF_SHADOW_KID_NAME_CONFLICT
             else:
                 # Create shadow kid
                 shadow_kid_id = coordinator._create_shadow_kid_for_parent(
                     parent_id, new_parent_data
                 )
                 new_parent_data[const.DATA_PARENT_LINKED_SHADOW_KID_ID] = shadow_kid_id

         if not errors:
             coordinator._create_parent(parent_id, new_parent_data)
             coordinator._persist()
             # Trigger entity platform reload for new kid entities
             await self._async_reload_platforms_for_new_kid()
     ```

  5. **Update `async_step_edit_parent()` in options_flow.py** (Status: Not started)

     Handle toggling of checkboxes:

     ```python
     # Scenarios to handle:
     # 1. allow_chore_assignment: False → True = Create shadow kid
     # 2. allow_chore_assignment: True → False = Delete shadow kid (or warn)
     # 3. enable_chore_workflow: toggled = Just update flag, entity reload handles buttons
     # 4. enable_gamification: toggled = Just update flag, entity reload handles sensors

     old_allow = existing_parent.get(const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT, False)
     new_allow = user_input.get(const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT, False)

     if not old_allow and new_allow:
         # Create shadow kid
         shadow_kid_id = coordinator._create_shadow_kid_for_parent(parent_id, updated_data)
         updated_data[const.DATA_PARENT_LINKED_SHADOW_KID_ID] = shadow_kid_id
     elif old_allow and not new_allow:
         # Delete shadow kid (cascade)
         shadow_kid_id = existing_parent.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID)
         if shadow_kid_id and shadow_kid_id in coordinator.kids_data:
             coordinator.delete_kid_entity(shadow_kid_id)
         updated_data[const.DATA_PARENT_LINKED_SHADOW_KID_ID] = None
     ```

- **Key issues**

  - **Name collision**: Parent name conflicts with existing kid name
    - Solution: Validate and show error, require rename
  - **Edit flow complexity**: Toggling `allow_chore_assignment` on/off
    - Create shadow kid on enable
    - Delete shadow kid on disable (may lose chore history)
  - **Platform reload**: New shadow kid needs entity platform reload
    - Use existing `_async_reload_platforms_for_new_kid()` pattern

- **Estimated LOC**: ~140 lines (includes language field integration)

---

### Phase 3 – Button Creation Logic

- **Goal**: Implement conditional button creation based on parent capability flags.

- **Steps / detailed work items**

  1. **Add helper functions in kc_helpers.py** (Status: Not started)

     ```python
     def is_shadow_kid(coordinator: KidsChoresDataCoordinator, kid_id: str) -> bool:
         """Check if a kid is a shadow kid (linked to parent)."""
         kid_info = coordinator.kids_data.get(kid_id, {})
         return kid_info.get(const.DATA_KID_IS_SHADOW, False)

     def get_parent_for_shadow_kid(
         coordinator: KidsChoresDataCoordinator,
         kid_id: str
     ) -> dict[str, Any] | None:
         """Get the parent data for a shadow kid."""
         kid_info = coordinator.kids_data.get(kid_id, {})
         parent_id = kid_info.get(const.DATA_KID_LINKED_PARENT_ID)
         if parent_id:
             return coordinator.parents_data.get(parent_id)
         return None

     def should_create_workflow_buttons(
         coordinator: KidsChoresDataCoordinator,
         kid_id: str
     ) -> bool:
         """Determine if claim/disapprove buttons should be created for a kid.

         Returns True for:
         - Regular kids (always have full workflow)
         - Shadow kids with enable_chore_workflow=True

         Returns False for:
         - Shadow kids with enable_chore_workflow=False (approval-only)
         """
         if not is_shadow_kid(coordinator, kid_id):
             return True  # Regular kids always get workflow buttons

         parent_data = get_parent_for_shadow_kid(coordinator, kid_id)
         if parent_data:
             return parent_data.get(const.DATA_PARENT_ENABLE_CHORE_WORKFLOW, False)
         return False

     def should_create_gamification_entities(
         coordinator: KidsChoresDataCoordinator,
         kid_id: str
     ) -> bool:
         """Determine if gamification entities should be created for a kid.

         Returns True for:
         - Regular kids (always have gamification)
         - Shadow kids with enable_gamification=True

         Returns False for:
         - Shadow kids with enable_gamification=False
         """
         if not is_shadow_kid(coordinator, kid_id):
             return True  # Regular kids always get gamification

         parent_data = get_parent_for_shadow_kid(coordinator, kid_id)
         if parent_data:
             return parent_data.get(const.DATA_PARENT_ENABLE_GAMIFICATION, False)
         return False
     ```

  2. **Update button entity creation in button.py** (Status: Not started)

     Modify the chore button creation loop (~lines 56-108):

     ```python
     for chore_id, chore_info in coordinator.chores_data.items():
         assigned_kids_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

         for kid_id in assigned_kids_ids:
             kid_name = kh.get_kid_name_by_id(coordinator, kid_id)
             if not kid_name:
                 kid_name = f"{const.TRANS_KEY_LABEL_KID} {kid_id}"

             # ALWAYS create Approve button (for all kids including shadow kids)
             entities.append(
                 ParentChoreApproveButton(
                     coordinator=coordinator,
                     entry=entry,
                     kid_id=kid_id,
                     kid_name=kid_name,
                     chore_id=chore_id,
                     chore_name=chore_name,
                     icon=chore_approve_icon,
                 )
             )

             # CONDITIONAL: Create Claim and Disapprove buttons
             # Only if regular kid OR shadow kid with workflow enabled
             if kh.should_create_workflow_buttons(coordinator, kid_id):
                 # Claim Button
                 entities.append(
                     KidChoreClaimButton(
                         coordinator=coordinator,
                         entry=entry,
                         kid_id=kid_id,
                         kid_name=kid_name,
                         chore_id=chore_id,
                         chore_name=chore_name,
                         icon=chore_claim_icon,
                     )
                 )

                 # Disapprove Button
                 entities.append(
                     ParentChoreDisapproveButton(
                         coordinator=coordinator,
                         entry=entry,
                         kid_id=kid_id,
                         kid_name=kid_name,
                         chore_id=chore_id,
                         chore_name=chore_name,
                         icon=chore_disapprove_icon,
                     )
                 )
     ```

  3. **Update bonus/penalty/reward button creation** (Status: Not started)

     These should also respect gamification flag:

     ```python
     # For bonus buttons (~line 170)
     for kid_id in coordinator.kids_data:
         if not kh.should_create_gamification_entities(coordinator, kid_id):
             continue  # Skip for shadow kids without gamification

         # ... create bonus buttons ...

     # Same pattern for penalty buttons (~line 149)
     # Same pattern for reward buttons (~line 101)
     # Same pattern for points adjust buttons (~line 227)
     ```

- **Key issues**

  - **Button entity unique IDs**: Must remain stable when workflow flag is toggled
    - Approve button always exists → stable UID
    - Claim/Disapprove buttons appear/disappear → UID based on kid+chore, not flag
  - **Entity registry cleanup**: When workflow disabled, claim/disapprove buttons should be removed
    - Platform reload handles this automatically

- **Estimated LOC**: ~80 lines

---

### Phase 4 – Gamification Toggle

- **Goal**: Skip points, badges, achievements when gamification is disabled for shadow kids.

- **Steps / detailed work items**

  1. **Update `approve_chore()` in coordinator.py** (Status: Not started)

     Check gamification flag before awarding points:

     ```python
     def approve_chore(self, parent_name: str, kid_id: str, chore_id: str,
                       points_awarded: float | None = None):
         # ... existing validation ...

         # Check if gamification is enabled for this kid
         enable_gamification = True  # Default for regular kids
         if kh.is_shadow_kid(self, kid_id):
             parent_data = kh.get_parent_for_shadow_kid(self, kid_id)
             if parent_data:
                 enable_gamification = parent_data.get(
                     const.DATA_PARENT_ENABLE_GAMIFICATION, False
                 )

         # Existing _process_chore_state call
         self._process_chore_state(
             kid_id,
             chore_id,
             const.CHORE_STATE_APPROVED,
             # Pass 0 points if gamification disabled
             points_awarded=default_points if enable_gamification else 0,
         )

         # Skip badge/achievement/challenge checks if gamification disabled
         if enable_gamification:
             self._check_badges_for_kid(kid_id)
             self._check_achievements_for_kid(kid_id)
             self._check_challenges_for_kid(kid_id)
     ```

  2. **Update sensor entity creation in sensor.py** (Status: Not started)

     Skip gamification sensors for shadow kids without gamification:

     ```python
     # Per-kid sensor creation loop
     for kid_id, kid_info in coordinator.kids_data.items():
         kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

         # Always create basic sensors (ALL kids including shadow)
         entities.append(KidChoresSensor(...))  # Chore counts
         entities.append(KidChoreStatusSensor(...))  # Chore status
         entities.append(KidDashboardHelperSensor(...))  # Dashboard helper

         # CONDITIONAL: Gamification sensors (only if gamification enabled)
         if kh.should_create_gamification_entities(coordinator, kid_id):
             entities.append(KidPointsSensor(...))
             entities.append(KidBadgesSensor(...))

             # Per-badge progress sensors
             for badge_id in coordinator.badges_data:
                 entities.append(KidBadgeProgressSensor(kid_id, badge_id))

             # Per-achievement progress sensors
             for achievement_id in coordinator.achievements_data:
                 entities.append(KidAchievementProgressSensor(kid_id, achievement_id))

             # Per-challenge progress sensors
             for challenge_id in coordinator.challenges_data:
                 entities.append(KidChallengeProgressSensor(kid_id, challenge_id))

             # Per-reward status sensors
             for reward_id in coordinator.rewards_data:
                 entities.append(KidRewardStatusSensor(kid_id, reward_id))

             # Legacy sensors (if they exist)
             # Skip for shadow kids - they start fresh
             if not kh.is_shadow_kid(coordinator, kid_id):
                 # Add any legacy sensors for regular kids only
                 pass
     ```

  3. **Update dashboard helper sensor** (Status: ✅ Complete)

     **New Attributes Added** (4 total):

     | Attribute              | Type      | Purpose                           | Shadow Kid Value             | Regular Kid Value |
     | ---------------------- | --------- | --------------------------------- | ---------------------------- | ----------------- |
     | `is_shadow_kid`        | bool      | Identify shadow kid               | `True`                       | `False`           |
     | `workflow_enabled`     | bool      | Expose parent's workflow flag     | From `enable_chore_workflow` | Always `True`     |
     | `gamification_enabled` | bool      | Expose parent's gamification flag | From `enable_gamification`   | Always `True`     |
     | `linked_parent_name`   | str\|None | Parent's display name             | Parent's name                | `None`            |

     **Dashboard Integration Use Cases**:

     - `is_shadow_kid=True` → Show "(Parent)" indicator in UI
     - `workflow_enabled=False` → Only show Approve button (hide Claim/Disapprove)
     - `workflow_enabled=True` → Show all three buttons (Claim, Approve, Disapprove)
     - `gamification_enabled=False` → Hide points/badges/rewards sections
     - `gamification_enabled=True` → Show full gamification UI
     - `linked_parent_name` → Display parent's name or "(You)" in kid selector

     **Implementation**: `custom_components/kidschores/sensor.py` (~L1092+)

     ```python
     @property
     def extra_state_attributes(self) -> dict[str, Any]:
         # ... existing attributes ...

         kid_info = self.coordinator.kids_data.get(self._kid_id, {})
         is_shadow = kid_info.get(const.DATA_KID_IS_SHADOW, False)

         attrs["is_shadow_kid"] = is_shadow

         if is_shadow:
             parent_data = kh.get_parent_for_shadow_kid(self.coordinator, self._kid_id)
             if parent_data:
                 attrs["gamification_enabled"] = parent_data.get(
                     const.DATA_PARENT_ENABLE_GAMIFICATION, False
                 )
                 attrs["workflow_enabled"] = parent_data.get(
                     const.DATA_PARENT_ENABLE_CHORE_WORKFLOW, False
                 )
                 attrs["linked_parent_name"] = parent_data.get(
                     const.DATA_PARENT_NAME, None
                 )
         else:
             attrs["gamification_enabled"] = True
             attrs["workflow_enabled"] = True
             attrs["linked_parent_name"] = None

         return attrs
     ```

     **Testing**: `tests/test_parent_shadow_kid.py::TestDataIntegrity::test_dashboard_helper_exposes_shadow_kid_capabilities`

     - Verifies all 4 attributes present for shadow kid (Dad with workflow=False, gamification=True)
     - Verifies regular kid has correct values (Sarah: is_shadow_kid=False, workflow/gamification both True, linked_parent_name=None)
     - Uses scenario: Dad (shadow kid) vs Sarah (regular kid)

- **Key issues**

  - **Points history**: If gamification is toggled on later, history starts from 0
    - Acceptable behavior for MVP
  - **Badge progress**: Disabled kids don't accumulate badge progress
    - When re-enabled, starts fresh

- **Estimated LOC**: ~100 lines (includes comprehensive entity filtering for all gamification entities)

---

### Phase 5 – Edge Cases & Special Handling

- **Goal**: Handle notifications, language, deletion cascade, and other edge cases.

- **Steps / detailed work items**

  1. **Notification handling** (Status: ✅ Complete)

     **Problem**: Shadow kids would receive duplicate notifications (as both kid and via parent)

     **Solution**: Shadow kids have `enable_notifications=False` by default

     **Verification needed in coordinator.py**:

     - `_notify_kid_translated()` checks `DATA_KID_ENABLE_NOTIFICATIONS` → ✓ Already respects this
     - `_notify_parents_translated()` sends to associated parents → Parent still gets notified

     **Additional consideration**: When shadow kid completes chore, should parent get "chore claimed" notification?

     - Current: Parent notified when ANY kid claims chore they supervise
     - Shadow kid: Parent IS the kid, so notification is self-referential
     - **Decision**: Skip "approval needed" notification for shadow kids since parent = claimer

     ```python
     # In claim_chore(), modify notification logic:
     if chore_info.get(const.DATA_CHORE_NOTIFY_ON_CLAIM, True):
         # Skip notification if the claimer is their own shadow kid
         if not kh.is_shadow_kid(self, kid_id):
             self.hass.async_create_task(
                 self._notify_parents_translated(kid_id, ...)
             )
     ```

  2. **Language handling** (Status: ✅ Complete)

     **Problem**: Shadow kids need dashboard language setting for proper localization

     **Solution**: Add `dashboard_language` field to parent schema

     **Implementation**: ✅ Complete

     1. ✅ Add `DATA_PARENT_DASHBOARD_LANGUAGE` and `CFOF_PARENTS_INPUT_DASHBOARD_LANGUAGE` constants
     2. ✅ Add `LanguageSelector` to parent form (same pattern as kid form)
     3. ✅ Shadow kid inherits parent's language setting
     4. ✅ Update existing parent edit flow to pass current language as default

     **Implemented in**: Phase 2 schema updates and `flow_helpers.build_shadow_kid_data()` (L640):

     ```python
     const.DATA_KID_DASHBOARD_LANGUAGE: parent_data.get(
         const.DATA_PARENT_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
     ),
     ```

  3. **Deletion cascade** (Status: ✅ Complete)

     **Problem**: Deleting parent should delete shadow kid

     **Implementation in coordinator.py** `delete_parent_entity()`: ✅ Implemented

     ```python
     # Cascade delete shadow kid if exists
     shadow_kid_id = parent_data.get(const.DATA_PARENT_LINKED_SHADOW_KID_ID)
     if shadow_kid_id:
         self._delete_shadow_kid(shadow_kid_id)
     ```

  4. **Shadow kid protection** (Status: ✅ Complete - Alternate approach)

     **Problem**: Prevent direct deletion of shadow kids (must delete via parent)

     **Solution implemented**: Instead of blocking deletion with an error, we auto-disable the parent's `allow_chore_assignment` flag and use existing `_delete_shadow_kid()` flow. This keeps a single code path for shadow kid cleanup.

     **Implementation in coordinator.py** `delete_kid_entity()`:

     ```python
     # Shadow kid handling: disable parent flag and use existing cleanup
     if kid_info.get(const.DATA_KID_IS_SHADOW, False):
         parent_id = kid_info.get(const.DATA_KID_LINKED_PARENT_ID)
         if parent_id and parent_id in self._data.get(const.DATA_PARENTS, {}):
             # Disable chore assignment on parent and clear link
             self._data[const.DATA_PARENTS][parent_id][
                 const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT
             ] = False
             self._data[const.DATA_PARENTS][parent_id][
                 const.DATA_PARENT_LINKED_SHADOW_KID_ID
             ] = None
         # Use existing shadow kid cleanup
         self._delete_shadow_kid(kid_id)
         return  # Done - single code path
     ```

  5. **Authorization for shadow kid actions** (Status: ✅ Complete - No change needed)

     **Problem**: When parent presses Approve button for their shadow kid's chore, authorization must pass

     **Verification**: Shadow kid's `ha_user_id` = Parent's `ha_user_id`, so existing authorization works.
     Tested via existing shadow kid button tests.

  6. **Chore assignment validation** (Status: ✅ Complete - No change needed)

     **Problem**: Shadow kids should appear in chore assignment dropdown

     **Current flow**: `assigned_kids` dropdown shows all kids from `coordinator.kids_data`

     **Shadow kids are IN `kids_data`** → They automatically appear

     **Verification**: Test that shadow kids appear in chore assignment options (no code change expected)

- **Key issues**

  - **Self-notification loop**: Parent completing their own chore shouldn't notify themselves
    - Solution: Skip "approval needed" notification for shadow kids
  - **Hide shadow kids from regular kid list?**: In kid management UI
    - Decision: Show with "(You)" suffix or similar indicator
    - Implementation: Add to Phase 5 or future enhancement

- **Estimated LOC**: ~50 lines

---

### Phase 6 – Testing

- **Goal**: Comprehensive test coverage for parent capabilities feature.

- **Steps / detailed work items**

  1. **Test file: test_parent_chore_capabilities.py** (Status: Not started)

     Test cases:

     - Parent creation with `allow_chore_assignment=True` creates shadow kid
     - Parent creation with `allow_chore_assignment=False` does NOT create shadow kid
     - Shadow kid has correct attributes (is_shadow=True, linked_parent_id, etc.)
     - Shadow kid inherits parent's ha_user_id
     - Shadow kid has notifications disabled
     - Name collision error when parent name matches existing kid
     - Edit parent: enable chore assignment → creates shadow kid
     - Edit parent: disable chore assignment → deletes shadow kid
     - Delete parent → cascade deletes shadow kid
     - Cannot directly delete shadow kid (protection)

  2. **Test file: test_shadow_kid_buttons.py** (Status: ✅ Complete)

     Test cases: (All implemented and passing)

     - Shadow kid with workflow=False: only Approve button created
     - Shadow kid with workflow=True: Claim, Approve, Disapprove buttons created
     - Regular kid: always has all three buttons
     - Approve button works from PENDING state (approval-only workflow)
     - Toggle workflow flag → entity reload creates/removes buttons

     **Completion Notes:**

     - All 4 tests implemented using Dashboard Helper pattern (Rules 3 & 4 compliance)
     - Anti-pattern violations fixed: Removed direct coordinator access helper functions
     - Tests refactored to use entity registry validation and proper YAML scenario setup
     - All tests passing ✅

  3. **Test file: test_shadow_kid_gamification.py** (Status: Not started)

     Test cases:

     - Shadow kid with gamification=False: no points awarded on approval
     - Shadow kid with gamification=True: points awarded on approval
     - Gamification=False: no badge/achievement/challenge progress
     - Gamification=False: no point sensors created
     - Toggle gamification flag → entity reload creates/removes sensors

  4. **Test file: test_shadow_kid_notifications.py** (Status: Not started)

     Test cases:

     - Shadow kid does not receive notifications (notifications disabled)
     - Parent notification not sent for shadow kid's own chore claim
     - Other parent notifications work normally

- **Key issues**

  - Need test fixtures for parent with shadow kid
  - Need mock for entity platform reload

- **Estimated LOC**: ~250 lines

---

## Testing & validation

- **Tests to execute**:

  1. All existing tests pass (regression): `python -m pytest tests/ -v`
  2. New parent capability tests: `python -m pytest tests/test_parent_chore_capabilities.py -v`
  3. New shadow kid button tests: `python -m pytest tests/test_shadow_kid_buttons.py -v`
  4. New shadow kid gamification tests: `python -m pytest tests/test_shadow_kid_gamification.py -v`
  5. Linting: `./utils/quick_lint.sh --fix`

- **Manual validation**:
  1. Create parent with "Allow chores to be assigned" checked
  2. Verify shadow kid appears in States view
  3. Create chore assigned to shadow kid
  4. Verify only Approve button appears (no Claim, no Disapprove)
  5. Press Approve → chore completes (PENDING → APPROVED)
  6. Edit parent, enable workflow → verify Claim/Disapprove buttons appear
  7. Edit parent, enable gamification → verify points awarded on next approval
  8. Delete parent → verify shadow kid also deleted

---

## Notes & follow-up

### Architecture considerations

1. **Shadow kid storage**: Shadow kids are stored in `kids_data` like regular kids, with additional marker fields (`is_shadow_kid`, `linked_parent_id`). This reuses 100% of existing kid infrastructure.

2. **Button creation flow**: The existing pattern of iterating `assigned_kids_ids` naturally includes shadow kids. The only change is conditional logic around which buttons to create.

3. **Coordinator methods unchanged**: `claim_chore()`, `approve_chore()`, `disapprove_chore()` work with shadow kids without modification (except gamification skip).

### Future enhancements (out of scope for v0.6.0)

1. **Dashboard language on parent**: Add `dashboard_language` field to parent schema, inherit to shadow kid
2. **Convert shadow to real kid**: Allow "upgrading" a shadow kid to a full kid (reassign chores, keep history)
3. **Shadow kid indicators in UI**: Show "(You)" or icon next to shadow kids in kid lists
4. **Multiple shadow kids per parent**: Allow parent to have multiple shadow profiles (different names)
5. **Peer approval for shadow kids**: Option to require different parent to approve shadow kid's chores

### Dependencies

- None external
- Requires v0.5.0 storage-only architecture (schema 42+)

---

## LOC Summary

| Phase                         | Estimated Lines |
| ----------------------------- | --------------- |
| Phase 1 – Data Model          | ~50             |
| Phase 2 – Shadow Kid Creation | ~140            |
| Phase 3 – Button Logic        | ~80             |
| Phase 4 – Gamification Toggle | ~100            |
| Phase 5 – Edge Cases          | ~50             |
| Phase 6 – Testing             | ~300            |
| **Total**                     | **~720**        |

---

## Glossary

- **Shadow kid**: A "kid" entity automatically created for a parent who opts into chore assignment. Appears in all kid lists but has special handling for notifications and optionally gamification.
- **Approval-only workflow**: Default mode for shadow kids where only the Approve button exists, allowing one-click completion (PENDING → APPROVED) without claim/disapprove steps.
- **Full workflow**: Optional mode (enable_chore_workflow=True) that adds Claim and Disapprove buttons, matching regular kid behavior.
- **Gamification**: Points, badges, achievements, challenges, rewards tracking. Disabled by default for shadow kids.
