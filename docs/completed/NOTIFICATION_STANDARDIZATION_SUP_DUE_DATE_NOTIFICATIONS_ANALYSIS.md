# Due Date Notification Types - Analysis & Clarification

**Supporting Document for**: NOTIFICATION_STANDARDIZATION_IN-PROCESS.md
**Created**: 2026-02-11
**Status**: Analysis Complete - Awaiting Decision

---

## Executive Summary

The integration has **THREE** distinct "due date" notification types that serve different purposes in the chore lifecycle. The current naming is confusing because:

1. **Wiki uses "Chore Due Soon"** for what code calls **"DUE_WINDOW"** (state transition notification)
2. **Wiki calls one "Chore Due Soon Reminder"** for what code calls **"DUE_REMINDER"** (configurable reminder before due)
3. **No "Chore Due Soon" in code** - only DUE_WINDOW and DUE_REMINDER

---

## Current Implementation Analysis

### 1. CHORE_DUE_WINDOW (Incorrectly labeled "Due Soon" in wiki)

**Purpose**: Notify kid when chore **transitions from PENDING → DUE state**

**Trigger**:

- Fires when `now_utc` enters the "due window" (configurable offset before due date)
- Default: 1 hour before due date (`const.DEFAULT_DUE_WINDOW_OFFSET = "0d 1h 0m"`)
- Configurable per-chore: `DATA_CHORE_DUE_WINDOW_OFFSET`

**Code Location**: `notification_manager.py` line 2266

```python
def _handle_chore_due_window(self, payload: dict[str, Any]) -> None:
    """Handle CHORE_DUE_WINDOW event - notify kid when chore enters due window (v0.6.0+).

    Triggered when chore transitions from PENDING → DUE state.
    Uses Schedule-Lock pattern to prevent duplicate notifications within same period.
    """
```

**Current Notification Text** (`en_notifications.json`):

- Title: Not defined (code uses `TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW`)
- Message: Not defined (code uses `TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW`)
- **ERROR**: These keys don't exist in en_notifications.json!

**Action Button**: ✅ "Claim Now" action is added

**Toggle Control**: `DATA_CHORE_NOTIFY_ON_DUE_WINDOW` (per-chore setting)

**Schedule-Lock**: Yes - prevents duplicate notifications in same period

---

### 2. CHORE_DUE_REMINDER (Wiki calls "Chore Due Soon Reminder")

**Purpose**: Send **configurable reminder** notification before chore becomes overdue

**Trigger**:

- Fires when `now_utc` enters the "reminder window" (configurable offset before due date)
- Default: 30 minutes before due date (`const.DEFAULT_DUE_REMINDER_OFFSET = "0d 0h 30m"`)
- Configurable per-chore: `DATA_CHORE_DUE_REMINDER_OFFSET`
- **Note**: Can overlap with DUE_WINDOW if reminder offset > window offset (e.g., if user sets reminder to 2 hours)

**Code Location**: `notification_manager.py` line 2337

```python
def _handle_chore_due_reminder(self, payload: dict[str, Any]) -> None:
    """Handle CHORE_DUE_REMINDER event - send reminder to kid with claim button (v0.6.0+).

    Renamed from _handle_chore_due_soon to clarify purpose.
    Uses configurable per-chore `due_reminder_offset` timing.
    Uses Schedule-Lock pattern to prevent duplicate notifications within same period.
    """
```

**Current Notification Text** (`en_notifications.json`):

- Title: `TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON` = "Chore Due Soon" ❌ MISLEADING
- Message: `TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_SOON` = "{chore_name} is due in {minutes} minutes"
- **Legacy Keys**: Code uses `CHORE_DUE_SOON` translation keys for backward compatibility

**Action Button**: ✅ "Claim Now" action is added

**Toggle Control**: `DATA_CHORE_NOTIFY_DUE_REMINDER` (per-chore setting)

**Schedule-Lock**: Yes - prevents duplicate notifications in same period

---

### 3. CHORE_OVERDUE (Separate notification type)

**Purpose**: Notify kid + parents when chore **passes due date without being completed**

**Trigger**:

- Fires when `now_utc > due_date` and chore is still actionable
- Only if `overdue_handling != NEVER_OVERDUE`

**Recipients**: Kid + Parents (separate notifications with different actions)

