# Due Window Notifications - Implementation Analysis

**Supporting Document for**: [DUE_WINDOW_FEATURE_IN-PROCESS.md](DUE_WINDOW_FEATURE_IN-PROCESS.md)

**Purpose**: Detailed technical analysis for implementing Phase 4 (Enhanced Notifications & Automation) of the Due Window Feature.

**Created**: January 28, 2026

---

## Executive Summary

The Due Window Feature introduces a new **DUE** state that activates X hours/days before a chore's due date. Phase 4 requires integrating this new state into the notification system and replacing the legacy fixed 30-minute reminder system with a configurable notification architecture.

**Key Changes Required**:

1. **Migrate** from hardcoded 30-minute reminder to configurable per-chore timing
2. **Add** new due window start notifications (PENDING → DUE transition)
3. **Consolidate** timing logic using existing duration parser
4. **Clean up** legacy reminder tracking system
5. **Extend** notification preferences for dual notification types

---

## Current System Architecture

### 1. Existing 30-Minute Reminder System

**Location**: `managers/chore_manager.py` lines 3527-3639

**How It Works**:

```python
async def check_chore_due_reminders(self) -> None:
    """Check for chores due soon and send reminder notifications (v0.5.0+).

    Hooks into coordinator refresh cycle (typically every 5 min) to check for
    chores that are due within the next 30 minutes and haven't had reminders sent.

    Tracking uses coordinator's transient _due_soon_reminders_sent set.
    """
    reminder_window = timedelta(minutes=30)  # ❌ HARDCODED
```

**Architecture Pattern**:

- **Trigger**: Coordinator refresh cycle (every 5 minutes)
- **Tracking**: Transient set `coordinator._due_soon_reminders_sent`
  - Format: `"{chore_id}:{kid_id}"`
  - Cleared on: Chore claim, approval, or HA restart
  - Prevents duplicate reminders
- **Event**: Emits `SIGNAL_SUFFIX_CHORE_DUE_SOON` with payload
- **Handler**: `NotificationManager._handle_chore_due_soon()` sends notification

**Signal Flow**:

```
ChoreManager.check_chore_due_reminders()
  └─> emit(SIGNAL_SUFFIX_CHORE_DUE_SOON, payload={kid_id, chore_id, chore_name, minutes, points})
        └─> NotificationManager._handle_chore_due_soon(payload)
              └─> notify_kid_translated(TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON)
```

**Notification Constants** (const.py):

- Signal: `SIGNAL_SUFFIX_CHORE_DUE_SOON` (line 80)
- Title: `TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON` (line 1694)
- Message: `TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_SOON` (line 1723)

**Cleanup Mechanism**:

```python
# managers/chore_manager.py line 2049
def clear_chore_due_reminder(self, chore_id: str, kid_id: str) -> None:
    """Clear due-soon reminder tracking for a chore+kid combination (v0.5.0+)."""
    reminder_key = f"{chore_id}:{kid_id}"
    self._coordinator._due_soon_reminders_sent.discard(reminder_key)
```

**Called From**:

- `claim_chore()` (line 246) - Clear when kid claims chore
- Presumably on approval/completion (need to verify)

---

### 2. Due Window State System (Phase 2 - Already Implemented)

**Location**: `managers/chore_manager.py` lines 1704-1763

**Storage Fields** (per-chore in `.storage/kidschores_data`):

```python
DATA_CHORE_DUE_WINDOW_OFFSET: Final = "chore_due_window_offset"  # Duration string "1d 6h 30m"
DATA_CHORE_DUE_REMINDER_OFFSET: Final = "chore_due_reminder_offset"  # Duration string "30m"
DATA_CHORE_NOTIFY_ON_DUE_WINDOW: Final = "notify_on_due_window"  # Boolean
DATA_CHORE_NOTIFY_DUE_REMINDER: Final = "notify_due_reminder"  # Boolean
```

**Defaults**:

```python
DEFAULT_DUE_WINDOW_OFFSET: Final = "0"  # Disabled by default
DEFAULT_DUE_REMINDER_OFFSET: Final = "30m"  # 30 minutes before due (configurable now)
DEFAULT_NOTIFY_ON_DUE_WINDOW = False  # Don't notify on due window start by default
DEFAULT_NOTIFY_DUE_REMINDER = True  # Notify on due reminder by default
```

**State Calculation Logic**:

