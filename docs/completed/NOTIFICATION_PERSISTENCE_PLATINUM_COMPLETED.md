# Notification Persistence - Platinum Architecture Refactor

## Initiative snapshot

- **Name / Code**: Notification Persistence (NOTIF-PERSIST)
- **Target release / milestone**: v0.5.0 (beta3 stabilization)
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: ✅ **COMPLETED** (Jan 31, 2026)

## Summary & immediate steps

| Phase / Step             | Description                                         | % complete | Quick notes                                       |
| ------------------------ | --------------------------------------------------- | ---------- | ------------------------------------------------- |
| Phase 1 – Constants      | Add storage keys for notification timestamps        | 100%       | ✅ DATA_NOTIFICATIONS bucket + keys               |
| Phase 2 – Storage Access | NotificationManager helpers + Schedule-Lock method  | 100%       | ✅ Separate bucket (not chore_data) + cleanup     |
| Phase 3 – ChoreManager   | Remove set checks, emit facts only (with due_date!) | 100%       | ✅ Removed transient sets, Schedule-Lock handlers |
| Phase 3B – Overdue Notif | Add Schedule-Lock to overdue handler                | 100%       | ✅ Uses "overdue" notif_type in Schedule-Lock     |
| Phase 4 – Coordinator    | Remove transient sets from Coordinator              | 100%       | ✅ Removed sets & clear method, updated test      |
| Phase 5 – Validation     | Full test suite, verify restart persistence         | 100%       | ✅ 1151 tests pass                                |

**Key insight**: Schedule-Lock pattern eliminates need for explicit cleanup listeners!
When `approval_period_start` advances (chore reset), old `last_notified` timestamps become automatically obsolete.

**Architectural Pivot (Jan 31)**: Moved notification storage from `chore_data` to separate
`DATA_NOTIFICATIONS` bucket to maintain strict domain ownership (NotificationManager owns its own bucket).

1. **Key objective** – Move notification suppression from transient Coordinator sets to persistent storage in `DATA_NOTIFICATIONS[kid_id][chore_id]`, ensuring notifications survive HA restarts and follow Platinum domain separation.

2. **Summary of recent work**
   - Completed COORDINATOR_CASCADE_REFACTOR - Infrastructure Coordinator pattern in place
   - Pivoted from storing in `chore_data` (domain leak) to separate `DATA_NOTIFICATIONS` bucket
   - NotificationManager now owns its own bucket, reads `approval_period_start` from ChoreManager (query only)

3. **Next steps (short term)**
   - ~~Add constants for new storage keys~~ ✅ Done: DATA*NOTIFICATIONS, DATA_NOTIF_LAST_DUE*\*
   - ~~Move suppression check from ChoreManager to NotificationManager~~ ✅ Done
   - ~~Implement "Schedule-Lock" pattern~~ ✅ Done with proper domain separation
   - Add cleanup handlers for CHORE_DELETED and KID_DELETED ✅ Done

4. **Risks / blockers**
   - ~~Must maintain backward compatibility~~ ✅ Missing keys safely default to None
   - ~~NotificationManager must access kid's chore_data for timestamp storage~~ ✅ PIVOTED: Own bucket
   - ~~Cleanup signals must be emitted consistently~~ ✅ \_cleanup_chore_notifications, \_cleanup_kid_notifications

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Infrastructure Coordinator Pattern
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) § 5.3 – Event Architecture
   - [DUE_WINDOW_FEATURE_COMPLETED.md](../completed/DUE_WINDOW_FEATURE_COMPLETED.md) – Current implementation

6. **Decisions & completion check**
   - **Decisions captured**:
     - [x] Storage location: `DATA_NOTIFICATIONS[kid_id][chore_id]` (PIVOTED: separate bucket, not chore_data)
     - [x] Suppression owner: NotificationManager (not ChoreManager)
     - [x] Invalidation logic: Schedule-Lock pattern (compare vs `approval_period_start` from chore_data - READ-ONLY)
     - [x] Cleanup: NotificationManager listens to CHORE_DELETED/KID_DELETED and cleans own bucket
     - [x] Cleanup triggers: Automatic via Schedule-Lock (no explicit triggers needed)
     - [x] Overdue notifications: Added Schedule-Lock to existing handler
   - **Completion confirmation**: `[x]` All follow-up items completed

---

## Architecture Overview

