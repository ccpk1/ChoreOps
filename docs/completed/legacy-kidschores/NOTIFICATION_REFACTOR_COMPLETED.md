# Initiative Plan: Notification System Refactor

## Initiative snapshot

- **Name / Code**: NOTIF-REFACTOR-001 - Notification System Consolidation & Reliability
- **Target release / milestone**: v0.6.0 (Post-v0.5.0 stabilization)
- **Owner / driver(s)**: KidsChores Maintainers
- **Status**: Not started (Deep dive analysis complete)

## Summary & immediate steps

| Phase / Step               | Description                                          | % complete | Quick notes                             |
| -------------------------- | ---------------------------------------------------- | ---------- | --------------------------------------- |
| Phase 0 – Immediate Fixes  | Event listener fix, tag consistency, reminder bugs   | 100%       | ALL DONE - event, state, tags, datetime |
| Phase 1 – Helper Creation  | Add action builder & extra_data helper functions     | 100%       | DONE - 3 helpers added                  |
| Phase 2 – Coordinator DRY  | Replace 9 duplicate action blocks with helpers       | 100%       | DONE - all 7 locations refactored       |
| Phase 3 – ParsedAction     | Add dataclass + structured parser                    | 100%       | DONE - dataclass + parser added         |
| Phase 4 – Handler Refactor | Update action_handler to use ParsedAction            | 100%       | DONE - removed type ignores, cleaner    |
| Phase 5 – Testing          | Unit tests for new helpers + parsing                 | 100%       | DONE - 36 tests, all passing            |
| Phase 6 – User Guide       | Create comprehensive notification user guide in wiki | EXEMPT     | Existing wiki docs sufficient           |
| Phase 7 – Tag System Fix   | Fix notification tag collisions + add clear function | 100% ✅    | All steps complete                      |

1. **Key objective** – Eliminate ~100 lines of duplicated notification code, improve type safety, fix identified issues, and create a maintainable foundation with user documentation.

2. **Summary of recent work**
   - **COMPLETED**: Comprehensive deep dive audit of entire notification system
   - Identified 17 notification events across 4 categories (chores, rewards, gamification, reminders)
   - Documented 9 locations with duplicated action button building code
   - Documented fragile string parsing in notification_action_handler.py
   - Fixed missing parent notification in `disapprove_chore()` (separate bug fix)
   - **Identified 6 issues/gaps requiring attention** (see Issues section below)

3. **Next steps (short term)**
   - [x] ~~Review and approve identified issues list~~ **DONE** (2026-01-16)
   - [x] ~~Approve scope: Full 6-phase refactor~~ **APPROVED** (2026-01-16)
   - [x] ~~Fix Issue #3 (event listener unload)~~ **FIXED** (2026-01-16)
   - [x] ~~Fix Issue #4 (reminder state bug - used shared state instead of per-kid state)~~ **FIXED** (2026-01-16)
   - [x] ~~Fix Issue #5 (add per-chore reminder setting)~~ **FIXED** (2026-01-16)
   - [x] ~~Add consistent tag usage to reminders~~ **DONE** (2026-01-16)
   - [x] ~~Add tag to overdue notifications~~ **DONE** (2026-01-16)
   - [x] ~~Add localized date/time formatting helper~~ **DONE** (2026-01-16)
   - [x] ~~Complete Phase 1 helper functions~~ **DONE** (2026-01-16)
   - [x] ~~Complete Phase 2 - Replace duplicated action blocks with helpers~~ **DONE** (2026-01-16)
   - [x] ~~Complete Phase 3 - Add ParsedAction dataclass~~ **DONE** (2026-01-16)
   - [x] ~~Complete Phase 4 - Update action_handler to use ParsedAction~~ **DONE** (2026-01-16)
   - [x] ~~Complete Phase 5 - Unit tests for new helpers + parsing~~ **DONE** (2026-01-16)
   - [x] ~~Phase 6 - User-facing documentation~~ **EXEMPT** (Existing wiki docs sufficient)
   - [x] ~~Complete Phase 7 - Fix notification tag collisions~~ **DONE** (2026-01-17)

4. **Risks / blockers**
   - **Risk**: ~~Changes to action format could break existing notifications~~ → **RESOLVED**: No versioning needed, v0.5.0 beta allows clean break
   - **Mitigation**: None needed - v0.5.0 beta has no legacy impact
   - **Blocker**: ~~Should wait until v0.5.0 is released~~ → **RESOLVED**: Can fix in beta

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model and storage patterns
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Coding conventions
   - [notification_helper.py](../../custom_components/kidschores/notification_helper.py) - Current helper module
   - [notification_action_handler.py](../../custom_components/kidschores/notification_action_handler.py) - Action callback handler
   - [coordinator.py](../../custom_components/kidschores/coordinator.py) - 30+ notification calls
   - [en_notifications.json](../../custom_components/kidschores/translations_custom/en_notifications.json) - Translation templates

6. **Decisions & completion check**
   - **Decisions captured**:
     - [x] Scope decision: **Full 6-phase refactor approved**
     - [x] Format versioning: **Skip versioning** - v0.5.0 beta allows clean break
     - [x] Migration strategy: **No migration needed** - beta has no legacy
     - [x] Issue #3 priority: **Fixed immediately** (event listener unload)
     - [x] Issue #4 priority: **Fixed immediately** (reminder state bug - per-kid state)
     - [x] Issue #5 priority: **Fixed immediately** (per-chore reminder setting)
     - [x] REMIND_30 behavior: **Should use same tag** to replace original notification
     - [x] Date/time formatting: **Add localized short format helper** based on system timezone
     - [x] Reminder tags: **Added** `tag_type` to both chore and reward reminders
   - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, user guide) before requesting owner approval to mark initiative done.

---

## Detailed phase tracking

### Phase 0 – Immediate Fixes (v0.5.0 Beta)

- **Goal**: Fix critical issues that can be addressed immediately in v0.5.0 beta.
- **Steps / detailed work items**
  1. - [x] **DONE** Fix Issue #3: Wrap event listener in `entry.async_on_unload()`
     - File: `custom_components/kidschores/__init__.py` line 248
     - Changed: `hass.bus.async_listen(...)` → `entry.async_on_unload(hass.bus.async_listen(...))`
  2. - [x] **DONE** Fix Issue #4: Reminder state bug - used shared state instead of per-kid state
     - File: `custom_components/kidschores/coordinator.py` lines 11575-11650
     - Changed: `chore_info.get(const.DATA_CHORE_STATE)` → `self._get_kid_chore_data(kid_id, chore_id)`
     - Added per-kid state check using `DATA_KID_CHORE_DATA_STATE`
     - Reminders now only send for `PENDING` and `OVERDUE` states (not `CLAIMED`, `APPROVED`, `COMPLETED_BY_OTHER`)
  3. - [x] **DONE** Fix Issue #5: Add per-chore reminder notification setting
     - Added `DATA_CHORE_NOTIFY_ON_REMINDER` constant in `const.py`
     - Added `CFOF_CHORES_INPUT_NOTIFY_ON_REMINDER` constant in `const.py`
     - Added `DEFAULT_NOTIFY_ON_REMINDER = True` in `const.py`
     - Updated `_build_notification_defaults()` in `flow_helpers.py`
     - Updated `build_chore_schema()` SelectSelector in `flow_helpers.py`
     - Updated `build_chores_data()` extraction in `flow_helpers.py`
     - Updated `build_default_chore_data()` in `kc_helpers.py`
     - Added translation in `translations/en.json`
  4. - [x] **DONE** Add `tag_type` parameter to `remind_in_minutes()` calls
     - File: `custom_components/kidschores/coordinator.py`
     - Chore reminders: Added `tag_type=const.NOTIFY_TAG_TYPE_PENDING`
     - Reward reminders: Added `tag_type=const.NOTIFY_TAG_TYPE_REWARDS`
  5. - [x] **DONE** Add `tag_type` parameter to `_notify_overdue_chore()` calls
     - File: `custom_components/kidschores/coordinator.py` lines 9140-9160
     - Added `tag_type=const.NOTIFY_TAG_TYPE_PENDING` to parent overdue notification
  6. - [x] **DONE** Add `format_short_datetime()` helper
     - File: `custom_components/kidschores/kc_helpers.py`
     - Converts UTC datetime to local timezone with user-friendly format
     - Format: "Jan 16, 3:00 PM" (English) or "Jan 16, 15:00" (24-hour for other languages)
  7. - [x] **DONE** Replace raw `isoformat()` calls with `format_short_datetime()` in notifications
     - File: `custom_components/kidschores/coordinator.py`
     - Updated kid and parent overdue notifications to use friendly date format