```python
def chore_is_due(self, kid_id: str | None, chore_id: str) -> bool:
    """Check if a chore is in the due window (approaching due date).

    A chore is in the due window if:
    - It has a due_window_offset > 0 configured
    - Current time is within: (due_date - due_window_offset) <= now < due_date
    - The chore is not already overdue, claimed, or approved
    """
```

**Already Works For**:

- ✅ ChoreStatusSensor calculates DUE state (sensor.py line 765)
- ✅ Dashboard helper groups DUE chores in "today" bucket
- ✅ State icons/colors defined
- ✅ Attributes: `due_window_start`, `time_until_due`

**Duration Parser** (already exists in `utils/dt_utils.py` line 495):

```python
def dt_parse_duration(value: str | None) -> timedelta | None:
    """Parse duration string to timedelta.

    Examples:
    - "30" or "30m" → 30 minutes (default unit)
    - "2h" → 2 hours
    - "1d 6h 30m" → compound duration (1 day, 6 hours, 30 minutes)
    - "0" → returns timedelta(0) (disabled)
    - None or "" → returns None
    """
```

---

## Problem Statement

### Issues with Current System

1. **Hardcoded Timing**: 30-minute reminder window is fixed in code
   - Cannot be customized per chore
   - Doesn't respect `DATA_CHORE_DUE_REMINDER_OFFSET` field
   - Users expect configurability (field exists in UI but unused)

2. **No Due Window Notifications**: System tracks DUE state but doesn't notify
   - `DATA_CHORE_NOTIFY_ON_DUE_WINDOW` field exists but unused
   - No signal emission on PENDING → DUE transition
   - Users don't know when chores enter due window

3. **Dual Notification Confusion**: Overlap potential
   - Due window start: e.g., "Chore due in 1 day"
   - Due reminder: e.g., "Chore due in 30 minutes"
   - Both could trigger for same chore if timing overlaps

4. **Legacy Naming**: "due-soon" terminology confusing
   - Signal: `CHORE_DUE_SOON` actually means "due reminder"
   - Should be renamed for clarity

5. **Incomplete Cleanup**: Reminder tracking not cleared consistently
   - Cleared on claim (line 246)
   - NOT cleared on approval/disapproval
   - NOT cleared on skip
   - Could lead to stale tracking entries

---

## Migration Strategy

### Backward Compatibility Requirements

**Non-Breaking Changes**:

- Existing chores with no `due_reminder_offset` will use default "30m"
- Existing chores with no `due_window_offset` will remain disabled ("0")
- Notification behavior changes only affect chores with new settings configured

**Data Migration**: NOT REQUIRED

- All fields already exist in storage (Phase 1b complete)
- Schema version remains unchanged (v42)
- Default values ensure backward compatibility

**Translation Keys**: EXTEND (not replace)

- Keep existing: `TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON`, `TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_SOON`
- Add new: `TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW`, `TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW`
- Reasoning: Due reminder != due window notification (different contexts)

---

## Proposed Architecture

### 1. Dual Notification System

**Two Independent Notification Types**:

| Type             | Trigger Event                 | Timing                           | User Message                                   | Per-Chore Control             |
| ---------------- | ----------------------------- | -------------------------------- | ---------------------------------------------- | ----------------------------- |
| **Due Window**   | PENDING → DUE state           | `due_date - due_window_offset`   | "Chore '{name}' is now due (X time remaining)" | `notify_on_due_window` (bool) |
| **Due Reminder** | Within reminder offset window | `due_date - due_reminder_offset` | "Reminder: Chore '{name}' due in X minutes"    | `notify_due_reminder` (bool)  |

**Example Scenario**:

```
Chore: "Clean Room"
Due Date: Monday 6:00 PM
Due Window Offset: "1d" (1 day)
Due Reminder Offset: "30m" (30 minutes)

Timeline:
Sunday 6:00 PM  →  DUE WINDOW notification: "Clean Room is now due (24 hours remaining)"
Monday 5:30 PM  →  DUE REMINDER notification: "Reminder: Clean Room due in 30 minutes"
Monday 6:00 PM  →  OVERDUE (existing logic continues)
```

**Deduplication Logic**:

- Track both types independently
- `_due_window_notif_sent: set[str]` (NEW)
- `_due_reminder_notif_sent: set[str]` (RENAME from `_due_soon_reminders_sent`)
- Format: `"{chore_id}:{kid_id}"`

---

### 2. Implementation Phases

#### Phase 4.1: Rename & Refactor Legacy System