### Current State (Transient Sets - Problem)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Coordinator                                  │
│  __init__():                                                        │
│    self._due_reminder_notif_sent: set[str] = set()  ← TRANSIENT     │
│    self._due_window_notif_sent: set[str] = set()    ← TRANSIENT     │
│                                                                     │
│  Problem: Sets reset on HA restart → duplicate notifications        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ChoreManager (Current Owner)                      │
│  check_chore_due_reminders():                                       │
│    if reminder_key in self._coordinator._due_reminder_notif_sent:   │
│        continue  # Skip                                             │
│    self.emit(SIGNAL_SUFFIX_CHORE_DUE_REMINDER, ...)                │
│    self._coordinator._due_reminder_notif_sent.add(reminder_key)    │
│                                                                     │
│  Problem: ChoreManager knows about notification history (wrong SoC) │
└─────────────────────────────────────────────────────────────────────┘
```

### Target State (Persistent Storage - Platinum with Domain Separation)

```
┌─────────────────────────────────────────────────────────────────────┐
│          Storage: _data[DATA_NOTIFICATIONS][kid_id][chore_id]        │
│  (OWNED BY NotificationManager - separate from chore_data!)          │
│  {                                                                  │
│    "last_due_window": "2026-01-29T14:00:00+00:00",                  │
│    "last_due_reminder": "2026-01-29T15:30:00+00:00",                │
│  }                                                                  │
│                                                                     │
│  Benefit: Survives HA restart, strict domain ownership              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                   READ-ONLY QUERY  │  approval_period_start
                     (from chore_data owned by ChoreManager)
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                    ChoreManager (Pure State Engine)                  │
│  check_chore_due_reminders():                                       │
│    # No suppression check - just emit the FACT                      │
│    self.emit(SIGNAL_SUFFIX_CHORE_DUE_REMINDER, ...)                │
│                                                                     │
│  Responsibility: Identify when chore is due (no notification logic) │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ CHORE_DUE_REMINDER signal (with due_date!)
┌─────────────────────────────────────────────────────────────────────┐
│            NotificationManager (Gatekeeper / Voice)                  │
│  _handle_chore_due_reminder():                                      │
│    1. Query approval_period_start from ChoreManager (READ-ONLY)     │
│    2. Get last_notified from OUR notifications bucket               │
│    3. Schedule-Lock Check:                                          │
│       if last_notified and last_notified >= approval_period_start:  │
│           return  # SILENCE: Already notified this period           │
│    4. Send notification                                             │
│    5. Update last_notified in OUR bucket (persist)                  │
│                                                                     │
│  Responsibility: Enforce notification policy (no domain mutation)   │
└─────────────────────────────────────────────────────────────────────┘

### Cleanup via Choreography (Janitor Pattern)

```

CHORE_DELETED signal → NotificationManager.\_cleanup_chore_notifications()
Removes all kid records for that chore from DATA_NOTIFICATIONS

KID_DELETED signal → NotificationManager.\_cleanup_kid_notifications()
Removes entire kid entry from DATA_NOTIFICATIONS

```

### Automatic Invalidation (No Period Cleanup Needed!)

When a chore resets or is approved, `approval_period_start` moves forward.
This automatically makes any old `last_notified` timestamp obsolete:

```

Period 1: approval_period_start = "2026-01-29T00:00:00"
last_due_reminder = "2026-01-29T14:00:00"
→ last_notified >= approval_period_start → SUPPRESSED ✓

Period 2: approval_period_start = "2026-01-30T00:00:00" (chore reset!)
last_due_reminder = "2026-01-29T14:00:00" (unchanged in our bucket)
→ last_notified < approval_period_start → SEND NEW REMINDER ✓

```

No explicit cleanup listeners needed! The boundary naturally moves.
```

### Schedule-Lock Pattern (Invalidation Logic)

```python
def _should_send_notification(self, kid_chore_data: dict, notif_type: str) -> bool:
    """Check if notification should be sent using Schedule-Lock pattern.

    The "lock" is the approval_period_start timestamp. A notification is
    only valid for the CURRENT period. If last_notified < approval_period_start,
    the previous notification was for an old cycle.
    """
    last_notified_key = (
        const.DATA_KID_CHORE_DATA_LAST_NOTIFIED_DUE_WINDOW
        if notif_type == "due_window"
        else const.DATA_KID_CHORE_DATA_LAST_NOTIFIED_DUE_REMINDER
    )

    last_notified_str = kid_chore_data.get(last_notified_key)
    if not last_notified_str:
        return True  # Never notified - send it

    approval_period_start_str = kid_chore_data.get(
        const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
    )
    if not approval_period_start_str:
        return True  # No period defined - send it

    last_notified = dt_to_utc(last_notified_str)
    approval_period_start = dt_to_utc(approval_period_start_str)

    if last_notified is None or approval_period_start is None:
        return True  # Parse error - send to be safe

    # Schedule-Lock: Only suppress if notified WITHIN current period
    return last_notified < approval_period_start
