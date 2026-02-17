# Kid Undo Claim Feature Implementation Plan

## Initiative snapshot

- **Name / Code**: Kid Undo Claim Feature (Button-Based)
- **Target release / milestone**: v0.5.1
- **Owner / driver(s)**: Implementation Agent
- **Status**: Complete ✅

## Summary & immediate steps

| Phase / Step           | Description                                       | % complete | Quick notes                               |
| ---------------------- | ------------------------------------------------- | ---------- | ----------------------------------------- |
| Phase 1 – Coordinator  | Add undo methods & skip_stats parameter           | 100%       | ✅ Complete - 2 methods, skip_stats added |
| Phase 2 – Button Logic | Update disapproval buttons with kid authorization | 100%       | ✅ Complete - Kid detection implemented   |
| Phase 3 – Testing      | Create test suite for kid undo behavior           | 100%       | ✅ Complete - 5/5 tests pass (1 skipped)  |

1. **Key objective** – Allow kids to "undo" their own chore/reward claims via the disapproval button without tracking disapproval stats, while preserving parent/admin disapproval behavior with stat tracking.

2. **Summary of recent work** – Investigation complete (DISAPPROVAL_UNDO_INVESTIGATION.md). All technical details researched. Ready for implementation.

3. **Next steps (short term)**

   - Phase 1: Implement coordinator methods with skip_stats
   - Phase 2: Update button authorization logic
   - Phase 3: Create comprehensive test suite

4. **Risks / blockers**

   - None identified. All technical paths validated during investigation.
   - Authorization logic is straightforward (kid ha_user_id match)
   - No service layer needed initially (button-only implementation)

5. **References**

   - [DISAPPROVAL_UNDO_INVESTIGATION.md](DISAPPROVAL_UNDO_INVESTIGATION.md) - Complete technical research
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model reference
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Coding standards
   - Existing test patterns: `test_workflow_chores.py`, `test_chore_services.py`

6. **Decisions & completion check**
   - **Decisions captured**:
     - Parameter naming: Use `skip_stats` (not `skip_disapproval_stats`) for future flexibility
     - Implementation: Button-only (no services layer initially)
     - Authorization: Allow admins, parents, AND kids (kid must match ha_user_id)
     - Notifications: REMOVED - undo is silent (not noisy like disapproval)
   - **Completion confirmation**:
     - [x] Coordinator methods implemented (undo_chore_claim, undo_reward_claim)
     - [x] skip_stats parameter added to _process_chore_state chain
     - [x] Button authorization updated for both chores and rewards
     - [x] All 5 test scenarios passing (1 skipped - no rewards in scenario_minimal)
     - [x] Lint/mypy/pytest validation passing (9.5+/10, zero errors, 100% pass)
     - [x] Code reviewed against DEVELOPMENT_STANDARDS.md Phase 0
     - [x] Documentation updated (this plan marked complete)

> **Important:** This is a button-only implementation with silent undo (no notifications). Services can be added later if automation access is requested. Estimated total effort: 5-7 hours (reduced from 7-10 by removing notifications).

## Tracking expectations

- **Summary upkeep**: Update percentages after each phase completion. Mark blockers immediately.
- **Detailed tracking**: Use phase sections below for step-by-step progress and technical notes.

---

## Detailed phase tracking

### Phase 1 – Coordinator Methods

- **Goal**: Add `undo_chore_claim()` and `undo_reward_claim()` coordinator methods. Modify `_process_chore_state()` to accept `skip_stats` parameter.