**Action Buttons**:

- Kid: "Claim Now"
- Parents: "Complete" / "Skip" / "Remind"

---

## The Confusion Problem

### Wiki Table (Current)

| Event                       | Trigger               | What It Means (User Perception)               |
| --------------------------- | --------------------- | --------------------------------------------- |
| **Chore Due Soon**          | Chore due window open | ❌ Vague - "soon" could mean hours or minutes |
| **Chore Due Soon Reminder** | Chore due reminder    | ❌ Sounds redundant with above                |
| **Chore Overdue**           | Chore past due date   | ✅ Clear                                      |

### Code Constants (Current)

| Signal Name          | Handler Name                 | Translation Key                    | Purpose                          |
| -------------------- | ---------------------------- | ---------------------------------- | -------------------------------- |
| `CHORE_DUE_WINDOW`   | `_handle_chore_due_window`   | `TRANS_KEY_NOTIF_TITLE_DUE_WINDOW` | State transition (PENDING → DUE) |
| `CHORE_DUE_REMINDER` | `_handle_chore_due_reminder` | `TRANS_KEY_NOTIF_TITLE_DUE_SOON`   | Reminder before due date         |
| `CHORE_OVERDUE`      | `_handle_chore_overdue`      | `TRANS_KEY_NOTIF_TITLE_OVERDUE`    | Past due date                    |

---

## User's Interpretation (What They Think)

When users see:

- **"Chore Due Soon"** → They think: "The due date is approaching"
- **"Chore Due Soon Reminder"** → They think: "A reminder that the due date is approaching" (redundant?)

**Reality**:

- **DUE_WINDOW** = "Chore has entered its 'due' state (was pending, now available to claim)"
- **DUE_REMINDER** = "Heads up, chore is about to become overdue soon"

---

## Recommended Clarifications

### Option A: Align Wiki to Code Logic

| Notification Name      | Trigger Description                                | User-Friendly Meaning                        |
| ---------------------- | -------------------------------------------------- | -------------------------------------------- |
| **Chore Available**    | Chore enters due window (PENDING → DUE transition) | "You can now claim this chore"               |
| **Chore Due Reminder** | Configurable reminder before due date              | "Reminder: Chore is due soon, don't forget!" |
| **Chore Overdue**      | Chore past due date                                | "Uh oh, this chore is now overdue"           |

**Translation Keys** (New):

```python
TRANS_KEY_NOTIF_TITLE_CHORE_AVAILABLE = "chore_available"
TRANS_KEY_NOTIF_MESSAGE_CHORE_AVAILABLE = "chore_available"
```

**en_notifications.json** (New):

```json
"chore_available": {
  "title": "🎯 Chore Available",
  "message": "{chore_name} is ready to claim! ({hours} hours until due)"
}
```

---

### Option B: Keep "Due Soon" but Clarify Wiki

| Notification Name          | Trigger Description                     | Clarification                                        |
| -------------------------- | --------------------------------------- | ---------------------------------------------------- |
| **Chore Due Window Opens** | Chore enters due window (PENDING → DUE) | "Chore becomes claimable (state changes to 'due')"   |
| **Chore Due Reminder**     | Configurable reminder before due date   | "Reminder notification before chore becomes overdue" |
| **Chore Overdue**          | Chore past due date                     | "Chore is now overdue"                               |

**Keep existing translation keys**, update messages:

```json
"chore_due_window": {
  "title": "🎯 Chore Ready",
  "message": "{chore_name} is now due! You have {hours} hours to complete it (+{points} pts)"
},
"chore_due_soon": {
  "title": "⏰ Reminder",
  "message": "{chore_name} is due in {minutes} minutes - claim it now! (+{points} pts)"
}
```

---

### Option C: Split State Transition from Reminder (Most Clear)

| Notification Name  | Trigger Description                                | User-Friendly Meaning                      |
| ------------------ | -------------------------------------------------- | ------------------------------------------ |
| **Chore Now Due**  | Chore enters due window (PENDING → DUE transition) | "This chore is now due and can be claimed" |
| **Chore Reminder** | Configurable reminder before overdue               | "Don't forget to claim this chore!"        |
| **Chore Overdue**  | Chore past due date                                | "This chore is overdue - claim ASAP"       |