```

---

## Detailed phase tracking

### Phase 1 – Constants & Storage Keys ✅ COMPLETE

- **Goal**: Add constants for new persistent timestamp fields.

- **Steps / detailed work items**

1. - [x] Add to `const.py`:

   ```python
   # Notification persistence keys (v0.5.0+ - Platinum Pattern)
   DATA_KID_CHORE_DATA_LAST_NOTIFIED_DUE_WINDOW = "last_notified_due_window"
   DATA_KID_CHORE_DATA_LAST_NOTIFIED_DUE_REMINDER = "last_notified_due_reminder"
   ```

2. - [x] Add to `type_defs.py` (KidChoreDataEntry docstring):
   ```python
   - last_notified_due_window: str | None (ISO datetime, v0.5.0+ Platinum Pattern)
   - last_notified_due_reminder: str | None (ISO datetime, v0.5.0+ Platinum Pattern)
   ```

- **Key issues**
- None

### Phase 2 – NotificationManager Storage Access & Schedule-Lock ✅ COMPLETE

- **Goal**: Enable NotificationManager to read/write kid's chore_data with O(1) suppression lookup.

- **Steps / detailed work items**

1. - [x] Add helper method `_get_kid_chore_data()` - gets/creates kid's per-chore tracking data
2. - [x] Add `_should_send_notification()` - Schedule-Lock pattern (compare vs approval_period_start)
3. - [x] Add `_record_notification_sent()` - updates timestamp and persists

**Implementation location**: [notification_manager.py#L248-L329](custom_components/kidschores/managers/notification_manager.py#L248-L329)

- **Key issues**
- None

### Phase 3 – ChoreManager: Emit Facts Only ✅ COMPLETE

- **Goal**: ChoreManager identifies facts, no longer tracks notification state.

- **Steps / detailed work items**

1. - [x] Modify `ChoreManager.check_chore_due_reminders()`:
   - Removed: `reminder_key = f"{chore_id}:{kid_id}"`
   - Removed: transient set checks and adds
   - Added: `due_date=due_date_str` to emit (for Schedule-Lock)
   - Kept: State checks (claimed, approved) before emitting

2. - [x] Modify `ChoreManager.check_chore_due_window_transitions()`:
   - Removed: `window_key = f"{chore_id}:{kid_id}"`
   - Removed: transient set checks and adds
   - Kept: State checks before emitting
   - Kept: `due_date=due_dt.isoformat()` already present

3. - [x] Add listeners to NotificationManager's `async_setup()`:
   - Already existed at lines 175/177

4. - [x] Update `_handle_chore_due_reminder()` with Schedule-Lock check:
   - Added: `_should_send_notification()` check
   - Added: `_record_notification_sent()` after sending
   - Added: Suppression debug logging

5. - [x] Update `_handle_chore_due_window()` with Schedule-Lock check

**Implementation locations**:

- [chore_manager.py - check_chore_due_reminders](custom_components/kidschores/managers/chore_manager.py#L3783)
- [chore_manager.py - check_chore_due_window_transitions](custom_components/kidschores/managers/chore_manager.py#L3888)
- [notification_manager.py - handlers](custom_components/kidschores/managers/notification_manager.py#L1767-L1868)

- **Key issues**
- None

### Phase 3B – Add Schedule-Lock to Overdue Handler ✅ COMPLETE

- **Goal**: Ensure overdue notifications also use Schedule-Lock for deduplication.

- **Implementation**:
  - Added `_should_send_notification(kid_id, chore_id, "overdue")` check
  - Added `_record_notification_sent(kid_id, chore_id, "overdue")` after sending
  - Uses same helpers as due_start and due_reminder

- **Storage key**: `DATA_NOTIF_LAST_OVERDUE = "last_overdue"`

- **Steps / detailed work items**

1. - [x] Update `const.py`: Added `DATA_NOTIF_LAST_OVERDUE = "last_overdue"`
2. - [x] Update `_get_notif_key()` helper: Added "overdue" → `DATA_NOTIF_LAST_OVERDUE` mapping
3. - [x] Update `_handle_chore_overdue()`: Added Schedule-Lock check and record

- **Key issues**
- None

### Phase 4 – Coordinator Cleanup ✅ COMPLETE

- **Goal**: Remove transient notification tracking from Coordinator.

**Why no explicit cleanup phase?** The Schedule-Lock pattern handles invalidation automatically:

- When a chore resets → `approval_period_start` moves forward
- Old `last_notified` timestamps become obsolete (< new period start)
- No need to listen for CLAIMED/RESET signals to clear timestamps!

- **Steps / detailed work items**

1. - [x] Remove from `Coordinator.__init__()`:
   - Removed `_due_reminder_notif_sent` and `_due_window_notif_sent` sets
   - Removed associated comments

2. - [x] Remove `ChoreManager.clear_chore_notifications()` method:
   - Deleted method entirely
   - Removed all calls from `claim_chore`, `approve_chore`, `disapprove_chore`, `reset_chore_status`

3. - [x] Grep verified no references remain in `custom_components/`

4. - [x] Updated test `test_due_soon_reminder_cleared_on_claim` → `test_due_reminder_schedule_lock_invalidation`:
   - Now tests Schedule-Lock invalidation logic instead of transient set clearing

- **Key issues**
- None

### Phase 5 – Validation ✅ COMPLETE

- **Goal**: Verify persistence, restart behavior, and test suite passes.

- **Steps / detailed work items**

1. - [x] Run full test suite: `python -m pytest tests/ -v --tb=line`
   - Result: 1151 passed, 2 skipped

2. - [x] Run lint/type check: `./utils/quick_lint.sh --fix`
   - Result: All checks passed (ruff, mypy 0 errors, 10 boundary checks)

3. - [x] Test for Schedule-Lock invalidation added:
   - `test_due_reminder_schedule_lock_invalidation` in `test_workflow_notifications.py`
   - Verifies timestamp comparison logic

- **Key issues**
- None

---

## Testing & validation

- **Tests to run**:
  - `python -m pytest tests/ -v --tb=line -q` (full suite)
  - `python -m pytest tests/test_notification_helpers.py -v` (notification-specific)
  - `./utils/quick_lint.sh --fix` (lint/type/architectural boundaries)

- **New tests to add**:
  - `test_notification_timestamp_survives_restart` – Verify persistence
  - `test_schedule_lock_invalidation_on_period_advance` – Verify auto-invalidation
  - `test_overdue_notification_suppression` – Verify overdue uses NotificationManager

---

## Notes & follow-up

### Why Schedule-Lock Wins

| Feature                 | Transient Sets (Old)       | Schedule-Lock (New)             |
| ----------------------- | -------------------------- | ------------------------------- |
| **Restart persistence** | ❌ Lost on crash/reboot    | ✅ Survives all restarts        |
| **Cleanup logic**       | Manual set-clearing needed | Automatic (period advances)     |
| **Memory usage**        | Sets grow unbounded        | O(1) per chore-kid combo        |
| **Deduplication**       | `key in set` check         | `last_notified >= period_start` |
| **Owner**               | ChoreManager (wrong!)      | NotificationManager (correct)   |

### Separation of Concerns Summary

| Component           | Role        | Responsibility                               |
| ------------------- | ----------- | -------------------------------------------- |
| **ChoreManager**    | Fact-Finder | "Chore X is due/overdue for Kid Y" (emit)    |
| **NotificationMgr** | Gatekeeper  | "Should I notify?" (Schedule-Lock) + persist |
| **Storage**         | Truth Store | Timestamps in kid_info[chore_data][chore_id] |

### Key Insight: Overdue Notifications

The existing `_notify_overdue_chore()` method (lines 4162-4220) already uses persistent storage
(`DATA_KID_OVERDUE_NOTIFICATIONS`), BUT the suppression logic lives in ChoreManager.
Phase 3B moves this suppression to NotificationManager for consistency.

**Before (Platinum violation)**:

```
ChoreManager._handle_overdue_chore_state()
  → ChoreManager._notify_overdue_chore()  ← Suppression logic HERE
    → emit SIGNAL_SUFFIX_CHORE_OVERDUE
      → NotificationManager._handle_chore_overdue()  ← Just sends