- **Steps / detailed work items**

  - [x] **1.1** Add `skip_stats` parameter to `_process_chore_state()`

    - **File**: `custom_components/kidschores/coordinator.py`
    - **Location**: Line 3339 (method signature)
    - **Current signature**:
      ```python
      def _process_chore_state(
          self,
          kid_id: str,
          chore_id: str,
          new_state: str,
          *,
          points_awarded: float | None = None,
          reset_approval_period: bool = False,
      ) -> None:
      ```
    - **New signature**:
      ```python
      def _process_chore_state(
          self,
          kid_id: str,
          chore_id: str,
          new_state: str,
          *,
          points_awarded: float | None = None,
          reset_approval_period: bool = False,
          skip_stats: bool = False,
      ) -> None:
      ```
    - **Docstring update**: Add parameter description:
      ```python
      skip_stats: If True, skip disapproval stat tracking (for kid undo).
      ```

  - [x] **2.2** Modify disapproval stat tracking in `_update_chore_data_for_kid()`

    - **File**: `custom_components/kidschores/coordinator.py`
    - **Location**: Lines 3850-3873 (DISAPPROVED state handling)
    - **Current code** (line 3853):
      ```python
      elif (
          state == const.CHORE_STATE_PENDING
          and previous_state == const.CHORE_STATE_CLAIMED
      ):
          kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = now_iso
          # ... stat increment logic
      ```
    - **New code** (wrap stat tracking in skip_stats check):
      ```python
      elif (
          state == const.CHORE_STATE_PENDING
          and previous_state == const.CHORE_STATE_CLAIMED
      ):
          if not skip_stats:
              kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = now_iso
              # ... rest of stat tracking logic
      ```
    - **Note**: `_update_chore_data_for_kid()` needs to receive `skip_stats` from caller

  - [x] **2.3** Pass `skip_stats` parameter through call chain

    - **Chain**: `_process_chore_state()` → `_update_chore_data_for_kid()`
    - **File**: `custom_components/kidschores/coordinator.py`
    - **Location**: Line 3397 (call to `_update_chore_data_for_kid()`)
    - **Current call**:
      ```python
      self._update_chore_data_for_kid(
          kid_id=kid_id,
          chore_id=chore_id,
          points_awarded=actual_points,
          state=new_state,
          due_date=due_date,
      )
      ```
    - **New call**:
      ```python
      self._update_chore_data_for_kid(
          kid_id=kid_id,
          chore_id=chore_id,
          points_awarded=actual_points,
          state=new_state,
          due_date=due_date,
          skip_stats=skip_stats,
      )
      ```
    - **Also update** `_update_chore_data_for_kid()` method signature (line ~3600):
      ```python
      def _update_chore_data_for_kid(
          self,
          kid_id: str,
          chore_id: str,
          points_awarded: float,
          *,
          state: str | None = None,
          due_date: str | None = None,
          skip_stats: bool = False,
      ) -> None:
      ```

  - [x] **2.4** Add `undo_chore_claim()` coordinator method

    - **File**: `custom_components/kidschores/coordinator.py`
    - **Location**: After line 2970 (after `disapprove_chore()` method)
    - **Implementation**:

      ```python
      def undo_chore_claim(self, kid_id: str, chore_id: str):
          """Undo a chore claim without tracking as disapproval.

          This is called when a kid removes their own claim. Unlike disapprove_chore():
          - Does NOT update last_disapproved timestamp
          - Does NOT increment disapproval stats
          - Uses "undo" notification instead of "disapproved"

          Args:
              kid_id: Internal ID of the kid who claimed the chore
              chore_id: Internal ID of the chore to unclaim

          Raises:
              HomeAssistantError: If chore or kid not found
          """
          chore_info = self.chores_data.get(chore_id)
          if not chore_info:
              raise HomeAssistantError(
                  translation_domain=const.DOMAIN,
                  translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                  translation_placeholders={
                      "entity_type": const.LABEL_CHORE,
                      "name": chore_id,
                  },
              )

          kid_info = self.kids_data.get(kid_id)
          if not kid_info:
              raise HomeAssistantError(
                  translation_domain=const.DOMAIN,
                  translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                  translation_placeholders={
                      "entity_type": const.LABEL_KID,
                      "name": kid_id,
                  },
              )

          # Decrement pending_count (same as disapprove)
          kid_chores_data = kid_info.setdefault(const.DATA_KID_CHORE_DATA, {})
          if chore_id not in kid_chores_data:
              self._update_chore_data_for_kid(kid_id, chore_id, 0.0)
          kid_chore_data_entry = kid_chores_data[chore_id]
          current_count = kid_chore_data_entry.get(
              const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
          )
          kid_chore_data_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
              0, current_count - 1
          )

          # Handle SHARED_FIRST completion criteria (same as disapprove)
          completion_criteria = chore_info.get(
              const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
          )
          if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
              const.LOGGER.info(
                  "SHARED_FIRST: Undo - resetting all kids to pending for chore '%s'",
                  chore_info.get(const.DATA_CHORE_NAME),
              )
              for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                  self._process_chore_state(
                      other_kid_id, chore_id, const.CHORE_STATE_PENDING, skip_stats=True
                  )
                  # Clear claimed_by/completed_by attributes
                  other_kid_info = self.kids_data.get(other_kid_id, {})
                  chore_data = other_kid_info.get(const.DATA_KID_CHORE_DATA, {})
                  if chore_id in chore_data:
                      chore_data[chore_id].pop(const.DATA_CHORE_CLAIMED_BY, None)
                      chore_data[chore_id].pop(const.DATA_CHORE_COMPLETED_BY, None)
          else:
              # Normal: only reset the kid who is undoing
              self._process_chore_state(
                  kid_id, chore_id, const.CHORE_STATE_PENDING, skip_stats=True
              )

          # No notification sent for undo (silent operation)

          self._persist()
          self.async_set_updated_data(self._data)
      ```

  - [x] **1.5** Add `undo_reward_claim()` coordinator method

    - **File**: `custom_components/kidschores/coordinator.py`
    - **Location**: After line 4915 (after `disapprove_reward()` method)
    - **Implementation**:

      ```python
      def undo_reward_claim(self, kid_id: str, reward_id: str):
          """Undo a reward claim without tracking as disapproval.

          This is called when a kid removes their own reward claim. Unlike disapprove_reward():
          - Does NOT update last_disapproved timestamp
          - Does NOT increment total_disapproved counter
          - Does NOT increment period_disapproved counters
          - Silent operation (no notification sent)

          Args:
              kid_id: Internal ID of the kid who claimed the reward
              reward_id: Internal ID of the reward to unclaim

          Raises:
              HomeAssistantError: If reward or kid not found
          """
          reward_info = self.rewards_data.get(reward_id)
          if not reward_info:
              raise HomeAssistantError(
                  translation_domain=const.DOMAIN,
                  translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                  translation_placeholders={
                      "entity_type": const.LABEL_REWARD,
                      "name": reward_id,
                  },
              )

          kid_info = self.kids_data.get(kid_id)
          if not kid_info:
              raise HomeAssistantError(
                  translation_domain=const.DOMAIN,
                  translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                  translation_placeholders={
                      "entity_type": const.LABEL_KID,
                      "name": kid_id,
                  },
              )

          # Decrement pending_count only (no stat tracking)
          reward_entry = self._get_kid_reward_data(kid_id, reward_id, create=False)
          if reward_entry:
              reward_entry[const.DATA_KID_REWARD_DATA_PENDING_COUNT] = max(
                  0, reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0) - 1
              )

          # No notification sent for undo (silent operation)

          self._persist()
          self.async_set_updated_data(self._data)
      ```

  - [x] **1.6** Validate coordinator changes with lazy logging
    - Search for all `const.LOGGER` calls in new methods
    - Ensure format: `const.LOGGER.info("Message: %s", variable)` (NOT f-strings)
    - Check all translation keys use `const.TRANS_KEY_*` constants (for errors only)