**Remove "Soon" entirely** - it's vague and confusing.

---

## Missing Translation Keys (Bug Found)

**CRITICAL**: Code references translation keys that don't exist in `en_notifications.json`:

```python
# notification_manager.py line 2276
title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW,  # ❌ NOT DEFINED
message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW,  # ❌ NOT DEFINED
```

**Current State**:

- `TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW` exists in const.py
- `TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW` exists in const.py
- **BUT**: `en_notifications.json` has NO `chore_due_window` key
- **Result**: Users likely see raw translation keys or fall back to defaults

---

## Toggle Configuration Analysis

Per-chore settings in config flow:

| Toggle Name (UI)                | Constant                          | Controls Which Notification   |
| ------------------------------- | --------------------------------- | ----------------------------- |
| "Notify When Due Window Starts" | `DATA_CHORE_NOTIFY_ON_DUE_WINDOW` | DUE_WINDOW (state transition) |
| "Notify at Due Reminder Time"   | `DATA_CHORE_NOTIFY_DUE_REMINDER`  | DUE_REMINDER (before overdue) |
| "Notify When Overdue"           | `DATA_CHORE_NOTIFY_ON_OVERDUE`    | OVERDUE (past due date)       |

**Offset Settings**:

- `DATA_CHORE_DUE_WINDOW_OFFSET` - Default: "0d 1h 0m" (1 hour before due)
- `DATA_CHORE_DUE_REMINDER_OFFSET` - Default: "0d 0h 30m" (30 minutes before due)

**Possible Overlap**:

- If user sets DUE_REMINDER offset to 2 hours, it fires BEFORE DUE_WINDOW (1 hour)
- Both notifications could fire for same chore
- Default configuration: Reminder fires 30 min before due, Window fired 30 min earlier (1 hour before)

---

## Recommendations

### 1. Fix Missing Translation Keys (CRITICAL - Phase 2)

Add to `en_notifications.json`:

```json
"chore_due_window": {
  "title": "KidsChores: Chore Now Due",
  "message": "{chore_name} is now due! {hours} hours to complete (+{points} pts)"
}
```

### 2. Clarify Wiki Documentation (Phase 3)

Update table with clear trigger descriptions:

- **DUE_WINDOW**: "When chore enters 'due' state (was pending, now claimable)"
- **DUE_REMINDER**: "Configurable reminder X minutes before overdue"
- **OVERDUE**: "When chore passes due date without completion"

### 3. Consider Renaming (Phase 2 - Text Changes Only)

Most user-friendly approach:

- **"Chore Now Due"** (instead of "Due Soon" or "Due Window")
- **"Chore Reminder"** (instead of "Due Soon Reminder")
- **"Chore Overdue"** (keep as-is)

### 4. Update Toggles in UI (Future - Out of Scope for Text-Only Plan)

Config flow labels should match notification names:

- "Notify when chore becomes due" (instead of "Notify When Due Window Starts")
- "Send reminder before overdue" (instead of "Notify at Due Reminder Time")

---

## Implementation Impact

### Phase 1 (Constants Organization)

- No changes needed - constants are already well-organized

### Phase 2 (JSON Text Rewrite)

- **MUST ADD**: `chore_due_window` key (missing)
- **SHOULD UPDATE**: `chore_due_soon` → `chore_due_reminder` (rename for clarity)
- Update message templates to reflect state transitions vs reminders

### Phase 3 (Wiki Documentation)

- Update notification table with clear trigger descriptions
- Add explanation of DUE_WINDOW vs DUE_REMINDER vs OVERDUE
- Document offset settings and potential overlaps

### Phase 4 (Testing)

- Verify DUE_WINDOW notification appears with correct text
- Test overlap scenario (reminder offset > window offset)
- Validate Schedule-Lock prevents duplicates

---

## Decision Made ✅

**CHOSEN**: **Option C** - "Chore Now Due" + "Chore Reminder"

**Rationale**:

- Simplest user-facing names
- Removes confusing "Soon" terminology
- Text-only changes in JSON (no code changes required)
- Clear distinction between state transition and reminder

**Implementation**:

- Phase 2: Update en_notifications.json with new naming
- Phase 3: Update wiki documentation to explain difference
- No code changes required - only translation text updates