```

**After (Platinum compliant)**:

```
ChoreManager._handle_overdue_chore_state()
  → emit SIGNAL_SUFFIX_CHORE_OVERDUE (raw fact)
    → NotificationManager._handle_chore_overdue()  ← Suppression logic HERE
      → Check DATA_KID_OVERDUE_NOTIFICATIONS
      → Send if allowed, update timestamp
```

### Benefits

| Benefit                         | Description                                         |
| ------------------------------- | --------------------------------------------------- |
| **Restart Persistence**         | Notifications survive HA crash/reboot               |
| **Platinum Separation**         | ChoreManager = Fact-Finder, NotificationMgr = Voice |
| **Automatic Invalidation**      | Period advance auto-obsoletes old timestamps        |
| **No Cleanup Logic**            | No listeners needed for CLAIMED/RESET signals       |
| **No Coordinator Domain State** | Transient sets removed from Coordinator             |
| **Unified Suppression**         | ALL notification types managed by NotificationMgr   |
| **O(1) Efficiency**             | Single dict lookup vs set membership check          |

### Migration Notes

- No schema migration needed (new keys default to None/missing)
- Backward compatible (missing keys = never notified = send notification)
- `DATA_KID_OVERDUE_NOTIFICATIONS` already exists - reuse it for overdue