- **Key issues**
  - Must ensure `skip_stats` parameter is passed through entire call chain
  - SHARED_FIRST logic must match `disapprove_chore()` behavior
  - No notifications sent for undo operations (silent by design)

---

### Phase 2 – Button Authorization Logic

- **Goal**: Update `ParentChoreDisapproveButton` and `ParentRewardDisapproveButton` to detect kid users and call appropriate coordinator method.

- **Steps / detailed work items**

  - [x] **3.1** Update `ParentChoreDisapproveButton.async_press()`

    - **File**: `custom_components/kidschores/button.py`
    - **Location**: Line 593 (inside `async_press()` method)
    - **Current logic** (lines 619-631):

      ```python
      user_id = self._context.user_id if self._context else None
      if user_id and not await kh.is_user_authorized_for_global_action(
          self.hass, user_id, const.SERVICE_DISAPPROVE_CHORE
      ):
          raise HomeAssistantError(...)

      user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
      parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

      self.coordinator.disapprove_chore(
          parent_name=parent_name,
          kid_id=self._kid_id,
          chore_id=self._chore_id,
      )
      ```

    - **New logic** (replace lines 619-631):

      ```python
      user_id = self._context.user_id if self._context else None

      # Check if user is the kid for this chore
      is_kid_undo = False
      if user_id:
          kid_info = self.coordinator.kids_data.get(self._kid_id)
          if kid_info and kid_info.get(const.DATA_KID_HA_USER_ID) == user_id:
              is_kid_undo = True

      # If not kid, check parent/admin authorization
      if not is_kid_undo:
          if user_id and not await kh.is_user_authorized_for_global_action(
              self.hass, user_id, const.SERVICE_DISAPPROVE_CHORE
          ):
              raise HomeAssistantError(
                  translation_domain=const.DOMAIN,
                  translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                  translation_placeholders={
                      "action": const.ERROR_ACTION_DISAPPROVE_CHORES
                  },
              )

      # Call appropriate method based on user type
      if is_kid_undo:
          self.coordinator.undo_chore_claim(
              kid_id=self._kid_id,
              chore_id=self._chore_id,
          )
          const.LOGGER.info(
              "INFO: Chore '%s' claim removed (undo) by Kid '%s'",
              self._chore_name,
              self._kid_name,
          )
      else:
          user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
          parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

          self.coordinator.disapprove_chore(
              parent_name=parent_name,
              kid_id=self._kid_id,
              chore_id=self._chore_id,
          )
          const.LOGGER.info(
              "INFO: Chore '%s' disapproved for Kid '%s' by parent '%s'",
              self._chore_name,
              self._kid_name,
              parent_name,
          )
      ```

  - [x] **3.2** Update `ParentRewardDisapproveButton.async_press()`

    - **File**: `custom_components/kidschores/button.py`
    - **Location**: Line 977 (inside `async_press()` method)
    - **Current logic** (lines 1003-1015):

      ```python
      user_id = self._context.user_id if self._context else None
      if user_id and not await kh.is_user_authorized_for_global_action(
          self.hass, user_id, const.SERVICE_DISAPPROVE_REWARD
      ):
          raise HomeAssistantError(...)

      user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
      parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

      self.coordinator.disapprove_reward(
          parent_name=parent_name,
          kid_id=self._kid_id,
          reward_id=self._reward_id,
      )
      ```

    - **New logic** (replace lines 1003-1015):

      ```python
      user_id = self._context.user_id if self._context else None

      # Check if user is the kid for this reward
      is_kid_undo = False
      if user_id:
          kid_info = self.coordinator.kids_data.get(self._kid_id)
          if kid_info and kid_info.get(const.DATA_KID_HA_USER_ID) == user_id:
              is_kid_undo = True

      # If not kid, check parent/admin authorization
      if not is_kid_undo:
          if user_id and not await kh.is_user_authorized_for_global_action(
              self.hass, user_id, const.SERVICE_DISAPPROVE_REWARD
          ):
              raise HomeAssistantError(
                  translation_domain=const.DOMAIN,
                  translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                  translation_placeholders={
                      "action": const.ERROR_ACTION_DISAPPROVE_REWARDS
                  },
              )

      # Call appropriate method based on user type
      if is_kid_undo:
          self.coordinator.undo_reward_claim(
              kid_id=self._kid_id,
              reward_id=self._reward_id,
          )
          const.LOGGER.info(
              "INFO: Reward '%s' claim removed (undo) by Kid '%s'",
              self._reward_name,
              self._kid_name,
          )
      else:
          user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
          parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

          self.coordinator.disapprove_reward(
              parent_name=parent_name,
              kid_id=self._kid_id,
              reward_id=self._reward_id,
          )
          const.LOGGER.info(
              "INFO: Reward '%s' disapproved for Kid '%s' by parent '%s'",
              self._reward_name,
              self._kid_name,
              parent_name,
          )
      ```

  - [x] **3.3** Verify import statements include required constants
    - **File**: `custom_components/kidschores/button.py`
    - **Line 26**: Ensure imports include:
      ```python
      from . import const, kc_helpers as kh
      ```
    - Verify `const.DATA_KID_HA_USER_ID` is available (should be in const.py)