**Goal**: Make existing 30-minute system use `due_reminder_offset`

**Changes**:

1. Rename signal: `SIGNAL_SUFFIX_CHORE_DUE_SOON` → `SIGNAL_SUFFIX_CHORE_DUE_REMINDER`
2. Rename tracking: `_due_soon_reminders_sent` → `_due_reminder_notif_sent`
3. Rename method: `check_chore_due_reminders()` (keep name, change logic)
4. Rename handler: `_handle_chore_due_soon()` → `_handle_chore_due_reminder()`

**Updated Logic** (`managers/chore_manager.py`):

```python
async def check_chore_due_reminders(self) -> None:
    """Check for chores within due reminder window and send reminder notifications.

    Uses per-chore `due_reminder_offset` field (default "30m").
    Respects per-chore `notify_due_reminder` setting.
    """
    now_utc = dt_util.utcnow()

    for chore_id, chore_info in self._coordinator.chores_data.items():
        # Check if reminder notifications enabled for this chore
        if not chore_info.get(
            const.DATA_CHORE_NOTIFY_DUE_REMINDER, const.DEFAULT_NOTIFY_DUE_REMINDER
        ):
            continue

        # Get configurable reminder offset (replaces hardcoded 30 minutes)
        reminder_offset_str = chore_info.get(
            const.DATA_CHORE_DUE_REMINDER_OFFSET,
            const.DEFAULT_DUE_REMINDER_OFFSET,
        )
        reminder_offset = dt_parse_duration(reminder_offset_str)
        if not reminder_offset or reminder_offset.total_seconds() <= 0:
            continue

        for kid_id in assigned_kids:
            reminder_key = f"{chore_id}:{kid_id}"

            # Skip if already sent this reminder
            if reminder_key in self._coordinator._due_reminder_notif_sent:
                continue

            # Get due date...
            due_dt = dt_to_utc(due_date_str)
            time_until_due = due_dt - now_utc

            # Check: due within reminder window AND not past due yet
            if timedelta(0) < time_until_due <= reminder_offset:
                # Emit event
                self.emit(
                    const.SIGNAL_SUFFIX_CHORE_DUE_REMINDER,  # Renamed signal
                    kid_id=kid_id,
                    chore_id=chore_id,
                    chore_name=chore_name,
                    minutes=int(time_until_due.total_seconds() / 60),
                    points=points,
                )

                self._coordinator._due_reminder_notif_sent.add(reminder_key)
```

**Constants to Update** (`const.py`):

```python
# Signals (rename)
SIGNAL_SUFFIX_CHORE_DUE_REMINDER: Final = "chore_due_reminder"  # Was: chore_due_soon

# Keep existing translation keys (don't break translations)
TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON: Final = "notification_title_chore_due_soon"
TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_SOON: Final = "notification_message_chore_due_soon"
```

**Coordinator** (`coordinator.py`):

```python
# Rename tracking set
self._due_reminder_notif_sent: set[str] = set()  # Was: _due_soon_reminders_sent
```

---

#### Phase 4.2: Add Due Window Notifications

**Goal**: Notify when chores transition from PENDING → DUE

**New Method** (`managers/chore_manager.py`):

```python
async def check_chore_due_window_transitions(self) -> None:
    """Check for chores entering due window and send notifications.

    Emits SIGNAL_SUFFIX_CHORE_DUE_WINDOW when a chore transitions
    from PENDING to DUE state (entering the due window).

    Uses per-chore `due_window_offset` field.
    Respects per-chore `notify_on_due_window` setting.
    """
    now_utc = dt_util.utcnow()

    for chore_id, chore_info in self._coordinator.chores_data.items():
        # Check if due window notifications enabled for this chore
        if not chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW,
            const.DEFAULT_NOTIFY_ON_DUE_WINDOW,
        ):
            continue

        # Get due window offset
        due_window_offset_str = chore_info.get(
            const.DATA_CHORE_DUE_WINDOW_OFFSET,
            const.DEFAULT_DUE_WINDOW_OFFSET,
        )
        due_window_offset = dt_parse_duration(due_window_offset_str)
        if not due_window_offset or due_window_offset.total_seconds() <= 0:
            continue

        for kid_id in assigned_kids:
            window_key = f"{chore_id}:{kid_id}"

            # Skip if already sent this notification
            if window_key in self._coordinator._due_window_notif_sent:
                continue

            # Skip if already claimed/approved
            if self.chore_has_pending_claim(kid_id, chore_id):
                continue
            if self.chore_is_approved_in_period(kid_id, chore_id):
                continue

            # Check if chore just entered due window
            if self.chore_is_due(kid_id, chore_id):
                # Calculate time remaining until due
                due_dt = self.get_chore_due_date(kid_id, chore_id)
                time_until_due = due_dt - now_utc

                # Emit event
                self.emit(
                    const.SIGNAL_SUFFIX_CHORE_DUE_WINDOW,
                    kid_id=kid_id,
                    chore_id=chore_id,
                    chore_name=chore_info.get(const.DATA_CHORE_NAME, "Unknown"),
                    points=chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0),
                    hours_remaining=int(time_until_due.total_seconds() / 3600),
                    due_date=due_dt.isoformat(),
                )

                self._coordinator._due_window_notif_sent.add(window_key)

                const.LOGGER.debug(
                    "Sent due window notification for chore '%s' to kid '%s'",
                    chore_info.get(const.DATA_CHORE_NAME),
                    kid_id,
                )
```

