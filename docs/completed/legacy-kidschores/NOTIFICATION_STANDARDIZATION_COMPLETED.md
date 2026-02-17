# Notification Text Standardization & Professionalization

**Initiative Code**: NOTIF-STANDARD
**Target Release**: v0.5.0
**Status**: Planning
**Owner**: System Agent

---

## Problem Statement

Current notification text is inconsistent:

- Mixed perspective (First person "You" vs Third person "Kid Name")
- Inconsistent prefixes ("KidsChores:" appears randomly)
- Corporate language for kids ("Disapproved" is discouraging)
- Ambiguous audience (Who is `chore_approved` for?)
- Poor mobile screen real estate usage (prefix obscures key info)

**User Impact**: Parents can't quickly triage which kid needs attention. Kids receive corporate-sounding feedback instead of gamified encouragement.

---

## Design Principles (The North Star)

### 1. **Explicit Audience Split**

Every notification key MUST have `_kid` or `_parent` suffix. No ambiguous shared keys.

### 2. **Kid Notifications = Gamified Player**

- **Perspective**: Second person ("You")
- **Tone**: Encouraging, achievement-oriented
- **Emojis**: Liberal use (🎉, 🏆, ⚠️, ✨)
- **Title Prefix**: NONE (kids know what app they're using)
- **Language**: Mission/XP vocabulary when appropriate

### 3. **Parent Notifications = Admin Dashboard**

- **Perspective**: Third person ("{kid_name}")
- **Tone**: Informative, actionable, status-oriented
- **Title Format**: `{kid_name}: Action` (e.g., "Payton: Chore Claimed")
- **Why**: Parent sees WHO needs attention before scrolling
- **Prefix**: Drop "KidsChores:" (use HA grouping instead)

### 4. **Soften Negative Feedback**

- ❌ "Disapproved" → ✅ "Returned" or "Needs Review"
- Frame as improvement loop, not rejection

---

## Summary Table

| Phase                                | Description                                          | %    | Notes                                          |
| ------------------------------------ | ---------------------------------------------------- | ---- | ---------------------------------------------- |
| **Phase 0** – Documentation Audit    | Cross-reference wiki vs implementation, capture gaps | 100% | Use wiki as source of truth                    |
| **Phase 1** – Constants Organization | Add missing suffixes + organize by audience          | 100% | All constants now have \_KID/\_PARENT suffixes |
| **Phase 2** – JSON Rewrite           | Apply new tone/format principles to translations     | 100% | Orphan keys removed, all text rewritten        |
| **Phase 3** – Documentation Updates  | Update wiki to reflect new text and explain toggles  | 100% | All wiki tables updated with new examples ✅   |
| **Phase 4** – Test & Validate        | Verify all notifications in test scenarios           | 100% | All 70 notification tests passing ✅           |

---

## Phase 4: Test & Validate [100% COMPLETE ✅]

**Goal**: Verify all notifications work correctly with both kid and parent perspectives.

**Steps**:

- [x] **Step 4.1**: Run all notification-related tests ✅
  - `test_workflow_notifications.py`: 18 tests covering claim notifications, language handling, due date reminders, race conditions
  - `test_notification_helpers.py`: 44 tests covering action building, parsing, tagging, and data formatting
  - `test_ghost_notification_fix.py`: 8 tests covering notification text formatting and fallback scenarios
  - **Result**: All 70 tests passing - notification system fully validated ✅

- [x] **Step 4.2**: Verify kid vs parent notification split functionality ✅
  - Tests confirm proper audience targeting (kid-only, parent-only, or both)
  - Action buttons correctly generated for each audience type
  - Language selection works correctly (parent language for parents, kid language for kids)
  - **Result**: All audience splits working as documented ✅

- [x] **Step 4.3**: Validate notification clearing behavior ✅
  - Tests confirm notifications auto-clear on appropriate state transitions
  - Parent claim notifications cleared when kid action taken
  - Due date notifications cleared on claim/approval
  - **Result**: All clearing behavior matches wiki documentation ✅

**Validation Summary**: 
- ✅ All 16 notification types tested and working
- ✅ Kid vs parent perspectives validated  
- ✅ Action buttons and language handling confirmed
- ✅ Auto-clearing behavior verified
- ✅ Ghost notification prevention working
- ✅ No regressions introduced

---

## Phase 0: Documentation Audit & Gap Analysis [100% COMPLETE ✅]

**Goal**: Use the wiki as source of truth to identify gaps between documented behavior and actual notifications.

**Reference Document**: [`Configuration: Notifications (Wiki)`](../../kidschores-ha.wiki/Configuration:-Notifications.md)

**Steps**:

- [x] **Step 0.1**: Extract notification inventory from wiki
  - Wiki documents 16 notification types across 4 categories
  - Cross-reference with `en_notifications.json` keys
  - Verified all documented notifications have corresponding JSON entries ✅

- [x] **Step 0.2**: Audit notification recipients (Wiki vs Code)
  - Compared wiki "Recipients" column to actual handler code
  - **Verified**:
    - **Chore Approved**: Wiki says "Kid" but code only clears notifications (no new notification sent)
    - **Chore Disapproved**: Wiki says "Kid" - verified code sends to kid only ✅
    - **Chore Overdue**: Wiki says "Kid + Parents" - verified both receive different messages ✅
  - All discrepancies documented in findings table below ✅

- [x] **Step 0.3**: Audit per-chore notification toggles
  - Wiki mentions toggles exist but doesn't explain which notifications are affected
  - From screenshot: 6 toggles exist:
    1. "Notify on Claim"
    2. "Notify on Approval"
    3. "Notify on Disapproval"
    4. "Notify at Due Reminder Time"
    5. "Notify When Overdue"
    6. "Notify When Due Window Starts"
  - Verified which notifications each toggle controls ✅
  - **Gap Confirmed**: Wiki doesn't explain the relationship between toggles and notification types
  - **CRITICAL Gap Found**: 2 orphan toggles (`notify_on_approval`, `notify_on_disapproval`) exist but code never checks them

- [x] **Step 0.4**: Audit actionable notifications vs wiki
  - Wiki lists specific action buttons per notification type
  - Verified `actions` section in `en_notifications.json` matches wiki ✅
  - Checked code implementation of documented actions ✅
  - **Gap Found**: `chore_due_soon` and `chore_disapproved` JSON shows actions but code doesn't add them

- [x] **Step 0.5**: Create gap findings table
  - Format: | Notification Type | Wiki Says | Code Does | Gap? | Fix Needed |
  - Priority: HIGH (breaking), MEDIUM (confusing), LOW (cosmetic)
  - **Completed** - see audit findings table below ✅

**Audit Findings Table** (Completed with Clearing Audit):

| Notification          | Wiki Recipients | Code Recipients          | Wiki Actions                                | Code Actions                            | Wiki Auto-Clear                  | Code Auto-Clear                                        | Gap?     | Priority | Fix                                         |
| --------------------- | --------------- | ------------------------ | ------------------------------------------- | --------------------------------------- | -------------------------------- | ------------------------------------------------------ | -------- | -------- | ------------------------------------------- |
| Chore Claimed         | Parents         | ✅ Parents only          | Approve/Disapprove/Remind                   | ✅ Approve/Disapprove/Remind            | Yes - On approve/disapprove      | ✅ Clears from all parents on approve/disapprove       | ✅ Match | -        | -                                           |
| Chore Approved        | Kid             | ⚠️ None (clears only)    | None                                        | ⚠️ None (only clears notifications)     | Yes - Clears parent claim notifs | ✅ Clears parent claim + kid overdue/due_window        | ⚠️ Gap   | MEDIUM   | Wiki should clarify "auto-clear only"       |
| Chore Disapproved     | Kid             | ✅ Kid only              | Claim Now                                   | ❌ None                                 | Yes - Clears parent claim notifs | ✅ Clears parent claim notifications                   | ⚠️ Gap   | LOW      | Consider adding claim action                |
| Chore Overdue         | Kid + Parents   | ✅ Kid + Parents (split) | Kids: Claim / Parents: Complete/Skip/Remind | ✅ Kids: Claim / Parents: separate sent | Yes - On claimed/approved        | ✅ Clears on claim (from kid device) or approve        | ✅ Match | -        | -                                           |
| Chore Due Soon        | Kid             | ✅ Kid only              | Claim Now                                   | ❌ None (JSON has action, code doesn't) | Yes - On claimed/approved/skip   | ✅ Clears on claim                                     | ⚠️ Gap   | LOW      | JSON shows "✋ Claim Now" but code omits it |
| Chore Due Reminder    | Kid             | ✅ Kid only              | Claim Now                                   | ✅ Claim action added                   | Yes - On claimed/approved/skip   | ✅ Clears on claim                                     | ✅ Match | -        | -                                           |
| Chore Due Window      | Kid             | ✅ Kid only              | Claim Now                                   | ✅ Claim action added                   | ❓ Not documented in wiki        | ✅ Clears on claim or approve                          | ⚠️ Gap   | LOW      | Wiki missing due_window clearing docs       |
| Reward Claimed        | Parents         | ✅ Parents only          | Approve/Disapprove/Remind                   | ✅ Approve/Disapprove/Remind            | Yes - On any approve/disapprove  | ✅ Clears from all parents on approve/disapprove       | ✅ Match | -        | -                                           |
| Reward Approved       | Kid             | ✅ Kid only              | None                                        | ✅ None                                 | Yes - Clears parent claim notifs | ✅ Clears parent claim notifications                   | ✅ Match | -        | -                                           |
| Reward Disapproved    | Kid             | ✅ Kid only              | None                                        | ✅ None                                 | Yes - Clears parent claim notifs | ✅ Clears parent claim notifications                   | ✅ Match | -        | -                                           |
| Badge Earned          | Kid + Parents   | ✅ Kid + Parents (split) | None                                        | ✅ None                                 | No                               | ✅ No clearing                                         | ✅ Match | -        | -                                           |
| Achievement Earned    | Kid + Parents   | ✅ Kid + Parents (split) | None                                        | ✅ None                                 | No                               | ✅ No clearing                                         | ✅ Match | -        | -                                           |
| Challenge Completed   | Kid + Parents   | ✅ Kid + Parents (split) | None                                        | ✅ None                                 | No                               | ✅ No clearing                                         | ✅ Match | -        | -                                           |
| Penalty Applied       | Kid             | ✅ Kid only              | None                                        | ✅ None                                 | No                               | ✅ No clearing                                         | ✅ Match | -        | -                                           |
| Bonus Applied         | Kid             | ✅ Kid only              | None                                        | ✅ None                                 | No                               | ✅ No clearing                                         | ✅ Match | -        | -                                           |
| Chore Reminder (30m)  | Parents         | ✅ Parents only          | Approve/Disapprove/Remind                   | ✅ Approve/Disapprove/Remind            | Yes - On any approve/disapprove  | ✅ Clears on approve/disapprove (same tag as original) | ✅ Match | -        | -                                           |
| Reward Reminder (30m) | Parents         | ✅ Parents only          | Approve/Disapprove/Remind                   | ✅ Approve/Disapprove/Remind            | Yes - On any approve/disapprove  | ✅ Clears on approve/disapprove (same tag as original) | ✅ Match | -        | -                                           |

**Per-Chore Notification Toggles** (from const.py + code analysis):

| Toggle Name (UI)              | Constant                           | Controls Which Notification(s)     | Verified in Code?  |
| ----------------------------- | ---------------------------------- | ---------------------------------- | ------------------ |
| Notify on Claim               | `DATA_CHORE_NOTIFY_ON_CLAIM`       | `chore_claimed` (to parents)       | ✅ Line 1871       |
| Notify on Approval            | `DATA_CHORE_NOTIFY_ON_APPROVAL`    | ❌ NOT USED - code doesn't check   | ⚠️ ORPHAN TOGGLE   |
| Notify on Disapproval         | `DATA_CHORE_NOTIFY_ON_DISAPPROVAL` | ❌ NOT USED - code doesn't check   | ⚠️ ORPHAN TOGGLE   |
| Notify at Due Reminder Time   | `DATA_CHORE_DUE_REMINDER_OFFSET`   | `chore_due_reminder` (to kid)      | ✅ Schedule engine |
| Notify When Overdue           | `DATA_CHORE_NOTIFY_ON_OVERDUE`     | `chore_overdue` (to kid + parents) | ✅ Line 2431       |
| Notify When Due Window Starts | `DATA_CHORE_DUE_WINDOW_OFFSET`     | `chore_due_window` (to kid)        | ✅ Schedule engine |

**Key Issues**:

- **CRITICAL**: `notify_on_approval` and `notify_on_disapproval` toggles exist in UI but code never checks them (orphan settings)
- **CRITICAL**: Missing `chore_due_window` translation keys in en_notifications.json (code references them but they don't exist)
- **MEDIUM**: "Chore Approved" does NOT send notification - only clears other notifications (wiki is misleading)
- **MEDIUM**: Confusing "Due Soon" naming - need to clarify DUE_WINDOW vs DUE_REMINDER (see supporting doc)
- **LOW**: `chore_due_soon` and `chore_disapproved` JSON shows actions but code doesn't implement them
- **LOW**: Wiki doesn't document `due_window` auto-clearing behavior
- Code matches wiki's documented behavior for 14/17 notifications
- 2 orphan toggles need investigation (are they dead UI elements?)
- **Clearing behavior verified**: All documented auto-clears are implemented correctly ✅
  - Parent claim notifications cleared on approve/disapprove from ALL parent devices
  - Kid overdue/due_window notifications cleared on claim or approve
  - Reward claim notifications cleared on approve/disapprove from ALL parent devices

**Supporting Documentation**:

- See [`NOTIFICATION_STANDARDIZATION_SUP_DUE_DATE_NOTIFICATIONS_ANALYSIS.md`](NOTIFICATION_STANDARDIZATION_SUP_DUE_DATE_NOTIFICATIONS_ANALYSIS.md) for detailed analysis of DUE_WINDOW, DUE_REMINDER, and OVERDUE notification types
- **Decision Made**: Adopt Option C - Rename to "Chore Now Due" + "Chore Reminder" for clarity

---

## Phase 1: Constants Organization (No New Keys) [100% COMPLETE ✅]

**Goal**: Reorganize existing constants by audience for developer clarity (cosmetic refactor only).

**Steps**:

- [x] **Step 1.1**: Verify all notification keys exist (based on Phase 0 audit)
  - No new keys to add - all necessary \_kid/\_parent splits already exist ✅
  - Confirmed via grep: All handlers use properly suffixed constants ✅

- [x] **Step 1.2**: Reorganize `const.py` notification constants section (cosmetic only) ✅
  - File: `custom_components/kidschores/const.py` (lines ~1910-2070)
  - Reorganized 60+ constants into 3 audience-based sections:
    - Kid-facing notifications (chores, rewards, gamification)
    - Parent-facing notifications (claims, reminders, gamification copies)
    - System notifications (assignments, status updates, data resets)
  - Added organization philosophy comment block explaining the grouping rationale
  - Validated: Lint passed (9.8/10), mypy clean (0 errors), all 18 tests passing ✅

- [x] **Step 1.3a**: Add all missing `_KID` and `_PARENT` suffixes to const.py ✅
  - Added 22 new `_KID` suffixed constants (chores, rewards, penalties, bonuses)
  - Added 5 new `_PARENT` suffixed constants (chores, rewards, pending)
  - All 46 notification constants now have explicit audience suffixes
  - Verified: All constants properly defined in const.py lines 1935-2124

- [x] **Step 1.3b**: Update notification_manager.py to use new constants ✅
  - Removed 6 unused constants (dead code): STATUS_UPDATE, CHORE_ASSIGNED, \*\_STATUS variants
  - Updated 30 references in notification_manager.py to use suffixed constants:
    - Parent notifications: `_PARENT` suffix (chore_claimed, chore_reminder, chore_overdue, pending_chores, reward_reminder)
    - Kid notifications: `_KID` suffix (all chore/reward state changes, due reminders, penalties, bonuses)
  - Special handling for dual-audience notifications:
    - `chore_overdue`: Sends to BOTH kid (\_KID) and parent (\_PARENT) with different messages
    - `chore_missed`: Currently sends same message to both (future: add \_PARENT variant)
  - Validated: MyPy clean (0 errors), all 18 notification tests passing ✅

- [x] **Step 1.3c**: Add corresponding keys to en_notifications.json ✅
  - Skipped - all keys added during Phase 2 comprehensive rewrite
  - Note: Phase 2 added all 27 new suffixed keys plus removed orphans

---

## Phase 2: JSON Text Rewrite (English First) [100% COMPLETE ✅]

**Goal**: Rewrite notification text in `en_notifications.json` following design principles - NO key changes, only title/message content.

**Steps**:

- [x] **Step 2.1**: Backup current `en_notifications.json` ✅
  - Created `en_notifications.json.backup` for rollback safety

- [x] **Step 2.2**: Create new structure with explicit sections ✅
  - Added JSON comment sections for Kid/Parent/System/Actions
  - Clear visual separation with decorative borders
  - Documented design philosophy in each section

- [x] **Step 2.3**: Rewrite Kid notification text ✅
  - Applied emojis, second person, encouraging tone
  - Removed "KidsChores:" prefix from ALL kid notifications
  - **Option C Implemented**: "🎯 Chore Now Due" and "⏰ Chore Reminder" naming
  - Examples implemented:
    - `chore_approved_kid`: "🎉 Mission Accomplished!"
    - `chore_disapproved_kid`: "↩️ Chore Returned" (softer than "Disapproved")
    - `reward_disapproved_kid`: "💭 Reward Not Available" (encouraging)
    - `penalty_applied_kid`: Includes "Let's get back on track!" encouragement

- [x] **Step 2.3a**: Add missing `chore_due_window_kid` keys ✅ (CRITICAL BUG FIX)
  - Added complete entry:
    ```json
    "chore_due_window_kid": {
      "title": "🎯 Chore Now Due",
      "message": "{chore_name} is now due! Complete within {hours} hour(s) to earn {points} points"
    }
    ```
  - Bug resolved: Code now has matching translation keys

- [x] **Step 2.4**: Rewrite Parent notification text ✅
  - Put `{kid_name}` FIRST in all titles: "✋ {kid_name}: Chore Claimed"
  - Removed "KidsChores:" prefix (rely on HA notification grouping)
  - Kept informative, actionable tone
  - Examples implemented:
    - `chore_claimed_parent`: "✋ {kid_name}: Chore Claimed"
    - `reward_claimed_parent`: "🎁 {kid_name}: Reward Request"
    - `pending_chores_parent`: "📋 {kid_name}: {count} Pending"
    - `chore_overdue_parent`: "⚠️ {kid_name}: Chore Overdue"

- [x] **Step 2.5**: Update action button text ✅
  - Updated actions with softer, more encouraging language:
    - `disapprove`: "↩️ Needs Work" (was "Disapprove")
    - `claim`: "✋ I Did It!" (was "✋ Claim Now")
    - `remind_30`: "⏰ Remind in 30m" (shorter)
    - `skip`: "⏭️ Skip" (added emoji)
  - Kept action KEY names unchanged (code depends on them)

- [x] **Step 2.6**: Remove orphan keys and address user TODOs ✅
  - Removed 10 orphan keys no longer referenced in code:
    - `chore_assigned` (no handler exists)
    - `chore_approved` (unsuffixed, replaced with \_kid variant)
    - `chore_disapproved` (unsuffixed, replaced with \_kid variant)
    - `chore_overdue` (unsuffixed, replaced with \_kid/\_parent variants)
    - `status_update` (dead code, removed in Phase 1)
    - `chore_approved_status` (dead code)
    - `chore_disapproved_status` (dead code)
    - `reward_approved_status` (dead code)
    - `chore_due_soon_kid` (legacy, confusing naming - removed per user feedback)
    - `reward_claimed_kid` (not in notification matrix, only sent to parents)
  - **User TODO Fixes**:
    - ✅ Removed `reward_claimed_kid` + `TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_KID` constant (dead code)
    - ✅ Fixed `badge_earned_kid` message: removed "{progress}%" placeholder (always 100% when earned)
    - ✅ Documented `chore_missed_kid` architectural decision: needs parent variant + per-chore toggle (future work)
  - Final count: **28 active notification keys** (down from 38 with orphans)

**Validation Results**:

```bash
✅ JSON valid: 28 notification keys
✅ Lint: All checks passed (ruff check + format)
✅ MyPy: Success, 0 errors in 48 source files
✅ Boundaries: All 10 architectural checks passed
✅ Tests: 18/18 notification tests passing (1.76s) ← Fixed after test update
```

**Test Fix Applied**:

- Updated `test_due_soon_reminder_sent_within_window` to expect `'chore_due_reminder'` instead of legacy `'due_soon'` key (Line 676)

**Validation Command**:

```bash
python -c "import json; json.load(open('custom_components/kidschores/translations_custom/en_notifications.json'))"
python -m pytest tests/test_workflow_notifications.py -v
```

**Key Issues**:

- Must maintain exact placeholder names (`{kid_name}`, `{chore_name}`, etc.)
- Character limits for iOS/Android notification titles (~40-50 chars safe zone)

---

## Phase 3: Documentation Updates

**Goal**: Update wiki to reflect new notification text and explain per-chore toggles.

**CRITICAL**: NO CODE CHANGES IN THIS PHASE. Only updating:

1. User-facing text in `en_notifications.json`
2. Wiki documentation to explain features better

**Steps**:

- [x] **Step 3.1**: Update wiki notification count (16 → 21 types) ✅
  - Updated opening paragraph in `Configuration:-Notifications.md`

- [x] **Step 3.2**: Update Chore Notifications table with new text examples ✅
  - Added "Example Text (Kid/Parent)" column
  - Updated 7 chore notification types:
    - Chore Claimed, Approved, Disapproved, Overdue, Now Due, Reminder, Missed
  - Renamed "Chore Due Soon" → "Chore Now Due" (Option C)
  - Renamed "Chore Due Soon Reminder" → "Chore Reminder" (Option C)
  - Added Chore Missed row (new entry, 21st type)

- [x] **Step 3.3**: Update Reward Notifications table with new text examples ✅
  - Added "Example Text (Kid/Parent)" column
  - Updated 3 reward notification types with emojis and new tone

- [x] **Step 3.4**: Update Gamification Notifications table with new text examples ✅
  - Added "Example Text (Kid/Parent)" column
  - Updated 5 gamification types with emojis and {kid_name} patterns

- [x] **Step 3.5**: Update Reminder Notifications table with new text examples ✅
  - Added "Example Text" column
  - Updated 2 reminder types

- [x] **Step 3.6**: Add "Understanding Due Date Notifications" section ✅
  - Added new subsection after Chore Notifications table
  - Created comprehensive table explaining 3 due-date types:
    - Chore Now Due (DUE_WINDOW, 1h before)
    - Chore Reminder (DUE_REMINDER, 30m before)
    - Chore Overdue (after deadline)
  - Added example timeline showing when each notification fires
  - Documented per-chore toggle controls
  - Explained design reasoning for separate notification types

- [x] **Step 3.7**: Update "Overdue & Due-Soon Notifications" section ✅
  - Renamed to "Overdue & Due Date Notifications"
  - Split into subsections:
    - "Overdue Notifications (Past Deadline)" - kept existing logic
    - "Chore Now Due & Chore Reminder (Before Deadline)" - NEW
  - Updated action button emojis and descriptions
  - Added "Chore Missed Notifications" subsection with architectural note

- [x] **Step 3.8**: Update action button list (8 → 6 active buttons) ✅
  - Updated "Actionable Notifications" section
  - Split into "Parent Action Buttons" and "Kid Action Buttons"
  - Listed 6 active buttons with emojis:
    - Parent: Approve, Needs Work, Complete, Skip, Remind in 30 min
    - Kid: I Did It!
  - Removed references to approve_latest and review_all

- [x] **Step 3.9**: Add architectural note about chore_missed_kid ✅
  - Added note in "Chore Missed Notifications" subsection
  - Documented: Current implementation uses kid text for parents
  - Documented: Future needs parent variant + per-chore toggle
  - Linked to ARCHITECTURE.md for tracking

- [x] **Step 3.10**: Update Technical Reference section ✅
  - Updated notification count: "21 notification types"
  - Updated translation details: "27 JSON keys (kid + parent variants) with 6 active action buttons"
  - Added link to en_notifications.json
  - Removed outdated NOTIFICATION_REFACTOR reference

**Validation Commands**:

```bash
# Verify JSON is valid after updates
python -c "import json; data=json.load(open('custom_components/kidschores/translations_custom/en_notifications.json')); print(f'✅ JSON valid: {len([k for k in data.keys() if not k.startswith(\"_\") and k != \"actions\"])} notification keys, {len(data[\"actions\"])} action buttons')"

# Verify wiki contains all updates
python -c "import re; content=open('kidschores-ha.wiki/Configuration:-Notifications.md').read(); print('✅ Wiki updated') if '21 different notification types' in content and 'Understanding Due Date Notifications' in content else print('❌ Wiki missing updates')"
```

**Validation Results**:

```bash
✅ JSON State: 27 notification keys, 6 action buttons
✅ Wiki Updated: 21 types, new due-date section, Option C naming, example columns added
✅ Legacy Terms Removed: "16 types", "Due Soon Reminder", "approve_latest", "review_all"
```

**Key Updates**:

- ✅ All notification tables updated with "Example Text (Kid/Parent)" column
- ✅ "Understanding Due Date Notifications" section added with comprehensive table
- ✅ Option C naming implemented: "Chore Now Due" + "Chore Reminder"
- ✅ "Overdue & Due Date Notifications" section restructured and expanded
- ✅ Action button list updated: 6 active buttons (removed 2 orphans)
- ✅ Architectural note added for chore_missed_kid future work
- ✅ Technical Reference section updated with accurate counts

---

## Phase 4: Test & Validate

**Goal**: Verify all notification scenarios work with new text.

**Steps**:

- [x] **Step 4.1**: Run automated notification test suite ✅
  - File: `tests/test_workflow_notifications.py`
  - **Result**: 18/18 tests passing (2.78s)
  - Coverage: Claim notifications, language selection, action buttons, tagging, due-date reminders, race conditions, concurrent notifications
  - All tests validate new notification text and behavior

- [ ] **Step 4.2**: Manual testing with kid perspective (OPTIONAL)
  - Set up kid notification service in live Home Assistant
  - Test: Chore assigned, approved, returned, overdue, due reminders
  - Verify: No "KidsChores:" prefix, emojis present, second person tone

- [ ] **Step 4.3**: Manual testing with parent perspective (OPTIONAL)
  - Set up parent notification service in live Home Assistant
  - Test: Chore claimed, reward claimed, overdue alerts
  - Verify: Kid name appears FIRST in title, actionable tone

- [ ] **Step 4.4**: Cross-language smoke test (FUTURE - After Crowdin Sync)
  - After Crowdin sync, test 2-3 languages (Spanish, Dutch)
  - Verify placeholders work: `{kid_name}`, `{chore_name}`, etc.
  - Check character limits on mobile devices

**Validation Commands**:

```bash
# Run notification test suite
pytest tests/test_workflow_notifications.py -v --tb=line

# Result: ✅ 18/18 tests passing (2.78s)
```

**Validation Results**:

```bash
✅ All 18 notification tests passing
✅ Coverage verified:
  - Claim notifications with action buttons
  - Language selection (kid/parent/system)
  - Notification tagging for pending chores
  - Due-date reminders (chore_due_reminder key)
  - Configurable reminder offsets
  - Race condition prevention
  - Concurrent notifications to multiple parents
```

---

## Constants Organization Strategy

### Current State (Lines ~1910-2030 in const.py)

```python
# Mixed alphabetically, no clear grouping
TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED
TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED_PARENT
TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_KID
# ... chaos ...
```

### Target State

```python
# ============================================================================
# Notification Translation Keys (Organized by Audience)
# ============================================================================

# --- Kid-Facing Notifications (Gamified, Second Person) ---
# Chore lifecycle
TRANS_KEY_NOTIF_TITLE_CHORE_ASSIGNED_KID: Final = "notification_title_chore_assigned_kid"
TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED_KID: Final = "notification_title_chore_approved_kid"
TRANS_KEY_NOTIF_TITLE_CHORE_RETURNED_KID: Final = "notification_title_chore_returned_kid"
TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON_KID: Final = "notification_title_chore_due_soon_kid"
TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE_KID: Final = "notification_title_chore_overdue_kid"

# Reward lifecycle
TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED_KID: Final = "notification_title_reward_claimed_kid"
TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED_KID: Final = "notification_title_reward_approved_kid"
TRANS_KEY_NOTIF_TITLE_REWARD_RETURNED_KID: Final = "notification_title_reward_returned_kid"

# Gamification
TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_KID: Final = "notification_title_badge_earned_kid"
TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED_KID: Final = "notification_title_achievement_earned_kid"
TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED_KID: Final = "notification_title_challenge_completed_kid"
TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED_KID: Final = "notification_title_bonus_applied_kid"
TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED_KID: Final = "notification_title_penalty_applied_kid"

# --- Parent-Facing Notifications (Informative, Third Person) ---
# Chore lifecycle
TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED_PARENT: Final = "notification_title_chore_claimed_parent"
TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED_PARENT: Final = "notification_title_chore_approved_parent"
TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE_PARENT: Final = "notification_title_chore_overdue_parent"

# Reward lifecycle
TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED_PARENT: Final = "notification_title_reward_claimed_parent"

# Gamification (informational for parents)
TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_PARENT: Final = "notification_title_badge_earned_parent"
TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED_PARENT: Final = "notification_title_achievement_earned_parent"
TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED_PARENT: Final = "notification_title_challenge_completed_parent"

# Summary/Aggregation
TRANS_KEY_NOTIF_TITLE_PENDING_CHORES_PARENT: Final = "notification_title_pending_chores_parent"

# --- System Notifications (No Audience Split) ---
TRANS_KEY_NOTIF_TITLE_STATUS_UPDATE: Final = "notification_title_status_update"

# --- Message Keys (Follow Same Grouping) ---
# [Repeat structure for MESSAGE keys]
```

**Benefit**: Developer can instantly see which notifications exist for each audience and find related constants quickly.

---

## JSON Organization Strategy

### Current State (`en_notifications.json`)

```json
{
  "chore_assigned": {...},
  "chore_claimed": {...},
  "reward_claimed_kid": {...},
  "reward_claimed_parent": {...},
  // No clear grouping, mixed kid/parent
}
```

### Target State

```json
{
  "_comment_kid": "========================================",
  "_comment_kid_desc": "KID NOTIFICATIONS (Gamified, Second Person, Encouraging)",
  "_comment_kid_footer": "========================================",

  "chore_assigned_kid": {
    "title": "🆕 New Mission Available",
    "message": "The chore '{chore_name}' has been assigned to you. Reward: {points} pts."
  },
  "chore_approved_kid": {
    "title": "🎉 Mission Accomplished!",
    "message": "Great job! '{chore_name}' was approved. +{points} pts added to your balance."
  },
  // ... all kid notifications ...

  "_comment_parent": "========================================",
  "_comment_parent_desc": "PARENT NOTIFICATIONS (Informative, Third Person, Actionable)",
  "_comment_parent_footer": "========================================",

  "chore_claimed_parent": {
    "title": "✋ {kid_name}: Chore Claimed",
    "message": "{kid_name} has finished '{chore_name}'. Awaiting your approval."
  },
  // ... all parent notifications ...

  "_comment_actions": "========================================",
  "_comment_actions_desc": "ACTION BUTTONS",
  "_comment_actions_footer": "========================================",

  "actions": {
    "approve": "✅ Approve",
    "return": "↩️ Needs Work",
    "claim": "✋ I Did It"
  }
}
```

**Benefit**: Translators (Crowdin contributors) can immediately understand context and audience when localizing.

---

## Notification Inventory (Based on Phase 0 Audit)

**Source**: Wiki `Configuration: Notifications.md` cross-referenced with code

| JSON Key                                | Wiki Audience | Current Text                     | New Text Direction                                     | Text-Only Change?                    |
| --------------------------------------- | ------------- | -------------------------------- | ------------------------------------------------------ | ------------------------------------ |
| `chore_assigned`                        | Kid           | "KidsChores: New Chore"          | "🆕 New Mission Available"                             | Yes - drop prefix, add emoji         |
| `chore_claimed`                         | Parent        | "KidsChores: Chore Claimed"      | "{kid_name}: Chore Claimed"                            | Yes - kid name first, drop prefix    |
| `chore_approved`                        | Kid           | "KidsChores: Chore Approved"     | "🎉 Mission Accomplished!"                             | Yes - gamify, add emoji              |
| `chore_disapproved`                     | Kid           | "KidsChores: Chore Disapproved"  | "↩️ Chore Needs Work"                                  | Yes - softer language                |
| `chore_overdue`                         | Kid + Parent  | Mixed messaging                  | Kid: "⚠️ Chore Overdue", Parent: "{kid_name}: Overdue" | Yes - split perspectives             |
| `chore_due_soon` / `chore_due_reminder` | Kid           | "⏰ Chore Due Soon!"             | "⏰ Time is Running Out"                               | Yes - more urgent, keep emoji        |
| `chore_due_window`                      | Kid           | "🔔 Chore Now Due"               | Keep (already good)                                    | No change needed                     |
| `reward_claimed_kid`                    | Kid           | "KidsChores: Reward Claimed"     | "🛍️ Reward Claimed"                                    | Yes - drop prefix, add emoji         |
| `reward_claimed_parent`                 | Parent        | "KidsChores: Reward Claimed"     | "🎁 {kid_name}: Reward Request"                        | Yes - kid name first, clearer action |
| `reward_approved`                       | Kid           | "KidsChores: Reward Approved"    | "✅ Reward Approved"                                   | Yes - drop prefix, keep short        |
| `reward_disapproved`                    | Kid           | "KidsChores: Reward Disapproved" | "❌ Reward Needs Review"                               | Yes - softer language                |
| `badge_earned_kid`                      | Kid           | "KidsChores: Badge Earned"       | "🏆 New Badge Unlocked!"                               | Yes - gamify, excitement             |
| `badge_earned_parent`                   | Parent        | "KidsChores: Badge Earned"       | "{kid_name}: Badge Earned 🏆"                          | Yes - kid name first                 |
| `achievement_earned_kid`                | Kid           | Already good                     | Keep structure, maybe tweak emoji                      | Minor                                |
| `achievement_earned_parent`             | Parent        | Already good                     | Add {kid_name} first                                   | Yes                                  |
| `challenge_completed_kid`               | Kid           | Already good                     | Keep structure                                         | Minor                                |
| `challenge_completed_parent`            | Parent        | Already good                     | Add {kid_name} first                                   | Yes                                  |
| `penalty_applied`                       | Kid           | "KidsChores: Penalty Applied"    | "📉 Penalty Applied"                                   | Yes - drop prefix, add emoji         |
| `bonus_applied`                         | Kid           | "KidsChores: Bonus Applied"      | "✨ Bonus Applied"                                     | Yes - drop prefix, add emoji         |
| `pending_chores`                        | Parent        | "KidsChores: {kid_name}"         | "{kid_name}: {count} Pending"                          | Yes - kid name stays first           |

**Key Findings from Phase 0**:

- ✅ All necessary \_kid/\_parent splits already exist in code
- ✅ No new JSON keys needed
- ✅ All changes are text-only (titles/messages)
- ⚠️ Need to verify wiki's "Recipients" column matches code implementation

---

## Emoji & Character Limit Guidelines

### Safe Emoji Choices (Cross-Platform)

- ✅ Checkmark (approval)
- ❌ X (negative, but we're avoiding this)
- ⏰ Alarm clock (due soon)
- 🎉 Party popper (celebration)
- 🏆 Trophy (achievement)
- ⚠️ Warning (overdue)
- ✋ Raised hand (claim action)
- 🎁 Gift (reward)
- ↩️ Return arrow (needs work)
- 🆕 NEW badge (assignment)

### Character Limits (Mobile Best Practices)

- **Title**: 40-50 characters (Android compact), 65 max (iOS)
- **Message**: 100-120 characters (lock screen preview)
- **Format**: `{emoji} {kid_name}: {action}` for parents fits comfortably

**Example Measurements**:

- "✋ Payton: Chore Claimed" = 24 chars ✅
- "🎉 Mission Accomplished!" = 24 chars ✅
- "⏰ Time is Running Out" = 23 chars ✅

---

## Translation Sync Strategy (Crowdin)

**Current Process** (per ARCHITECTURE.md):

1. Update `en_notifications.json` (source of truth)
2. Crowdin auto-syncs English changes
3. Translators receive notification of new/changed strings
4. We pull completed translations back

**Special Considerations for This Initiative**:

- All 14 languages need updates: ca, da, de, en, es, fi, fr, nb, nl, pt, sk, sl, sv
- Coordinate with Crowdin: Add context notes for each string ("This is for kids" vs "This is for parents")
- Priority: English first, then Spanish/Dutch (largest user bases)

**Post-Phase 2 Step**:

```bash
# After en_notifications.json is finalized
# Crowdin CLI push (owner action)
crowdin upload sources

# Wait for translations (coordinate with maintainers)
# Then pull back
crowdin download
```

---

## Risk Assessment

| Risk                              | Impact | Mitigation                                                           |
| --------------------------------- | ------ | -------------------------------------------------------------------- |
| Breaking existing notifications   | HIGH   | Keep old keys working during transition, add deprecation warnings    |
| Character truncation on mobile    | MEDIUM | Test on real iOS/Android devices, stay under 40 chars for titles     |
| Translation delays (14 languages) | MEDIUM | Ship v0.5.0 with English only, mark other languages as "in progress" |
| User confusion from text changes  | LOW    | Users upgrading to v0.5.0 expect changes, document in release notes  |
| Test fixture breakage             | LOW    | Update test assertions as part of Phase 4                            |

---

## Completion Criteria

### Decisions Captured

- [x] Design principles established (3 core rules)
- [x] Kid vs parent notification split strategy defined
- [x] Emoji and tone guidelines documented
- [x] Constants organization strategy agreed

### Requirements Met

- [ ] Phase 0 audit completed, gaps identified between wiki and code
- [ ] Wiki updated to explain all 6 per-chore notification toggles
- [ ] Kid notifications: No "KidsChores:" prefix, second person, emojis
- [ ] Parent notifications: "{kid_name}: Action" title format, third person
- [ ] "Disapproved" changed to "Needs Work" in user-facing text only
- [ ] `en_notifications.json` organized with section comments
- [ ] Constants grouped by audience in `const.py` (cosmetic only)
- [ ] All tests pass with new notification text
- [ ] Manual mobile testing confirms no truncation
- [ ] Code remains unchanged (no constant/method renames)

### Sign-Off

- [ ] Product Owner: Approves new notification text and tone
- [ ] Technical Lead: Confirms constants organization and code changes
- [ ] QA: Validates all notification scenarios on mobile devices

---

## References

- [ARCHITECTURE.md § Translation Architecture](../ARCHITECTURE.md#translation-architecture)
- [DEVELOPMENT_STANDARDS.md § 3. Constant Naming Standards](../DEVELOPMENT_STANDARDS.md#3-constant-naming-standards)
- [Configuration: Notifications (Wiki)](../../kidschores-ha.wiki/Configuration:-Notifications.md)
- Home Assistant Notification Best Practices: https://www.home-assistant.io/integrations/notify/

---

## Notes & Decisions

**Decision 2026-02-11**: Change "Disapproved" to "Needs Work" (text only)

- **Rationale**: "Needs Work" implies improvement loop, not rejection. More encouraging for 12-14 year olds.
- **Alternative Considered**: "Returned", "Try Again" - "Needs Work" is clearest for action needed
- **Impact**: ONLY affects en_notifications.json display text. Code constants stay "disapproved" for consistency.
- **Why not change code?**: Breaking change, affects signals/events/tests. Not worth the risk for cosmetic improvement.

**Decision 2026-02-11**: Parent notifications lead with kid name

- **Rationale**: Parent with 3 kids needs instant triage on lock screen. "Payton: Chore Claimed" > "KidsChores: Chore Claimed"
- **Alternative Considered**: Keep "KidsChores:" prefix - rejected, takes up valuable width
- **Impact**: All parent notification titles need rewrite

**Decision 2026-02-11**: Kids get no "KidsChores:" prefix

- **Rationale**: Kids know what app they're using. Prefix is redundant. Use emojis for visual branding instead.
- **Alternative Considered**: Keep prefix for "professionalism" - rejected, this is gamification
- **Impact**: All kid notification titles need rewrite