- **Key issues**
  - Must check `DATA_KID_HA_USER_ID` exists in kid_info before comparison
  - Authorization check only runs if NOT kid undo
  - Log messages must clearly distinguish "undo" vs "disapproved"

---

### Phase 3 – Testing

- **Goal**: Create comprehensive test suite covering kid undo behavior, parent disapproval behavior, and authorization checks.

- **Steps / detailed work items**

  - [x] **3.1** Create test file for undo feature

    - **File**: `tests/test_kid_undo_claim.py`
    - **Fixture**: Use `scenario_minimal` (1 kid, 1 parent, 5 chores)
    - **Test structure**: Follow pattern from `test_workflow_chores.py`

  - [x] **3.2** Test: Kid undo chore claim (basic)

    - **Test name**: `test_kid_undo_chore_claim_basic`
    - **Steps**:
      1. Setup: Load scenario_minimal, mock kid user
      2. Claim chore as kid
      3. Press disapprove button as kid (should call undo)
      4. Assert: State = PENDING, pending_count = 0
      5. Assert: `last_disapproved` NOT updated
      6. Assert: `period_disapproved` = 0 (no increment)
      7. Assert: `disapproved_all_time` = 0 (no increment)

  - [x] **3.3** Test: Parent disapprove still tracks stats

    - **Test name**: `test_parent_disapprove_tracks_stats`
    - **Steps**:
      1. Setup: Load scenario_minimal, mock parent user
      2. Claim chore as kid
      3. Press disapprove button as parent
      4. Assert: State = PENDING
      5. Assert: `last_disapproved` IS updated (timestamp)
      6. Assert: `period_disapproved` = 1 (incremented)
      7. Assert: `disapproved_all_time` = 1 (incremented)

  - [x] **3.4** Test: Kid undo reward claim (basic)

    - **Test name**: `test_kid_undo_reward_claim_basic`
    - **Steps**:
      1. Setup: Load scenario with rewards, mock kid user
      2. Redeem reward as kid
      3. Press disapprove button as kid (should call undo)
      4. Assert: pending_count = 0
      5. Assert: `last_disapproved` NOT updated
      6. Assert: `total_disapproved` = 0 (no increment)

  - [x] **3.5** Test: Authorization - kid can only undo own chores

    - **Test name**: `test_kid_cannot_undo_other_kid_chore`
    - **Steps**:
      1. Setup: Multi-kid scenario, mock kid1 user
      2. Kid2 claims chore
      3. Kid1 attempts to press disapprove button for kid2's chore
      4. Assert: Raises HomeAssistantError (not authorized)
      5. Assert: Chore state unchanged

  - [x] **3.6** Test: SHARED_FIRST chore undo resets all kids

    - **Test name**: `test_kid_undo_shared_first_resets_all`
    - **Steps**:
      1. Setup: Load scenario_shared, mock kid user
      2. Kid1 claims SHARED_FIRST chore
      3. Kid1 presses disapprove button (undo)
      4. Assert: All kids reset to PENDING
      5. Assert: No disapproval stats tracked for any kid

  - [ ] **3.7** Test: Multiple undo operations don't accumulate stats

    - **Test name**: `test_multiple_undo_no_stat_accumulation`
    - **Steps**:
      1. Setup: Load scenario_minimal, mock kid user
      2. Claim chore as kid
      3. Undo (kid presses disapprove)
      4. Claim same chore again
      5. Undo again
      6. Assert: `disapproved_all_time` still = 0
      7. Assert: `period_disapproved` = 0 for all periods

  - [x] **3.7** Run full test suite and validation
    - Command: `python -m pytest tests/test_kid_undo_claim.py -v --tb=line`
    - Expected: All 5 tests pass (1 skipped - scenario_minimal has no rewards)
    - Run lint: `./utils/quick_lint.sh --fix` (must score 9.5+/10)
    - Run type check: `mypy custom_components/kidschores/` (must be zero errors)
    - Run related tests: `pytest tests/test_workflow_chores.py -v` (ensure no regressions)