**Coordinator Hook**:

```python
# coordinator.py - add to refresh cycle
async def _async_update_data(self) -> dict[str, Any]:
    """Refresh coordinator data."""

    # Existing overdue checks
    await self.chore_manager.update_overdue_status()

    # NEW: Check due window transitions
    await self.chore_manager.check_chore_due_window_transitions()

    # Existing due reminder checks (now configurable)
    await self.chore_manager.check_chore_due_reminders()

    return self._data
```

**New Constants** (`const.py`):

```python
# Signals
SIGNAL_SUFFIX_CHORE_DUE_WINDOW: Final = "chore_due_window"

# Translation keys
TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW: Final = "notification_title_chore_due_window"
TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW: Final = "notification_message_chore_due_window"
```

**Notification Handler** (`managers/notification_manager.py`):

```python
async def async_setup(self) -> None:
    """Set up notification manager with event subscriptions."""

    # Existing subscriptions...

    # NEW: Due window notifications
    self.listen(const.SIGNAL_SUFFIX_CHORE_DUE_WINDOW, self._handle_chore_due_window)

@callback
def _handle_chore_due_window(self, payload: dict[str, Any]) -> None:
    """Handle CHORE_DUE_WINDOW event - notify kid when chore enters due window.

    Args:
        payload: Event data containing kid_id, chore_id, chore_name,
                 hours_remaining, points, due_date
    """
    kid_id = payload.get("kid_id", "")
    chore_id = payload.get("chore_id", "")
    chore_name = payload.get("chore_name", "Unknown Chore")
    hours_remaining = payload.get("hours_remaining", 0)
    points = payload.get("points", 0)

    if not kid_id or not chore_id:
        return

    # Notify kid with claim action
    self.hass.async_create_task(
        self.notify_kid_translated(
            kid_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW,
            message_data={
                "chore_name": chore_name,
                "hours": hours_remaining,
                "points": points,
            },
            actions=self.build_claim_action(kid_id, chore_id),
        )
    )

    const.LOGGER.debug(
        "NotificationManager: Sent due window notification for chore=%s to kid=%s (%d hrs)",
        chore_name,
        kid_id,
        hours_remaining,
    )
```

**Translations** (`translations/en.json`):

```json
{
  "notification_title_chore_due_window": "🔔 Chore Now Due",
  "notification_message_chore_due_window": "'{chore_name}' is now due! Complete it within {hours} hour(s) to earn {points} points."
}
```

---

#### Phase 4.3: Enhanced Cleanup Logic

**Goal**: Clear notification tracking consistently across all chore state transitions

**Update Cleanup Method** (`managers/chore_manager.py`):

```python
def clear_chore_notifications(self, chore_id: str, kid_id: str) -> None:
    """Clear ALL notification tracking for a chore+kid combination.

    Clears both due window and due reminder tracking to allow fresh
    notifications in next period.

    Called when:
    - Chore claimed
    - Chore approved/disapproved
    - Chore skipped
    - Chore reset

    Args:
        chore_id: The chore's internal ID
        kid_id: The kid's internal ID
    """
    key = f"{chore_id}:{kid_id}"

    # Clear both tracking sets
    self._coordinator._due_window_notif_sent.discard(key)
    self._coordinator._due_reminder_notif_sent.discard(key)

    const.LOGGER.debug(
        "Cleared notification tracking for chore=%s, kid=%s",
        chore_id,
        kid_id,
    )
```