- **Key issues**
  - None - Phase 0 complete ✅

### Phase 1 – Helper Creation

- **Goal**: Create reusable helper functions in `notification_helper.py` to eliminate action button and extra_data duplication.
- **Steps / detailed work items**
  1. - [x] **DONE** Add `build_chore_actions(kid_id: str, chore_id: str) -> list[dict[str, str]]`
     - File: `custom_components/kidschores/notification_helper.py`
     - Returns list with Approve, Disapprove, Remind action dicts
     - Uses existing `const.ACTION_*` and `const.TRANS_KEY_NOTIF_ACTION_*` constants
  2. - [x] **DONE** Add `build_reward_actions(kid_id: str, reward_id: str, notif_id: str | None = None) -> list[dict[str, str]]`
     - File: `custom_components/kidschores/notification_helper.py`
     - Handles optional `notif_id` suffix for reward tracking
  3. - [x] **DONE** Add `build_extra_data(kid_id: str, chore_id: str | None = None, reward_id: str | None = None, notif_id: str | None = None) -> dict[str, str]`
     - File: `custom_components/kidschores/notification_helper.py`
     - Consistent context data building for all notification types
  4. - [x] ~~Add import for new helpers in `coordinator.py`~~ N/A - helpers called from notification_helper.py only
  5. - [x] **DONE** Run quality gates: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/`
     - All checks passed, 16/16 tests passed
- **Key issues**
  - None - Phase 1 complete ✅

### Phase 2 – Coordinator DRY

- **Goal**: Replace all 9 duplicated action-building blocks in coordinator.py with helper calls.
- **Steps / detailed work items**
  1. - [x] **DONE** Replace action building in `claim_chore()` (line ~3103)
     - Changed: `actions = [...]` → `actions = build_chore_actions(kid_id, chore_id)`
  2. - [x] **DONE** Replace action building in `approve_chore()` aggregated pending (line ~3586)
     - Changed: `actions = [...]` → `actions = build_chore_actions(kid_id, latest_chore_id)`
  3. - [x] **DONE** Replace action building in `disapprove_chore()` aggregated pending (line ~3735)
     - Changed: `actions = [...]` → `actions = build_chore_actions(kid_id, latest_chore_id)`
  4. - [x] **DONE** Replace action building in `_check_overdue_chores()` (line ~9104)
     - Changed: `actions = [...]` → `actions = build_chore_actions(kid_id, chore_id)`
  5. - [x] **DONE** Replace action building in `remind_in_minutes()` chores (line ~11595)
     - Changed: `actions = [...]` → `actions = build_chore_actions(kid_id, chore_id)`
  6. - [x] **DONE** Replace action building in `claim_reward()` (line ~5625)
     - Changed: `actions = [...]` → `actions = build_reward_actions(kid_id, reward_id, notif_id)`
  7. - [x] **DONE** Replace action building in `remind_in_minutes()` rewards (line ~11643)
     - Changed: `actions = [...]` → `actions = build_reward_actions(kid_id, reward_id)`
  8. - [x] **DONE** Replace all `extra_data = {...}` blocks with `build_extra_data()` calls
     - 7 locations updated (combined with action replacements above)
  9. - [x] **DONE** Run quality gates: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/`
     - All checks passed, mypy: "Success: no issues found in 20 source files"
  10. - [x] **DONE** Run tests: `pytest tests/test_workflow_notifications.py -v`
  - All 16 notification tests passed
  - Full test suite: 690 passed, 2 deselected
- **Key issues**
  - None - Phase 2 complete ✅

### Phase 3 – ParsedAction Dataclass