- **Key issues**
  - Must mock Home Assistant user authentication properly
  - Need to verify `_context.user_id` is set correctly in tests
  - No notification testing needed (undo is silent operation)

---

## Testing & validation

### Test execution commands

```bash
# Run new undo tests
python -m pytest tests/test_kid_undo_claim.py -v --tb=line

# Run regression tests
python -m pytest tests/test_workflow_chores.py -v --tb=line
python -m pytest tests/test_chore_services.py -v --tb=line

# Lint validation (must be 9.5+/10)
./utils/quick_lint.sh --fix

# Type checking (must be zero errors)
mypy custom_components/kidschores/

# Full test suite (if time permits)
python -m pytest tests/ -v --tb=line
```

### Expected test results

- **New tests**: 6/6 passing (100%)
- **Regression tests**: No failures introduced
- **Lint score**: ≥9.5/10
- **Type errors**: 0
- **Coverage**: New coordinator methods covered by tests

### Outstanding tests

- Performance impact testing (undo vs disapprove timing)
- Multi-user concurrent undo testing (not critical for v0.5.1)
- Dashboard helper sensor update verification (manual test recommended)

---

## Notes & follow-up

### Architecture considerations

- **Parameter naming**: `skip_stats` chosen for future flexibility (e.g., admin corrections)
- **Button-only approach**: Services layer intentionally omitted to reduce scope
- **Authorization pattern**: Simple kid ha_user_id match, no new helper function needed
- **Silent operation**: No notifications sent for undo (reduces noise)