**Call Sites** (add to existing methods):

```python
async def claim_chore(self, kid_id: str, chore_id: str) -> None:
    """Claim a chore."""
    # ... existing logic ...
    self.clear_chore_notifications(chore_id, kid_id)  # ✅ Already called

async def approve_chore(self, kid_id: str, chore_id: str) -> None:
    """Approve a chore."""
    # ... existing logic ...
    self.clear_chore_notifications(chore_id, kid_id)  # ✅ ADD THIS

async def disapprove_chore(self, kid_id: str, chore_id: str) -> None:
    """Disapprove a chore."""
    # ... existing logic ...
    self.clear_chore_notifications(chore_id, kid_id)  # ✅ ADD THIS

async def skip_chore(self, kid_id: str, chore_id: str) -> None:
    """Skip a chore."""
    # ... existing logic ...
    self.clear_chore_notifications(chore_id, kid_id)  # ✅ ADD THIS

async def reset_chore(self, kid_id: str, chore_id: str) -> None:
    """Reset a chore to pending."""
    # ... existing logic ...
    self.clear_chore_notifications(chore_id, kid_id)  # ✅ ADD THIS
```

---

### 3. Testing Strategy

#### Unit Tests (new file: `tests/test_notification_due_window.py`)

**Test Coverage**:

1. ✅ Due window notification triggers at correct time
2. ✅ Due reminder notification triggers at configured offset (not hardcoded 30m)
3. ✅ Notifications respect per-chore enable/disable settings
4. ✅ Deduplication prevents duplicate notifications
5. ✅ Cleanup clears tracking on all state transitions
6. ✅ Both notification types can coexist for same chore
7. ✅ Default values maintain backward compatibility

**Test Fixtures** (`conftest.py`):

```python
@pytest.fixture
def chore_with_due_window(coordinator: KidsChoresDataCoordinator) -> str:
    """Create chore with due window and due reminder configured."""
    chore_data = {
        const.DATA_CHORE_NAME: "Test Chore",
        const.DATA_CHORE_DEFAULT_POINTS: 10,
        const.DATA_CHORE_DUE_DATE: (dt_util.utcnow() + timedelta(hours=2)).isoformat(),
        const.DATA_CHORE_DUE_WINDOW_OFFSET: "1h",  # Due window starts 1 hour before
        const.DATA_CHORE_DUE_REMINDER_OFFSET: "30m",  # Reminder at 30 min before
        const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW: True,
        const.DATA_CHORE_NOTIFY_DUE_REMINDER: True,
    }
    chore_id = coordinator.chore_manager.create_chore(chore_data)
    return chore_id
```

**Example Test**:

```python
async def test_due_window_notification_timing(
    hass: HomeAssistant,
    coordinator: KidsChoresDataCoordinator,
    chore_with_due_window: str,
    kid_id: str,
) -> None:
    """Test due window notification triggers at correct time."""

    # Advance time to due window start (1 hour before due)
    with freeze_time(dt_util.utcnow() + timedelta(minutes=60)):
        await coordinator.chore_manager.check_chore_due_window_transitions()

    # Verify signal emitted
    assert_signal_emitted(
        const.SIGNAL_SUFFIX_CHORE_DUE_WINDOW,
        kid_id=kid_id,
        chore_id=chore_with_due_window,
    )

    # Verify tracking set updated
    key = f"{chore_with_due_window}:{kid_id}"
    assert key in coordinator._due_window_notif_sent
```

#### Integration Tests (existing file: `tests/test_workflow_chore_notifications.py`)

**Scenarios to Add**:

1. Complete chore lifecycle with both notification types
2. Disable due window, enable reminder only
3. Enable due window, disable reminder only
4. Different timing configurations (1d window, 2h reminder, etc.)

---

### 4. Documentation Updates

#### User-Facing Wiki Updates

**File**: `kidschores-ha.wiki/Configuration:-Chores.md`

**Section to Add**:

````markdown
### Due Window & Reminder Notifications

Control when kids receive notifications as chores approach their due dates:

#### Due Window Notification

Triggers when a chore enters its "due window" (state changes from Pending → Due).

- **Setting**: `notify_on_due_window` (checkbox)
- **Timing**: `due_window_offset` (e.g., "1d" = notify 1 day before due)
- **Message**: "'{chore_name}' is now due! Complete it within X hours to earn Y points."
- **Use Case**: Early warning for larger tasks that take time to complete