- **Goal**: Create type-safe structured parsing for notification action strings.
- **Steps / detailed work items**
  1. - [x] **DONE** Create `ParsedAction` dataclass in `notification_helper.py`
     - Added dataclass with `action_type`, `kid_id`, `entity_id`, `notif_id` fields
     - Added `is_chore_action`, `is_reward_action`, `is_reminder_action` properties
     - Added `chore_id` and `reward_id` computed properties for convenience
  2. - [x] **DONE** Create `parse_notification_action(action_field: str) -> ParsedAction | None`
     - Returns `None` for invalid/malformed action strings
     - Handles both 3-part (chores) and 4-part (rewards) formats
     - Validates action type against known constants
     - Logs warnings for unrecognized formats
  3. - [x] **DONE** Add dataclass import at top of `notification_helper.py`
     - Added `from dataclasses import dataclass`
  4. - [x] N/A - Export new types in module `__all__` if applicable
     - Module doesn't use `__all__`, functions are accessed via direct import
  5. - [x] **DONE** Run quality gates: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/`
     - All checks passed, mypy: "Success: no issues found in 20 source files"
- **Key issues**
  - None - Phase 3 complete ✅

### Phase 4 – Handler Refactor

- **Goal**: Update `notification_action_handler.py` to use `ParsedAction` for type-safe parsing.
- **Steps / detailed work items**
  1. - [x] **DONE** Import `ParsedAction` and `parse_notification_action` in handler
     - Added `from .notification_helper import parse_notification_action`
  2. - [x] **DONE** Replace manual string splitting with `parse_notification_action()` call
     - Removed ~40 lines of manual parsing code
     - Replaced with single `parse_notification_action(action_field)` call
  3. - [x] **DONE** Remove 4x `# type: ignore[arg-type]` suppressions
     - All 4 suppressions removed - ParsedAction provides typed fields
     - Code now fully type-safe with no ignores
  4. - [x] **DONE** Update coordinator method calls to use parsed values
     - Chore: `parsed.kid_id`, `parsed.entity_id`
     - Reward: `parsed.kid_id`, `parsed.entity_id`, `parsed.notif_id`
     - Reminder: `parsed.chore_id`, `parsed.reward_id` (computed properties)
  5. - [x] **DONE** Run quality gates: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/`
     - All checks passed, mypy: "Success: no issues found in 20 source files"
  6. - [x] **DONE** Run tests: `pytest tests/test_workflow_notifications.py -v`
     - All 16 notification tests passed
     - Full test suite: 690 passed, 2 deselected
- **Key issues**
  - None - Phase 4 complete ✅

### Phase 5 – Testing (100% ✅)

**Status**: ✅ Complete (36 tests, all passing)

- **Goal**: Add comprehensive unit tests for new notification helpers and parsing logic.
- **Steps / detailed work items**
  1. - [x] Create `tests/test_notification_helpers.py` (new file)
  2. - [x] Add tests for `build_chore_actions()`
     - Test: Returns 3 action dicts
     - Test: Action strings have correct format `ACTION|kid_id|chore_id`
     - Test: Uses correct translation keys
  3. - [x] Add tests for `build_reward_actions()`
     - Test: Returns 3 action dicts
     - Test: Action strings include notif_id when provided
     - Test: Action strings omit notif_id suffix when None
  4. - [x] Add tests for `build_extra_data()`
     - Test: Includes only provided keys
     - Test: Handles all None optional params
  5. - [x] Add tests for `parse_notification_action()`
     - Test: Parses valid chore action (3 parts)
     - Test: Parses valid reward action (4 parts)
     - Test: Returns None for empty string
     - Test: Returns None for malformed string (too few parts)
     - Test: Returns None for unknown action type
  6. - [x] Add tests for `ParsedAction` properties
     - Test: `is_chore_action` returns True for APPROVE_CHORE, DISAPPROVE_CHORE
     - Test: `is_reward_action` returns True for APPROVE_REWARD, DISAPPROVE_REWARD
     - Test: `is_reminder_action` returns True for REMIND_30
  7. - [x] Run full test suite: `pytest tests/ -v --tb=line` → 726 passed
  8. - [x] Verify lint/type: `./utils/quick_lint.sh --fix` → All checks passed
- **Key issues**
  - Tests use direct function calls (approved exception - pure functions, no hass deps)
  - No duplication with `test_workflow_notifications.py` (16 workflow tests remain distinct)
- **Results**
  - 36 tests added for 5 helper functions/classes
  - 100% type coverage (mypy clean)
  - All lint checks passing

---

## Notification Event Reference

### Complete Inventory (17 Events)

| Category         | Event           | Trigger Method            | Recipients   | Has Actions | coordinator.py Lines |
| ---------------- | --------------- | ------------------------- | ------------ | ----------- | -------------------- |
| **Chore**        | Assigned        | `assign_chore_to_kid()`   | Kid          | ❌          | 1335-1345            |
| **Chore**        | Claimed         | `claim_chore()`           | Parents      | ✅          | 3103-3150            |
| **Chore**        | Approved        | `approve_chore()`         | Kid, Parents | ❌          | 3554-3620            |
| **Chore**        | Disapproved     | `disapprove_chore()`      | Kid, Parents | ❌          | 3708-3780            |
| **Chore**        | Overdue         | `_check_overdue_chores()` | Kid, Parents | ✅          | 9100-9160            |
| **Chore**        | Due Soon        | `_due_soon_reminder()`    | Kid          | ❌          | 9280-9320            |
| **Reward**       | Claimed         | `claim_reward()`          | Parents      | ✅          | 5625-5658            |
| **Reward**       | Approved        | `approve_reward()`        | Kid          | ❌          | 5859-5870            |
| **Reward**       | Disapproved     | `disapprove_reward()`     | Kid          | ❌          | 5910-5920            |
| **Reward**       | Reminder        | `remind_in_minutes()`     | Parents      | ✅          | 11643-11676          |
| **Gamification** | Badge Earned    | `award_badge()`           | Kid, Parents | ❌          | 6725-6746            |
| **Gamification** | Penalty Applied | `apply_penalty()`         | Kid          | ❌          | 8437-8450            |
| **Gamification** | Bonus Applied   | `apply_bonus()`           | Kid          | ❌          | 8494-8507            |
| **Gamification** | Achievement     | `award_achievement()`     | Kid, Parents | ❌          | 8669-8695            |
| **Gamification** | Challenge Done  | `award_challenge()`       | Kid, Parents | ❌          | 8825-8850            |
| **Reminder**     | Chore Reminder  | `remind_in_minutes()`     | Parents      | ✅          | 11595-11625          |
| **Reminder**     | Reward Reminder | `remind_in_minutes()`     | Parents      | ✅          | 11643-11676          |

### Action Button Locations (9 Duplications)

| Location | Method                            | Entity Type | Line Range   |
| -------- | --------------------------------- | ----------- | ------------ |
| 1        | `claim_chore()`                   | Chore       | ~3103-3120   |
| 2        | `approve_chore()` (aggregated)    | Chore       | ~3586-3600   |
| 3        | `disapprove_chore()` (aggregated) | Chore       | ~3735-3750   |
| 4        | `_check_overdue_chores()`         | Chore       | ~9104-9120   |
| 5        | `remind_in_minutes()`             | Chore       | ~11595-11610 |
| 6        | `claim_reward()`                  | Reward      | ~5625-5640   |
| 7        | `remind_in_minutes()`             | Reward      | ~11643-11658 |

---

## Testing & validation

- **Tests to execute**:
  - ✅ `pytest tests/test_notification_helpers.py -v` → 36 passed
  - ✅ `pytest tests/test_workflow_notifications.py -v` → 16 passed (no regressions)
  - ✅ `pytest tests/ -v --tb=line` → 726 passed, 2 deselected
- **Quality gates**:
  - ✅ `./utils/quick_lint.sh --fix` → All checks passed
  - ✅ `mypy custom_components/kidschores/` → Zero errors
- **Outstanding tests**: None - All test coverage complete
- **CI verification**: All tests passing ✅

---

## Notes & follow-up

### Known Issues Discovered During Documentation

1. **Overdue Chore Notification Action Buttons (Design Inconsistency)** - ✅ **WILL BE FIXED IN PHASE 7**
   - **Issue**: `_notify_overdue_chore()` sends action buttons (Approve/Disapprove/Remind) but chore hasn't been claimed yet
   - **Location**: `coordinator.py` lines 9050 (uses `build_chore_actions()`)
   - **Why Invalid**: Approve/Disapprove only make sense for claimed chores awaiting approval
   - **Solution**: Remove action buttons entirely (overdue is informational only)
   - **Status**: Phase 7 Step 8 will fix this

2. **Notification Tag Collision Bug** - ✅ **WILL BE FIXED IN PHASE 7**
   - **Issue**: Tags use only `kid_id`, so multiple chores for same kid replace each other
   - **Solution**: Change tags to `{chore_id}-{kid_id}` format
   - **Status**: Phase 7 Steps 1-10 will fix this

3. **Missing Clear Function** - ✅ **WILL BE FIXED IN PHASE 7**
   - **Issue**: Dashboard approvals leave stale notification on phone
   - **Solution**: Add `clear_notification_for_parents()` helper
   - **Status**: Phase 7 Steps 11-15 will fix this

### Architectural Decisions Needed

1. **Action String Format Versioning**
   - **Option A**: Keep current format `ACTION|kid_id|entity_id[|notif_id]`
   - **Option B**: Add version prefix `v1|ACTION|kid_id|entity_id[|notif_id]`
   - **Recommendation**: Option A (simpler, no breaking change)

2. **Migration Strategy**
   - **Option A**: Silent compatibility (parser handles both old and new)
   - **Option B**: Breaking change (require action format update)
   - **Recommendation**: Option A (no user-visible impact)

3. **Test Strategy**
   - **Option A**: Unit tests only for new helpers
   - **Option B**: Add snapshot tests for notification payloads
   - **Recommendation**: Option A for v0.6.0, consider Option B for v0.7.0

### Effort Estimate

| Phase     | Estimated Time | Complexity |
| --------- | -------------- | ---------- |
| Phase 1   | 1-2 hours      | Low        |
| Phase 2   | 2-3 hours      | Low-Medium |
| Phase 3   | 1-2 hours      | Medium     |
| Phase 4   | 1-2 hours      | Medium     |
| Phase 5   | 2-3 hours      | Medium     |
| **Total** | **7-12 hours** | **Medium** |

### Expected Outcomes

- **Lines removed**: ~100 (duplicated action building)
- **Lines added**: ~150 (helpers + tests)
- **Net change**: ~50 line reduction in production code
- **Type ignores removed**: 4
- **Maintainability**: Significantly improved - single source of truth for action format

### Future Considerations

- Consider adding `build_gamification_notification()` helper if badge/achievement notifications become more complex
- Tag-based notification replacement (v0.5.0+) may benefit from additional helpers
- Dashboard helper sensor could expose notification preferences for UI customization

---

## 🔍 DEEP DIVE ANALYSIS (Complete Audit)

This section documents the comprehensive code review performed to understand the notification system architecture, identify issues, and plan improvements.

### A. ARCHITECTURE OVERVIEW

#### A.1 Core Files & Responsibilities

| File                             | Lines    | Purpose                                                                                       |
| -------------------------------- | -------- | --------------------------------------------------------------------------------------------- |
| `notification_helper.py`         | 123      | Low-level `async_send_notification()` + `build_notification_tag()`                            |
| `notification_action_handler.py` | 132      | Handle mobile app button click callbacks                                                      |
| `coordinator.py`                 | 11,751   | Contains 30+ notification calls + `_notify_kid_translated()` + `_notify_parents_translated()` |
| `kc_helpers.py`                  | 2,478    | Contains `load_notification_translation()` with caching                                       |
| `translations_custom/*.json`     | 12 files | Notification message templates (12 languages)                                                 |
| `const.py`                       | 3,303    | All `TRANS_KEY_NOTIF_*`, `ACTION_*`, `NOTIFY_*` constants                                     |

#### A.2 Notification Flow (End-to-End)

```
1. TRIGGER EVENT (e.g., kid claims chore)
   ↓
2. coordinator.py method (e.g., claim_chore())
   ↓
3. Build actions[] with pipe-delimited format: "ACTION|kid_id|chore_id"
   ↓
4. Call _notify_parents_translated(kid_id, title_key, message_key, message_data, actions, extra_data, tag_type)
   ↓
5. For each parent associated with kid:
   - Load translations for parent's language (kc_helpers.load_notification_translation())
   - Convert title_key/message_key to JSON key (strip "notification_title_" prefix)
   - Format message with placeholders
   - Translate action button titles
   - Add notification tag if tag_type provided
   ↓
6. async_send_notification() → hass.services.async_call("notify", service, payload)
   ↓
7. Mobile app receives notification with action buttons
   ↓
8. User taps action button → HA fires event "mobile_app_notification_action"
   ↓
9. __init__.py listener → async_handle_notification_action(hass, event)
   ↓
10. Parse action string, extract kid_id/chore_id/reward_id/notif_id
   ↓
11. Call coordinator method (approve_chore, disapprove_chore, etc.)
```

#### A.3 Configuration Settings Hierarchy

**Kid-Level Settings** (per kid in storage):
| Setting | Data Key | Default | Effect |
|---------|----------|---------|--------|
| Enable notifications | `DATA_KID_ENABLE_NOTIFICATIONS` | `True` | Master on/off for kid |
| Mobile notify service | `DATA_KID_MOBILE_NOTIFY_SERVICE` | `""` | e.g., `notify.mobile_app_zoe` |
| Use persistent notifications | `DATA_KID_USE_PERSISTENT_NOTIFICATIONS` | `True` | Fallback if no mobile |
| Dashboard language | `DATA_KID_DASHBOARD_LANGUAGE` | System language | Translation language |

**Parent-Level Settings** (per parent in storage):
| Setting | Data Key | Default | Effect |
|---------|----------|---------|--------|
| Enable notifications | `DATA_PARENT_ENABLE_NOTIFICATIONS` | `True` | Master on/off for parent |
| Mobile notify service | `DATA_PARENT_MOBILE_NOTIFY_SERVICE` | `""` | e.g., `notify.mobile_app_mom` |
| Use persistent notifications | `DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS` | `True` | Fallback if no mobile |
| Dashboard language | `DATA_PARENT_DASHBOARD_LANGUAGE` | System language | Translation language |
| Associated kids | `DATA_PARENT_ASSOCIATED_KIDS` | `[]` | Which kids this parent sees |

**Chore-Level Settings** (per chore in storage):
| Setting | Data Key | Default | Effect |
|---------|----------|---------|--------|
| Notify on claim | `DATA_CHORE_NOTIFY_ON_CLAIM` | `True` | Send when kid claims |
| Notify on approval | `DATA_CHORE_NOTIFY_ON_APPROVAL` | `True` | Send when parent approves |
| Notify on disapproval | `DATA_CHORE_NOTIFY_ON_DISAPPROVAL` | `True` | Send when parent disapproves |
| Auto approve | `DATA_CHORE_AUTO_APPROVE` | `False` | Skip claim notification entirely |

#### A.4 Action String Formats

**Chores (3-part format):**

```
ACTION_TYPE|kid_id|chore_id
Examples:
  APPROVE_CHORE|abc123|def456
  DISAPPROVE_CHORE|abc123|def456
  REMIND_30|abc123|def456
```

**Rewards (4-part format):**

```
ACTION_TYPE|kid_id|reward_id|notif_id
Examples:
  APPROVE_REWARD|abc123|def456|notif789
  DISAPPROVE_REWARD|abc123|def456|notif789
  REMIND_30|abc123|def456|notif789
```

**Why different?** Rewards use `notif_id` for stale notification detection (tracking which specific claim is being approved when multiple claims exist).

#### A.5 Tag System (v0.5.0+)

Tags enable **smart notification replacement** - same tag = replace previous notification instead of stacking.

| Tag Type | Constant                  | Format                        | Purpose                            |
| -------- | ------------------------- | ----------------------------- | ---------------------------------- |
| Pending  | `NOTIFY_TAG_TYPE_PENDING` | `kidschores-pending-{kid_id}` | Aggregate pending chore approvals  |
| Rewards  | `NOTIFY_TAG_TYPE_REWARDS` | `kidschores-rewards-{kid_id}` | Aggregate pending reward approvals |
| Status   | `NOTIFY_TAG_TYPE_STATUS`  | `kidschores-status-{kid_id}`  | Status update replacements         |
| System   | `NOTIFY_TAG_TYPE_SYSTEM`  | `kidschores-system-{kid_id}`  | Achievements, badges               |

**Usage Example:**

```python
self._notify_parents_translated(
    kid_id,
    title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES,
    message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES,
    ...,
    tag_type=const.NOTIFY_TAG_TYPE_PENDING,  # ← Enables replacement
)
```

---

### B. IDENTIFIED ISSUES & GAPS

#### Issue #1: REMIND_30 Handler Doesn't Distinguish Chores vs Rewards (BUG)

**Location:** `notification_action_handler.py` lines 40-55

**Problem:** When parsing `REMIND_30` action, handler assumes it's for a chore if `chore_id` is provided. But the action string format doesn't include entity type indicator.

**Current Code:**

```python
elif base_action in (
    const.ACTION_APPROVE_CHORE,
    const.ACTION_DISAPPROVE_CHORE,
    const.ACTION_REMIND_30,  # ← REMIND_30 treated as chore
):
    if len(parts) < 3:
        ...
    kid_id = parts[1]
    chore_id = parts[2]  # ← What if this is actually a reward_id?
```

**Impact:** If a reward reminder uses `REMIND_30|kid_id|reward_id`, it would be misinterpreted as a chore action.

**Resolution:** Change action string to `REMIND_CHORE_30` and `REMIND_REWARD_30`, OR check length (4 parts = reward, 3 parts = chore).

**Priority:** Medium (currently works because rewards include `notif_id` making 4 parts)

---

#### Issue #2: Translation Key Mismatch Handling (SILENT FAILURE)

**Location:** `coordinator.py` lines 11420-11435 (`_notify_parents_translated`)

**Problem:** If a placeholder key is missing, the notification is sent with un-formatted template.

**Current Code:**

```python
try:
    message = message_template.format(**(message_data or {}))
except KeyError as err:
    const.LOGGER.warning(
        "Missing placeholder %s for notification '%s'",
        err,
        json_key,
    )
    message = message_template  # ← Sends "{chore_name}" literally
```

**Impact:** User sees raw template with `{placeholder}` text instead of actual values.

**Resolution:** Either fail gracefully with a generic message, or include placeholders in fallback.

**Priority:** Low (rare edge case, but poor UX when it happens)

---

#### Issue #3: Event Listener Not Unregistered on Unload (MEMORY LEAK)

**Location:** `__init__.py` lines 244-248

**Problem:** The event listener for `mobile_app_notification_action` is registered but never unregistered when the integration is unloaded.

**Current Code:**

```python
hass.bus.async_listen(const.NOTIFICATION_EVENT, handle_notification_event)
# ← No entry.async_on_unload() wrapper!
```

**Impact:** Listener remains active after integration unload, could cause errors if notifications arrive for unloaded integration.

**Resolution:** Wrap in `entry.async_on_unload()`:

```python
entry.async_on_unload(
    hass.bus.async_listen(const.NOTIFICATION_EVENT, handle_notification_event)
)
```

**Priority:** High (technical debt, follows HA best practices)

**Status:** ✅ **FIXED** (2026-01-16)

---

#### Issue #3a: Reminder State Bug - Uses Shared State Instead of Per-Kid State (BUG - FIXED)

**Location:** `coordinator.py` lines 11575-11650 (`remind_in_minutes()`)

**Problem:** The reminder logic checked `chore_info.get(const.DATA_CHORE_STATE)` which is the SHARED chore state, not the per-kid state. For shared chores, this meant:

1. If ANY kid claimed the chore, ALL kids stopped getting reminders (wrong)
2. Reminders sent for `claimed` state (wrong - already waiting for approval)
3. No check for `completed_by_other` state

**Old Code:**

```python
chore_state = chore_info.get(const.DATA_CHORE_STATE)
if chore_state in [const.CHORE_STATE_PENDING, const.CHORE_STATE_CLAIMED, const.CHORE_STATE_OVERDUE]:
    # Send reminder
```

**Resolution:**

```python
# Check per-chore reminder setting
if not chore_info.get(const.DATA_CHORE_NOTIFY_ON_REMINDER, const.DEFAULT_NOTIFY_ON_REMINDER):
    return

# Use per-kid state (FIXED)
kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)

# Only send for PENDING or OVERDUE (FIXED: removed CLAIMED)
if current_state not in [const.CHORE_STATE_PENDING, const.CHORE_STATE_OVERDUE]:
    return
```

**Priority:** High (functional bug affecting shared chores)

**Status:** ✅ **FIXED** (2026-01-16)

---

#### Issue #3b: Reminder Setting Was Per-Kid, Should Be Per-Chore (INCONSISTENCY - FIXED)

**Location:** Kid settings in options flow

**Problem:** The `enable_due_date_reminders` setting was in kid configuration, but other notification settings (`notify_on_claim`, `notify_on_approval`, `notify_on_disapproval`) are per-chore. This made it impossible to say "Send reminders for Homework, but not for Make Bed".

**Resolution:** Added new per-chore setting:

1. Added `DATA_CHORE_NOTIFY_ON_REMINDER` constant
2. Added `CFOF_CHORES_INPUT_NOTIFY_ON_REMINDER` constant
3. Added `DEFAULT_NOTIFY_ON_REMINDER = True` default
4. Updated `_build_notification_defaults()` in `flow_helpers.py`
5. Updated `build_chore_schema()` SelectSelector options
6. Updated `build_chores_data()` extraction
7. Updated `build_default_chore_data()` in `kc_helpers.py`
8. Added translation in `en.json`

**Priority:** Medium (inconsistency, not bug)

**Status:** ✅ **FIXED** (2026-01-16)

---

#### Issue #3c: Reminders Had No Tag - Caused Notification Stacking (FIXED)

**Location:** `coordinator.py` `remind_in_minutes()`

**Problem:** Chore and reward reminders did not include `tag_type` parameter, so repeated reminders stacked in the notification tray instead of replacing the previous one.

**Resolution:** Added `tag_type=const.NOTIFY_TAG_TYPE_PENDING` to chore reminders and `tag_type=const.NOTIFY_TAG_TYPE_REWARDS` to reward reminders.

**Priority:** Medium (UX issue)

**Status:** ✅ **FIXED** (2026-01-16)

---

#### Issue #4: Missing `notif_id` in Aggregated Pending Notifications

**Location:** `coordinator.py` lines 3586-3600 and 3735-3750

**Problem:** When sending aggregated pending notifications after approve/disapprove, the actions built don't include `notif_id` for rewards. However, this is only for chores (not rewards), so may not be an issue.

**Current Code:**

```python
actions = [
    {
        const.NOTIFY_ACTION: f"{const.ACTION_APPROVE_CHORE}|{kid_id}|{latest_chore_id}",
        ...
    },
```

**Impact:** None currently (only chores use aggregation). Document as design constraint.

**Priority:** Documentation only

---

#### Issue #5: Inconsistent `extra_data` Content

**Location:** Multiple locations in coordinator.py

**Problem:** Some notifications include `extra_data`, some don't. The content varies inconsistently.

**Examples:**

- `claim_chore()`: `{kid_id, chore_id}` ✓
- `approve_chore()` kid notification: `{kid_id, chore_id}` ✓
- `approve_chore()` parent status: No extra_data ✗
- `badge_earned`: `{kid_id, badge_id}` ✓
- `penalty_applied`: `{kid_id, penalty_id}` ✓

**Impact:** Mobile app can't deep-link to entities consistently.

**Resolution:** Standardize all notifications to include relevant entity IDs.

**Priority:** Low (enhancement, not bug)

---

#### Issue #6: Due Soon Reminders Reset on HA Restart

**Location:** `coordinator.py` lines 85, 9216

**Problem:** The `_due_soon_reminders_sent` set is transient (in-memory only). If HA restarts, reminders may be sent again.

**Current Code:**

```python
self._due_soon_reminders_sent: set[str] = set()  # ← Transient, resets on restart
```

**Impact:** Users may receive duplicate due-soon reminders after HA restart.

**Resolution:** Either accept this behavior (it's arguable whether re-notifying is bad), or persist to storage.

**Priority:** Low (acceptable behavior, document as known limitation)

---

### C. TRANSLATION FILE COMPLETENESS CHECK

**File:** `translations_custom/en_notifications.json`

| Notification Event       | JSON Key                                   | Status     |
| ------------------------ | ------------------------------------------ | ---------- |
| Chore Assigned           | `chore_assigned`                           | ✅ Present |
| Chore Claimed            | `chore_claimed`                            | ✅ Present |
| Chore Approved           | `chore_approved`                           | ✅ Present |
| Chore Disapproved        | `chore_disapproved`                        | ✅ Present |
| Chore Overdue            | `chore_overdue`                            | ✅ Present |
| Chore Due Soon           | `chore_due_soon`                           | ✅ Present |
| Chore Reminder           | `chore_reminder`                           | ✅ Present |
| Reward Claimed (Kid)     | `reward_claimed_kid`                       | ✅ Present |
| Reward Claimed (Parent)  | `reward_claimed_parent`                    | ✅ Present |
| Reward Approved          | `reward_approved`                          | ✅ Present |
| Reward Disapproved       | `reward_disapproved`                       | ✅ Present |
| Reward Reminder          | `reward_reminder`                          | ✅ Present |
| Badge Earned (Kid)       | `badge_earned_kid`                         | ✅ Present |
| Badge Earned (Parent)    | `badge_earned_parent`                      | ✅ Present |
| Achievement (Kid)        | `achievement_earned_kid`                   | ✅ Present |
| Achievement (Parent)     | `achievement_earned_parent`                | ✅ Present |
| Challenge (Kid)          | `challenge_completed_kid`                  | ✅ Present |
| Challenge (Parent)       | `challenge_completed_parent`               | ✅ Present |
| Penalty Applied          | `penalty_applied`                          | ✅ Present |
| Bonus Applied            | `bonus_applied`                            | ✅ Present |
| Pending Chores           | `pending_chores`                           | ✅ Present |
| Status Update            | `status_update`                            | ✅ Present |
| Chore Approved Status    | `chore_approved_status`                    | ✅ Present |
| Chore Disapproved Status | `chore_disapproved_status`                 | ✅ Present |
| Reward Approved Status   | `reward_approved_status`                   | ✅ Present |
| Actions                  | `actions` (approve, disapprove, remind_30) | ✅ Present |

**Result:** All translation keys are present. ✅

---

### D. TEST COVERAGE ANALYSIS

**Existing Test File:** `tests/test_workflow_notifications.py` (874 lines)

| Test Area                  | Coverage   | Notes                                      |
| -------------------------- | ---------- | ------------------------------------------ |
| Chore claim notification   | ✅ Covered | Tests parent receives notification         |
| Chore approve notification | ✅ Covered | Tests kid receives notification            |
| Language preference        | ✅ Covered | Tests Slovak translations load correctly   |
| Action button translation  | ✅ Covered | Tests buttons use parent's language        |
| Parent association         | ✅ Covered | Tests only associated parents notified     |
| Mock notification service  | ✅ Covered | Tests graceful handling of missing service |

**Gaps Identified:**

- ❌ No tests for action string parsing in handler
- ❌ No tests for malformed action handling
- ❌ No tests for `REMIND_30` action execution
- ❌ No tests for tag-based notification replacement
- ❌ No tests for due-soon reminder logic

---

### E. QUESTIONS FOR CLARIFICATION

1. **REMIND_30 Behavior:** Should `REMIND_30` create a new notification or update the existing one (using tags)?
   - Current: Creates new notification
   - Suggestion: Use same tag to replace

2. **Due-Soon Reminder Persistence:** Is it acceptable that due-soon reminders re-trigger after HA restart?
   - Current: Yes, transient
   - Alternative: Persist to storage

3. **Parent Status Notifications:** Should the "status update" notification (sent when all pending cleared) include action buttons to view history?
   - Current: No actions
   - Suggestion: Could add "View All" action

4. **Gamification Notifications:** Should badge/achievement/challenge notifications include parent action buttons?
   - Current: No actions (kid and parent just informed)
   - Suggestion: Could add "View Details" action

---

## Phase 6 – User Guide Documentation (EXEMPT)

**Status**: ✅ EXEMPT - Existing wiki documentation sufficient

- **Goal**: Create comprehensive user-facing documentation explaining notification system configuration and behavior.
- **Exemption Reason**: Existing wiki page `Notifications:-Overview.md` already provides comprehensive coverage:
  - ✅ All 17 notification events documented with recipients and actionability
  - ✅ Smart tag replacement system explained
  - ✅ Enable/disable controls (system-wide, per-profile, per-chore)
  - ✅ Language/translation architecture reference
  - ✅ Mobile app setup instructions
  - ✅ Troubleshooting section
  - ✅ Linked from wiki Home page under Configuration section
- **Steps / detailed work items**
  1. - [x] ~~Create `Notifications:-Overview.md`~~ **DONE** - Comprehensive notification documentation exists
  2. - [x] ~~Add notification FAQ section~~ **EXEMPT** - Covered in overview page
  3. - [x] ~~Update main README~~ **EXEMPT** - Wiki provides sufficient detail
  4. - [x] ~~Add screenshots~~ **EXEMPT** - Not needed for v0.6.0
  5. - [x] ~~Create troubleshooting page~~ **EXEMPT** - Included in overview
- **Outcome**: No additional documentation needed for v0.6.0 release

---

**Document created**: 2026-01-16
**Last updated**: 2026-01-16
**Deep dive completed**: 2026-01-16
**Next review**: After v0.5.0 release stabilization

---

## Phase 7 – Notification Tag System Fix (100% ✅)

**Status**: ✅ Complete (All 21 steps done)

### Problem Statement

**Current Bug**: Notifications use tags based ONLY on `kid_id`, causing notification collisions when:

1. Same kid claims 2+ chores at similar times → Second notification **replaces** first
2. Reminders sent 30 min later → Replaces notification for different chore

**Impact**: Parents MISS approval requests for chores because they get replaced silently.

### Root Cause Analysis

**Current Tag Pattern** (BROKEN):

```
Tag: kidschores-pending-{kid_id}
```

**Scenario A: Same Kid, 2 Chores (BROKEN)**

```
9:00:00 - Sarah claims "Trash" (chore1)
          → Tag: kidschores-pending-sarah123
          → Notification A appears ✅

9:00:05 - Sarah claims "Dishes" (chore2)
          → Tag: kidschores-pending-sarah123 (SAME TAG!)
          → Notification A DISAPPEARS, B appears ❌
          → Parents MISS "Trash" approval request!
```

**Scenario B: Shared Chore, 2 Kids (WORKS)**

```
9:00:00 - Sarah claims "Clean Room" (chore1)
          → Tag: kidschores-pending-sarah123
          → Notification A appears ✅

9:00:05 - Tom claims "Clean Room" (chore1)
          → Tag: kidschores-pending-tom456 (different kid)
          → Notification B appears ✅
          → Both visible ✅
```

**Scenario C: Reminder After Claim (BROKEN)**

```
9:00:00 - Sarah claims "Trash" (chore1)
          → Tag: kidschores-pending-sarah123

9:00:05 - Sarah claims "Dishes" (chore2)
          → Tag: kidschores-pending-sarah123
          → Replaces "Trash" notification ❌

9:30:00 - Parent presses "Remind 30" for "Trash"
          → Tag: kidschores-pending-sarah123
          → Replaces "Dishes" notification ❌
          → Now BOTH are lost/confused!
```

### Correct Solution: Per-Chore + Per-Kid Tags

**New Tag Pattern** (FIXED):

```
Tag: kidschores-status-{chore_id}-{kid_id}
```

**Scenario A: Same Kid, 2 Chores (FIXED)**

```
9:00:00 - Sarah claims "Trash" (chore1)
          → Tag: kidschores-status-chore1-sarah123
          → Notification A appears ✅

9:00:05 - Sarah claims "Dishes" (chore2)
          → Tag: kidschores-status-chore2-sarah123 (DIFFERENT TAG!)
          → Notification B appears ✅
          → BOTH VISIBLE ✅
```

**Scenario B: Shared Chore, 2 Kids (STILL WORKS)**

```
9:00:00 - Sarah claims "Clean Room" (chore1)
          → Tag: kidschores-status-chore1-sarah123
          → Notification A appears ✅

9:00:05 - Tom claims "Clean Room" (chore1)
          → Tag: kidschores-status-chore1-tom456 (DIFFERENT TAG!)
          → Notification B appears ✅
          → BOTH VISIBLE ✅
```

**Scenario C: Reminder for Same Chore (CORRECT)**

```
9:00:00 - Sarah claims "Trash" (chore1)
          → Tag: kidschores-status-chore1-sarah123

9:30:00 - Parent presses "Remind 30" for "Trash"
          → Tag: kidschores-status-chore1-sarah123 (SAME TAG - correct!)
          → REPLACES original with fresh reminder ✅
```

**Scenario D: Re-claim After Disapproval (CORRECT)**

```
9:00:00 - Sarah claims "Trash" (chore1)
          → Tag: kidschores-status-chore1-sarah123

9:05:00 - Parent disapproves

9:10:00 - Sarah re-claims "Trash" (chore1)
          → Tag: kidschores-status-chore1-sarah123 (SAME TAG - correct!)
          → REPLACES old disapproved notification ✅
```

### Implementation Plan

#### Step 1: Update `build_notification_tag()` to accept multiple identifiers

**File**: `custom_components/kidschores/notification_helper.py`

**Current** (line 182):

```python
def build_notification_tag(tag_type: str, identifier: str = "") -> str:
    if identifier:
        return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}-{identifier}"
    return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}"
```

**New**:

```python
def build_notification_tag(tag_type: str, *identifiers: str) -> str:
    """Build notification tag with multiple identifiers.

    Args:
        tag_type: Type of notification (pending, rewards, system, status)
        *identifiers: One or more identifiers to make tag unique.
                     For per-entity tags: (entity_id, kid_id)
                     For per-kid tags: (kid_id,)

    Returns:
        Tag string: kidschores-{tag_type}-{id1}-{id2}-...

    Examples:
        build_notification_tag("status", chore_id, kid_id)
        -> "kidschores-status-abc123-def456"
    """
    if identifiers:
        ids = "-".join(identifiers)
        return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}-{ids}"
    return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}"
```

#### Step 2: Update `_notify_parents_translated()` signature

**File**: `custom_components/kidschores/coordinator.py` (line 11284)

**Current**:

```python
async def _notify_parents_translated(
    self,
    kid_id: str,
    title_key: str,
    message_key: str,
    message_data: dict[str, Any] | None = None,
    actions: list[dict[str, str]] | None = None,
    extra_data: dict | None = None,
    tag_type: str | None = None,
) -> None:
```

**New**:

```python
async def _notify_parents_translated(
    self,
    kid_id: str,
    title_key: str,
    message_key: str,
    message_data: dict[str, Any] | None = None,
    actions: list[dict[str, str]] | None = None,
    extra_data: dict | None = None,
    tag_type: str | None = None,
    tag_identifiers: tuple[str, ...] | None = None,  # NEW
) -> None:
```

**And update tag building** (line ~11322):

```python
# Current:
if tag_type:
    notification_tag = build_notification_tag(tag_type, kid_id)

# New:
if tag_type:
    identifiers = tag_identifiers if tag_identifiers else (kid_id,)
    notification_tag = build_notification_tag(tag_type, *identifiers)
```

#### Step 3: Update ALL chore notification call sites (9 locations)

| #   | Method                          | Line  | Current            | New                                                          |
| --- | ------------------------------- | ----- | ------------------ | ------------------------------------------------------------ |
| 1   | `claim_chore()` aggregated      | 3126  | `tag_type=PENDING` | `tag_type=STATUS, tag_identifiers=(chore_id, kid_id)`        |
| 2   | `claim_chore()` single          | 3142  | `tag_type=PENDING` | `tag_type=STATUS, tag_identifiers=(chore_id, kid_id)`        |
| 3   | `approve_chore()` aggregated    | 3590  | `tag_type=PENDING` | `tag_type=STATUS, tag_identifiers=(latest_chore_id, kid_id)` |
| 4   | `approve_chore()` status        | 3604  | `tag_type=PENDING` | **REMOVE** (no longer needed - clear instead)                |
| 5   | `disapprove_chore()` aggregated | 3730  | `tag_type=PENDING` | `tag_type=STATUS, tag_identifiers=(latest_chore_id, kid_id)` |
| 6   | `disapprove_chore()` status     | 3744  | `tag_type=PENDING` | **REMOVE** (no longer needed - clear instead)                |
| 7   | `_notify_overdue_chore()`       | 9096  | `tag_type=PENDING` | `tag_type=STATUS, tag_identifiers=(chore_id, kid_id)`        |
| 8   | `remind_in_minutes()` chore     | 11579 | `tag_type=PENDING` | `tag_type=STATUS, tag_identifiers=(chore_id, kid_id)`        |
| 9   | `redeem_reward()`               | 5597  | **NO TAG**         | `tag_type=REWARDS, tag_identifiers=(reward_id, kid_id)`      |

#### Step 4: Update reward notification call sites

| #   | Method                       | Line  | Current                          | New                                                     |
| --- | ---------------------------- | ----- | -------------------------------- | ------------------------------------------------------- |
| 1   | `redeem_reward()`            | 5597  | No tag                           | `tag_type=REWARDS, tag_identifiers=(reward_id, kid_id)` |
| 2   | `remind_in_minutes()` reward | 11614 | `tag_type=REWARDS` (kid_id only) | `tag_type=REWARDS, tag_identifiers=(reward_id, kid_id)` |

#### Step 5: Add `clear_notification_for_parents()` helper

**File**: `custom_components/kidschores/coordinator.py` (new method)

```python
async def clear_notification_for_parents(
    self,
    kid_id: str,
    tag_type: str,
    entity_id: str,
) -> None:
    """Clear (dismiss) notifications for all parents associated with a kid.

    Sends 'clear_notification' message with the same tag used when the
    notification was originally sent. This dismisses stale notifications
    when the underlying action was taken via dashboard instead of
    notification button.

    Args:
        kid_id: The internal ID of the kid
        tag_type: Tag type (const.NOTIFY_TAG_TYPE_STATUS, etc.)
        entity_id: The chore_id or reward_id
    """
    from .notification_helper import build_notification_tag

    tag = build_notification_tag(tag_type, entity_id, kid_id)

    for parent_id, parent_info in self.parents_data.items():
        if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            continue

        mobile_service = parent_info.get(const.DATA_PARENT_MOBILE_NOTIFY_SERVICE)
        if not mobile_service:
            continue

        # HA Companion app uses "clear_notification" message with tag
        service_name = mobile_service.replace("notify.", "")
        await self.hass.services.async_call(
            "notify",
            service_name,
            {
                "message": "clear_notification",
                "data": {"tag": tag},
            },
        )
        const.LOGGER.debug(
            "Cleared notification tag '%s' for parent '%s'",
            tag,
            parent_id,
        )
```

#### Step 6: Add clear calls to approval/disapproval methods

**Call sites to add clear_notification_for_parents()**:

| Method                | When                         | Clear Tag                                 |
| --------------------- | ---------------------------- | ----------------------------------------- |
| `approve_chore()`     | After successful approval    | `kidschores-status-{chore_id}-{kid_id}`   |
| `disapprove_chore()`  | After successful disapproval | `kidschores-status-{chore_id}-{kid_id}`   |
| `approve_reward()`    | After successful approval    | `kidschores-rewards-{reward_id}-{kid_id}` |
| `disapprove_reward()` | After successful disapproval | `kidschores-rewards-{reward_id}-{kid_id}` |

**Note**: When approval/disapproval happens via **notification button**, the mobile app automatically clears the notification. The clear call handles the case where approval happens via **dashboard**.

#### Step 7: Update tests

**File**: `tests/test_notification_helpers.py`

Add tests for:

- `build_notification_tag()` with multiple identifiers
- `build_notification_tag()` with single identifier (backwards compatible)
- `build_notification_tag()` with no identifiers

#### Step 8: Fix overdue/due-soon notification action buttons

**Problem**: Overdue and due-soon notifications have wrong/missing action buttons.

| Notification       | Recipient | Current Buttons              | Correct Buttons               |
| ------------------ | --------- | ---------------------------- | ----------------------------- |
| **Chore Overdue**  | Parents   | Approve/Disapprove/Remind ❌ | **NONE** (chore not claimed)  |
| **Chore Overdue**  | Kids      | Approve/Disapprove ❌        | **NONE** (kids can't approve) |
| **Chore Due Soon** | Kids      | None                         | **NONE** (informational only) |

**Why remove overdue action buttons?**

- Approve/Disapprove only make sense for **claimed** chores awaiting approval
- Overdue chores are NOT claimed - kid hasn't done the work yet
- Action buttons on unclaimed chores are confusing and don't do anything useful

**File changes needed**:

**A. `_notify_overdue_chore()` - Parent notification** (line ~9082):

```python
# Current:
actions = build_chore_actions(kid_id, chore_id)
await self._notify_parents_translated(..., actions=actions, ...)

# New:
await self._notify_parents_translated(..., actions=None, ...)  # Remove actions
```

**B. `_notify_overdue_chore()` - Kid notification** (line ~9064):

```python
# Current:
extra_data = build_extra_data(kid_id, chore_id=chore_id)
await self._notify_kid_translated(..., extra_data=extra_data)

# New:
await self._notify_kid_translated(..., extra_data=None)  # Remove extra_data (no actions)
```

**Note**: We are NOT adding "Claim Now" buttons at this time. That would require:

- Deep-link URL support in mobile app
- URI action type configuration
- Dashboard entity reference resolution

This is a separate future enhancement, not a bug fix.

#### Step 9: Update wiki documentation

**File**: `docs/wiki/Notifications:-Overview.md`

Update "Smart Tags" section to explain per-chore+per-kid tagging and clear behavior.
Update overdue notification documentation to reflect no action buttons.

### Steps / Detailed Work Items

1. - [x] **DONE** Update `build_notification_tag()` to accept `*identifiers`
2. - [x] **DONE** Add `tag_identifiers` parameter to `_notify_parents_translated()`
3. - [x] **DONE** Update tag building logic in `_notify_parents_translated()`
4. - [x] **DONE** Update `claim_chore()` - 2 locations
5. - [x] **DONE** Update `approve_chore()` - tag + clear call (removed status notification)
6. - [x] **DONE** Update `disapprove_chore()` - tag + clear call (removed status notification)
7. - [x] **DONE** Update `_notify_overdue_chore()` - tag + **REMOVED action buttons from both kid and parent**
8. - [x] **DONE** Update `remind_in_minutes()` chore - 1 location
9. - [x] **DONE** Add tag to `redeem_reward()` - 1 location
10. - [x] **DONE** Update `remind_in_minutes()` reward - 1 location
11. - [x] **DONE** Add `clear_notification_for_parents()` helper method
12. - [x] **DONE** (Combined with step 5) Add clear call in `approve_chore()`
13. - [x] **DONE** (Combined with step 6) Add clear call in `disapprove_chore()`
14. - [x] **DONE** Add clear call in `approve_reward()`
15. - [x] **DONE** Add clear call in `disapprove_reward()`
16. - [x] **DONE** Update tests for `build_notification_tag()` multiple identifiers
17. - [x] **DONE** Wiki Smart Tags documentation - already accurate (lines 68-102 of Notifications:-Overview.md)
18. - [x] **DONE** Wiki overdue notification documentation - already accurate (lines 59-64 and line 20)
19. - [x] **DONE** Run validation: `./utils/quick_lint.sh --fix` ✅ All checks passed
20. - [x] **DONE** Run validation: `mypy custom_components/kidschores/` ✅ Zero errors
21. - [x] **DONE** Run tests: `pytest tests/ -v --tb=line` ✅ 734 passed, 2 deselected

### Key Issues / Risks

- **Breaking Change**: None - tags are internal implementation detail
- **Migration**: None needed - old notifications will simply be replaced by new ones
- **Risk**: Ensure reward notification ID (`notif_id`) is still passed correctly for tracking
- **Future Enhancement**: "Claim Now" deep-link buttons deferred (requires mobile app URI support)

### Effort Estimate

| Step Group                   | Estimated Time | Complexity |
| ---------------------------- | -------------- | ---------- |
| Helper updates (1-3)         | 30 min         | Low        |
| Chore call sites (4-8)       | 1 hour         | Low-Medium |
| Reward call sites (9-10)     | 20 min         | Low        |
| Clear helper + calls (11-15) | 1 hour         | Medium     |
| Tests + docs (16-21)         | 1 hour         | Low        |
| **Total**                    | **4-5 hours**  | **Medium** |