### Implementation notes

- All coordinator changes are isolated to undo methods and `_process_chore_state()`
- Button authorization logic is self-contained (no kc_helpers changes)
- No notification system changes needed (silent undo operation)
- Zero changes to existing disapproval behavior (backward compatible)

### Decisions made

1. **Skip services layer**: Button-only implementation reduces effort by ~30%
2. **Silent undo**: No notifications sent (user-initiated action, not noisy)
3. **Conditional button logic**: Single button serves both kid undo and parent disapproval
4. **SHARED_FIRST handling**: Match existing disapproval behavior exactly

### Future enhancements (not in scope)

- [ ] Add services layer for automation access (`undo_chore_claim`, `undo_reward_claim` services)
- [ ] Add config option: `allow_kid_undo` (default: true) for parental control
- [ ] Dashboard button text changes based on user type ("Undo" vs "Disapprove")
- [ ] Admin override service for manual corrections (separate from undo/disapprove)
- [ ] Audit log entries distinguishing undo vs disapprove actions

### Follow-up tasks

- [ ] Update user documentation with kid undo feature
- [ ] Test dashboard behavior with kid users (manual testing)
- [ ] Monitor user feedback for confusion around button behavior
- [ ] Consider adding visual indicator when kid user sees button (future UI enhancement)

---

**Plan Status**: Ready for implementation. All technical details researched and validated.