#### Due Reminder Notification

Triggers shortly before the chore is actually due (legacy "due soon" reminder).

- **Setting**: `notify_due_reminder` (checkbox)
- **Timing**: `due_reminder_offset` (default "30m" = notify 30 minutes before due)
- **Message**: "Reminder: '{chore_name}' due in X minutes"
- **Use Case**: Last-minute nudge before deadline hits

#### Example Configuration

**Scenario**: Weekly room cleaning due Sunday 6 PM

```yaml
Chore Settings:
  Due Window Offset: "1d" # Saturday 6 PM notification
  Due Reminder Offset: "1h" # Sunday 5 PM notification
  Notify on Due Window: ✅ Yes
  Notify Due Reminder: ✅ Yes
```
````

**Timeline**:

- **Saturday 6:00 PM**: 🔔 "Clean Room is now due! Complete it within 24 hours..."
- **Sunday 5:00 PM**: 🔔 "Reminder: Clean Room due in 60 minutes"
- **Sunday 6:00 PM**: Chore becomes OVERDUE (existing notification)

#### Best Practices

- **Both enabled**: Use for important recurring chores (homework, bedtime routine)
- **Window only**: Use for flexible tasks that don't require last-minute urgency
- **Reminder only**: Use for quick tasks where advance notice isn't needed
- **Both disabled**: Use for chores you'll manage manually or with automations

````

**File**: `kidschores-ha.wiki/Technical:-Notifications.md`

**Section to Update**:
```markdown
## Chore Due Date Notifications (v0.6.0+)

Two independent notification types for chore due dates:

### 1. Due Window Notification (NEW in v0.6.0)

**Trigger**: Chore state transitions from PENDING → DUE
**Signal**: `chore_due_window`
**Per-Chore Settings**:
- `notify_on_due_window` (bool, default: False)
- `due_window_offset` (duration string, default: "0" = disabled)

### 2. Due Reminder Notification (Enhanced in v0.6.0)

**Trigger**: Current time within `due_reminder_offset` before due date
**Signal**: `chore_due_reminder` (renamed from `chore_due_soon`)
**Per-Chore Settings**:
- `notify_due_reminder` (bool, default: True)
- `due_reminder_offset` (duration string, default: "30m")

### Migration Notes (v0.5.0 → v0.6.0)

- Signal renamed: `chore_due_soon` → `chore_due_reminder` (better reflects purpose)
- Hardcoded 30-minute window now configurable via `due_reminder_offset`
- Translation keys unchanged for backward compatibility
- Tracking set renamed: `_due_soon_reminders_sent` → `_due_reminder_notif_sent`
````

---

## File-by-File Change Summary

### `const.py`

**Add**:

```python
# Line ~80 - Signals
SIGNAL_SUFFIX_CHORE_DUE_WINDOW: Final = "chore_due_window"
SIGNAL_SUFFIX_CHORE_DUE_REMINDER: Final = "chore_due_reminder"  # Renamed from chore_due_soon

# Line ~1694 - Notification Translation Keys
TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW: Final = "notification_title_chore_due_window"
TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW: Final = "notification_message_chore_due_window"
```

**Keep (don't change)**:

```python
# Maintain for backward compatibility
TRANS_KEY_NOTIF_TITLE_CHORE_DUE_SOON: Final = "notification_title_chore_due_soon"
TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_SOON: Final = "notification_message_chore_due_soon"
```

---

### `coordinator.py`

**Rename**:

```python
# Line ~109 - Change tracking set name
self._due_reminder_notif_sent: set[str] = set()  # Was: _due_soon_reminders_sent
```

**Add**:

```python
# Line ~110 - Add new tracking set
self._due_window_notif_sent: set[str] = set()
```

**Update refresh cycle** (in `_async_update_data()`):

```python
async def _async_update_data(self) -> dict[str, Any]:
    """Refresh coordinator data."""

    # Existing
    await self.chore_manager.update_overdue_status()

    # NEW: Check due window transitions
    await self.chore_manager.check_chore_due_window_transitions()

    # Existing (but now uses configurable offsets)
    await self.chore_manager.check_chore_due_reminders()

    return self._data
```

---

### `managers/chore_manager.py`

**1. Update existing method** (`check_chore_due_reminders()`):

- Replace `reminder_window = timedelta(minutes=30)` with:
  ```python
  reminder_offset_str = chore_info.get(
      const.DATA_CHORE_DUE_REMINDER_OFFSET,
      const.DEFAULT_DUE_REMINDER_OFFSET,
  )
  reminder_offset = dt_parse_duration(reminder_offset_str)
  ```
- Change signal: `SIGNAL_SUFFIX_CHORE_DUE_SOON` → `SIGNAL_SUFFIX_CHORE_DUE_REMINDER`
- Update tracking set: `_due_soon_reminders_sent` → `_due_reminder_notif_sent`
- Add per-chore enable check:
  ```python
  if not chore_info.get(
      const.DATA_CHORE_NOTIFY_DUE_REMINDER, const.DEFAULT_NOTIFY_DUE_REMINDER
  ):
      continue
  ```

**2. Add new method** (`check_chore_due_window_transitions()`):

- See Phase 4.2 implementation above

**3. Rename cleanup method**:

```python
def clear_chore_notifications(self, chore_id: str, kid_id: str) -> None:
    """Clear ALL notification tracking (was: clear_chore_due_reminder)."""
    key = f"{chore_id}:{kid_id}"
    self._coordinator._due_window_notif_sent.discard(key)
    self._coordinator._due_reminder_notif_sent.discard(key)
```

**4. Add cleanup calls** (in existing methods):

- `approve_chore()` → add `self.clear_chore_notifications(chore_id, kid_id)`
- `disapprove_chore()` → add `self.clear_chore_notifications(chore_id, kid_id)`
- `skip_chore()` → add `self.clear_chore_notifications(chore_id, kid_id)`
- `reset_chore()` → add `self.clear_chore_notifications(chore_id, kid_id)`

---

### `managers/notification_manager.py`

**1. Update `async_setup()`**:

```python
async def async_setup(self) -> None:
    """Set up notification manager with event subscriptions."""

    # Existing subscriptions...

    # Update existing subscription (signal name change)
    self.listen(const.SIGNAL_SUFFIX_CHORE_DUE_REMINDER, self._handle_chore_due_reminder)

    # NEW: Add due window subscription
    self.listen(const.SIGNAL_SUFFIX_CHORE_DUE_WINDOW, self._handle_chore_due_window)
```

**2. Rename handler method**:

```python
@callback
def _handle_chore_due_reminder(self, payload: dict[str, Any]) -> None:
    """Handle CHORE_DUE_REMINDER event (was: _handle_chore_due_soon)."""
    # Update signal constant references
    # Keep notification logic same (just uses new signal name)
```

**3. Add new handler**:

```python
@callback
def _handle_chore_due_window(self, payload: dict[str, Any]) -> None:
    """Handle CHORE_DUE_WINDOW event."""
    # See Phase 4.2 implementation above
```

---

### `translations/en.json`

**Add new keys** (under appropriate sections):

```json
{
  "notification_title_chore_due_window": "🔔 Chore Now Due",
  "notification_message_chore_due_window": "'{chore_name}' is now due! Complete it within {hours} hour(s) to earn {points} points."
}
```

**Keep existing keys** (unchanged):

```json
{
  "notification_title_chore_due_soon": "⏰ Chore Due Soon",
  "notification_message_chore_due_soon": "'{chore_name}' is due in {minutes} minute(s)! Complete it now to earn {points} points."
}
```

---

## Risk Assessment

### High Risk

**None identified** - All changes are additive or internal refactoring

### Medium Risk

1. **Notification Spam**: Both notification types could fire close together
   - **Mitigation**: Clear documentation, sensible defaults, per-chore controls
   - **Detection**: Monitor logs for notification frequency patterns

2. **Tracking Set Memory**: Two tracking sets could grow large over time
   - **Mitigation**: Sets are transient (cleared on HA restart), entries removed on state transitions
   - **Detection**: Monitor coordinator memory usage (already tracked)

### Low Risk

1. **Signal Rename**: `CHORE_DUE_SOON` → `CHORE_DUE_REMINDER`
   - **Impact**: Internal only, no user-facing changes
   - **Mitigation**: Comprehensive test coverage

2. **Translation Key Reuse**: Keeping `CHORE_DUE_SOON` keys for reminder notifications
   - **Impact**: Slight semantic mismatch but maintains compatibility
   - **Mitigation**: Clear code comments explaining legacy naming

---

## Performance Considerations

### Coordinator Refresh Cycle Impact

**Current Load** (every 5 minutes):

- `update_overdue_status()` - Existing
- `check_chore_due_reminders()` - Existing

**New Load** (every 5 minutes):

- `check_chore_due_window_transitions()` - NEW

**Analysis**:

- Both new/updated methods iterate through chores and assigned kids (same pattern as existing)
- Additional cost: ~1 extra datetime comparison per chore-kid pair
- Expected impact: Negligible (same O(n\*m) complexity as existing checks)

**Optimization Opportunities** (if needed):

- Combine both checks into single loop (micro-optimization)
- Cache due date calculations (minimal benefit)
- **Recommendation**: Implement separately first, optimize only if performance issues observed

---

## Success Criteria

### Phase 4 Complete When:

- [x] **Architecture analysis** complete (this document)
- [ ] Due reminder system uses configurable `due_reminder_offset` (not hardcoded 30min)
- [ ] Due window notifications trigger on PENDING → DUE transitions
- [ ] Both notification types can be enabled/disabled per chore
- [ ] Notification tracking cleared consistently across all state transitions
- [ ] Signal names reflect purpose (`CHORE_DUE_REMINDER`, `CHORE_DUE_WINDOW`)
- [ ] Translation keys added for new notification type
- [ ] Test coverage ≥95% for new notification logic
- [ ] Wiki documentation updated with user guidance
- [ ] All quality gates pass:
  - `./utils/quick_lint.sh --fix` ✅
  - `mypy custom_components/kidschores/` ✅
  - `python -m pytest tests/test_notification*.py -v` ✅

---

## Appendix A: Constants Reference

### Existing Constants (Already Defined)

**Storage Fields**:

```python
DATA_CHORE_DUE_WINDOW_OFFSET: Final = "chore_due_window_offset"
DATA_CHORE_DUE_REMINDER_OFFSET: Final = "chore_due_reminder_offset"
DATA_CHORE_NOTIFY_ON_DUE_WINDOW: Final = "notify_on_due_window"
DATA_CHORE_NOTIFY_DUE_REMINDER: Final = "notify_due_reminder"
```

**Defaults**:

```python
DEFAULT_DUE_WINDOW_OFFSET: Final = "0"  # Disabled
DEFAULT_DUE_REMINDER_OFFSET: Final = "30m"  # 30 minutes
DEFAULT_NOTIFY_ON_DUE_WINDOW = False
DEFAULT_NOTIFY_DUE_REMINDER = True
```

**States**:

```python
CHORE_STATE_PENDING = "pending"
CHORE_STATE_DUE = "due"  # NEW in Phase 2
CHORE_STATE_OVERDUE = "overdue"
CHORE_STATE_CLAIMED = "claimed"
CHORE_STATE_APPROVED = "approved"
```

### New Constants (To Be Added)

**Signals**:

```python
SIGNAL_SUFFIX_CHORE_DUE_WINDOW: Final = "chore_due_window"
SIGNAL_SUFFIX_CHORE_DUE_REMINDER: Final = "chore_due_reminder"
```

**Translation Keys**:

```python
TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW: Final = "notification_title_chore_due_window"
TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW: Final = "notification_message_chore_due_window"
```

---

## Appendix B: Legacy Cleanup Checklist

Items to remove or rename during Phase 4 implementation:

- [x] **Rename**: `_due_soon_reminders_sent` → `_due_reminder_notif_sent` (coordinator.py)
- [x] **Rename**: `clear_chore_due_reminder()` → `clear_chore_notifications()` (chore_manager.py)
- [x] **Rename**: `_handle_chore_due_soon()` → `_handle_chore_due_reminder()` (notification_manager.py)
- [x] **Rename**: `SIGNAL_SUFFIX_CHORE_DUE_SOON` → `SIGNAL_SUFFIX_CHORE_DUE_REMINDER` (const.py)
- [ ] **Update**: All call sites to use new tracking set name
- [ ] **Update**: All signal emission sites to use new signal constant
- [ ] **Document**: Add code comments explaining legacy translation key names

**Grep Commands to Find All Occurrences**:

```bash
cd /workspaces/kidschores-ha
grep -r "_due_soon_reminders_sent" custom_components/kidschores/
grep -r "clear_chore_due_reminder" custom_components/kidschores/
grep -r "_handle_chore_due_soon" custom_components/kidschores/
grep -r "SIGNAL_SUFFIX_CHORE_DUE_SOON" custom_components/kidschores/
```

---

**End of Analysis Document**
