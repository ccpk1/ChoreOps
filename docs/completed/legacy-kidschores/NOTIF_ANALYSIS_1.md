# Parent Notification Concurrency - Detailed Plan & Debounce Analysis

**Status**: PROPOSED
**Effort**: 2-3 hours
**Priority**: MEDIUM (UX improvement)
**Last Updated**: December 23, 2025

---

## 📋 **Executive Summary**

Parent notifications are sent **sequentially** (one-by-one) whenever a chore is approved, reward is claimed, or achievement is earned. This makes approval flows feel slower than they could be. This document proposes converting to **concurrent** notification delivery while preserving necessary debouncing and deduplication.

**Current Implementation**:

- Sequential `await` for each parent notification in `_notify_parents()` (coordinator.py lines 8095-8162)
- 2-5 parent notifications per approval flow
- Each notification can take 100-500ms depending on service (mobile vs persistent)
- **Total time**: 200ms-2.5s per approval

**Proposed Change**:

- Use `asyncio.gather()` to send all notifications concurrently
- Isolate failures so one slow parent doesn't block others
- Maintain all existing features (translated text, actions, deduplication)

**Expected Outcome**:

- Multiple concurrent parents: ~30% faster (1 x max latency instead of sum)
- Single parent: No change
- User perception: Approvals feel instant, not delayed

---

## 🔍 **Current Implementation Analysis**

### Flow 1: Service Call (Parent Portal)

```
Service: kidschores.approve_chore
  └─ services.py: handle_approve_chore() (line 186)
     └─ services.py: coordinator.approve_chore() (line 228)
        └─ coordinator.py: approve_chore() (line 2310)
           └─ coordinator.py: _notify_kid_translated() (line 2438)
```

**Sequential behavior**: Not applicable here (single notification to kid)

### Flow 2: Notification Action (Mobile/Push Button Click)

```
Home Assistant Event: NOTIFICATION_ACTION_EVENT
  └─ __init__.py: handle_notification_event() (line 487)
     └─ notification_action_handler.py: async_handle_notification_action() (line 10)
        └─ notification_action_handler.py: coordinator.approve_chore() (line 87)
           └─ coordinator.py: approve_chore() (line 2310)
              └─ coordinator.py: _notify_kid_translated() (line 2438)
```

**Sequential behavior**: Not applicable here (single notification to kid)

### Flow 3: Overdue Chore Notification to Parents

```
coordinator.py: _check_overdue_chores() (line 7679)
  └─ coordinator.py: _notify_parents_translated() [multiple times]
     └─ coordinator.py: _notify_parents() (line 8095) ⭐ SEQUENTIAL HERE
```

**Code Location**: coordinator.py lines 8095-8162 (`_notify_parents()`)

**Current Implementation**:

```python
async def _notify_parents(self, kid_id, title, message, actions=None, extra_data=None):
    perf_start = time.perf_counter()
    parent_count = 0

    for parent_id, parent_info in self.parents_data.items():
        if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            continue
        if not parent_info.get(const.DATA_PARENT_ENABLE_NOTIFICATIONS, True):
            continue

        mobile_enabled = parent_info.get(const.CONF_ENABLE_MOBILE_NOTIFICATIONS, True)
        persistent_enabled = parent_info.get(const.CONF_ENABLE_PERSISTENT_NOTIFICATIONS, True)
        mobile_notify_service = parent_info.get(const.CONF_MOBILE_NOTIFY_SERVICE)

        if mobile_enabled and mobile_notify_service:
            parent_count += 1
            await async_send_notification(...)  # ⭐ SEQUENTIAL AWAIT
        elif persistent_enabled:
            parent_count += 1
            await self.hass.services.async_call(...)  # ⭐ SEQUENTIAL AWAIT

    # Performance logging
    perf_duration = time.perf_counter() - perf_start
    const.LOGGER.debug("PERF: _notify_parents() sent %d notifications in %.3fs (sequential)", ...)
```

**Problems**:

1. If Parent 1's notification service is slow (500ms), Parent 2 waits 500ms before being notified
2. For 5 parents at 200ms each: 1000ms total vs 200ms concurrent
3. No failure isolation (if Parent 1 fails, Parent 2-5 still proceed, but error handling is implicit)

---

## 🧪 **Debouncing & Deduplication Review**

### Question: Do we already have debouncing on approval actions?

**Analysis**:

#### 1. **Service Call Level** (services.py)

✅ **Duplicate Prevention**: The `approve_chore()` method in coordinator.py (lines 2356-2366) checks:

```python
allow_multiple = chore_info.get(const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY, False)
if not allow_multiple:
    if chore_id in kid_info.get(const.DATA_KID_APPROVED_CHORES, []):
        raise HomeAssistantError("Already approved today")
```

**Status**: ✅ YES - prevents double-approval at data level

#### 2. **Notification Action Handler** (notification_action_handler.py)

⚠️ **NO DEBOUNCING** - The handler directly calls `coordinator.approve_chore()` without any:

- Click debouncing (time-based deduplication)
- Request deduplication (checking if same approval already in-flight)
- UI feedback (no toast/spinner while processing)

**Code**:

```python
async def async_handle_notification_action(hass, event):
    # ... parsing ...
    if base_action == const.ACTION_APPROVE_CHORE:
        coordinator.approve_chore(...)  # ⭐ IMMEDIATE, NO DEBOUNCE
```

**Scenario**: User clicks "Approve" button twice rapidly on mobile notification

1. First click triggers approve_chore() (succeeds)
2. Second click (within same millisecond) also triggers approve_chore()
3. Both calls reach the duplicate check simultaneously
4. Race condition: Both read APPROVED_CHORES, both see it empty, both approve
5. Result: Duplicate approval + points added twice

#### 3. **Persistent Notification System**

⚠️ **Implicit Deduplication Only**: Home Assistant's persistent notification system deduplicates by `notification_id` in the UI, but:

- Two approvals still execute in coordinator
- Data is still modified twice
- Only the UI is deduplicated (shows one notification, not two)

#### 4. **Parent Notifications on Approval**

✅ **NO ISSUE** - Kid receives one notification per approval, no deduplication needed

---

## 🎯 **Proposed Solution: Concurrent Notifications with Debounce**

### Part 1: Convert Parent Notifications to Concurrent

**Changes to coordinator.py: `_notify_parents()` method**

**Before** (sequential):

```python
async def _notify_parents(self, kid_id, title, message, actions=None, extra_data=None):
    parent_count = 0
    for parent_id, parent_info in self.parents_data.items():
        # ... filter logic ...
        if mobile_enabled and mobile_notify_service:
            parent_count += 1
            await async_send_notification(...)  # Wait for each one
        elif persistent_enabled:
            parent_count += 1
            await self.hass.services.async_call(...)  # Wait for each one
```

**After** (concurrent):

```python
async def _notify_parents(self, kid_id, title, message, actions=None, extra_data=None):
    tasks = []

    for parent_id, parent_info in self.parents_data.items():
        # ... filter logic ...
        if mobile_enabled and mobile_notify_service:
            tasks.append(
                async_send_notification(...)  # Don't await - collect task
            )
        elif persistent_enabled:
            tasks.append(
                self.hass.services.async_call(...)  # Don't await - collect task
            )

    # Send all notifications concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Log any failures
    parent_count = len(tasks)
    for parent_id, result in zip(parent_ids, results):
        if isinstance(result, Exception):
            const.LOGGER.warning("Failed to notify parent %s: %s", parent_id, result)
```

**Benefits**:

- ✅ All notifications sent in parallel
- ✅ One slow parent doesn't block others
- ✅ All failures logged
- ✅ Single performance metric: max latency instead of sum

**Effort**: 1-1.5 hours

---

### Part 2: Add Debouncing to Notification Action Handler

**Problem**: Rapid double-clicks on mobile notification buttons can trigger duplicate approvals

**Current Behavior**:

1. User clicks "Approve" button on mobile notification
2. `async_handle_notification_action()` fires immediately
3. `coordinator.approve_chore()` is called
4. Data is updated
5. Kid gets notification
6. Parents get notifications (currently sequential, will be concurrent)

**Race Condition Scenario** (with rapid double-click):

1. User double-clicks "Approve" within 100ms
2. First click: `async_handle_notification_action()` called → approve_chore() queued
3. Second click: `async_handle_notification_action()` called → approve_chore() queued
4. Both calls execute near-simultaneously
5. Both see chore as "not approved" → both approve
6. Result: Duplicate approval (if no other protection)

**Existing Protection**:

- `approve_chore()` checks if already approved (line 2356-2366)
- But race condition: both calls read state before either writes
- Protection only works if sequential

**Solution Options**:

#### Option A: Service-Level Debounce (Recommended)

Add per-chore approval lock to prevent concurrent approvals:

```python
# In coordinator.__init__():
self._approval_locks: dict[str, asyncio.Lock] = {}  # Maps chore_id to Lock

async def approve_chore(self, parent_name, kid_id, chore_id, points_awarded=None):
    # Get or create lock for this chore
    if chore_id not in self._approval_locks:
        self._approval_locks[chore_id] = asyncio.Lock()

    async with self._approval_locks[chore_id]:
        # Only one approval can proceed at a time for this chore
        # ... rest of approve_chore logic ...
```

**Benefits**:

- ✅ True debouncing (only one approval in-flight per chore)
- ✅ Prevents race conditions entirely
- ✅ Clean, localized change
- ✅ Applies to all approval flows (service + notification action)

**Cost**: 30-45 min

#### Option B: Notification Action Handler Debounce

Add per-action debouncing directly in handler:

```python
# In notification_action_handler module:
_pending_approvals: dict[tuple, asyncio.Task] = {}

async def async_handle_notification_action(hass, event):
    action_key = (base_action, kid_id, chore_id)

    # If same approval already in-flight, ignore duplicate
    if action_key in _pending_approvals:
        const.LOGGER.debug("Ignoring duplicate approval (already in-flight)")
        return

    # Mark as in-flight
    task = asyncio.create_task(coordinator.approve_chore(...))
    _pending_approvals[action_key] = task

    try:
        await task
    finally:
        _pending_approvals.pop(action_key, None)
```

**Drawbacks**:

- Only protects notification action flow, not service calls
- Cleanup logic can fail (leaves orphaned tasks)
- Harder to test

#### Option C: UI-Level Debounce (Home Assistant Companion)

Disable button after click in the mobile app.

**Drawbacks**:

- Doesn't help parent portal users
- Relies on external component
- Not our responsibility

---

## ⚠️ **CRITICAL: Multi-Parent Approval Scenario**

**User Scenario**: What if both Parent 1 and Parent 2 try to approve the same claimed chore within milliseconds?

### Current Behavior by Chore Type

#### Chores with `allow_multiple=False` (1x per day max)

**Flow**:

1. Kid claims chore → state = CLAIMED
2. Parent 1 sends approve via notification button
3. Parent 2 sends approve via notification button (within 100ms)

**Current Protection** (coordinator.py lines 2356-2366):

```python
allow_multiple = chore_info.get(const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY, False)
if not allow_multiple:
    if chore_id in kid_info.get(const.DATA_KID_APPROVED_CHORES, []):
        raise HomeAssistantError("Already approved today")
```

**Race Condition**:

```
Parent 1: approve_chore() reads APPROVED_CHORES → empty → proceeds
Parent 2: approve_chore() reads APPROVED_CHORES → empty → proceeds  (BOTH see empty!)
Result: Chore approved twice, points added twice
```

**Status**: ❌ **VULNERABLE** - Both approvals can process if concurrent

#### Chores with `allow_multiple=True` (multiple completions per day)

**Flow**:

1. Kid claims chore → state = CLAIMED
2. Parent 1 approves → chore moves to APPROVED (completion #1)
3. Kid claims SAME chore again immediately → state = CLAIMED again
4. Parent 2 approves → chore moves to APPROVED (completion #2)

**What if Parents approve during same claim attempt**:

```python
# In claim_chore() (line 2230-2235)
if allow_multiple:
    # If already approved, remove it so the new claim can trigger a new approval flow
    kid_info[const.DATA_KID_APPROVED_CHORES] = [
        item for item in kid_info.get(const.DATA_KID_APPROVED_CHORES, [])
        if item != chore_id
    ]
```

**Scenario**:

1. Kid claims chore X (allow_multiple=True)
2. Parents get notifications with approve buttons for chore X
3. Parent 1 approves chore X → approved list = [X]
4. Parent 2 approves chore X SIMULTANEOUSLY
   - Both read approved list at same time
   - Both see [X] → think it's already approved? Or both proceed?
5. Kid claims chore X again (same day)
6. Claim clears previous approval and resets

**Current Code Does NOT Check allow_multiple Before Approving** (line 2356):

```python
# In approve_chore()
allow_multiple = chore_info.get(const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY, False)
if not allow_multiple:  # ← Only checks if NOT allow_multiple
    # throw error if already approved
```

**Status**: ✅ **SAFE** - Multiple approvals allowed, no protection needed

### The Real Problem: Single Notification, Multiple Approvals

**The actual concern**: When `claim_chore()` sends ONE notification to all parents with approve buttons, what if:

1. Parent 1 clicks "Approve" on phone
2. Parent 2 clicks "Approve" on phone (within 50ms)
3. BOTH calls reach `approve_chore()` simultaneously
4. For `allow_multiple=False`: Both get through (BUG) ✅ **NEEDS DEBOUNCE**
5. For `allow_multiple=True`: Both get through (INTENDED) ✅ **OK AS-IS**

### Proposed Debounce Strategy: Time-Window Deduplication

**Insight**: If two approvals for the same (kid, chore) come within 2 seconds, assume it's the same action (parent double-clicked or network retry)

**Implementation Options**:

#### Option A: Per-Claim Approval Lock ⭐ RECOMMENDED

```python
class KidsChoresDataCoordinator:
    def __init__(self, ...):
        # Track in-flight approvals: key=(kid_id, chore_id), value=timestamp
        self._approval_in_flight: dict[tuple, float] = {}

    def approve_chore(self, parent_name, kid_id, chore_id, points_awarded=None):
        key = (kid_id, chore_id)
        now = time.time()

        # Check if approval already in-flight for this chore
        if key in self._approval_in_flight:
            last_approval_time = self._approval_in_flight[key]
            if now - last_approval_time < 2.0:  # Within 2 seconds
                const.LOGGER.debug(
                    "Ignoring duplicate approval (already in-flight within 2s) for "
                    "kid %s chore %s", kid_id, chore_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_ALREADY_CLAIMED,
                    translation_placeholders={
                        "entity": self.chores_data[chore_id][const.DATA_CHORE_NAME]
                    },
                )

        # Mark as in-flight
        self._approval_in_flight[key] = now

        try:
            # Original approval logic...
            chore_info = self.chores_data[chore_id]
            allow_multiple = chore_info.get(
                const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY, False
            )
            if not allow_multiple:
                if chore_id in kid_info.get(const.DATA_KID_APPROVED_CHORES, []):
                    raise HomeAssistantError(...)

            # ... rest of approval ...
        finally:
            # Cleanup after brief delay
            self._approval_in_flight.pop(key, None)
```

**Behavior**:

- Parent 1 approves → marked in-flight for 2 seconds
- Parent 2 clicks within 2s → rejected with "already claimed" error
- Parent 1 can approve AGAIN after 2 seconds (intentional new attempt)
- Allow_multiple chores: Both parents CAN approve same claimed chore if staggered >2s apart

**Advantages**:

- ✅ Prevents accidental double-clicks (same parent)
- ✅ Prevents concurrent parent approvals of single claim
- ✅ Still allows intentional multiple approvals (after 2s window)
- ✅ Works for both allow_multiple and single-approval chores
- ✅ Simple, localized change

#### Option B: Async Lock Per Chore (What Plan Proposed)

```python
self._approval_locks[chore_id] = asyncio.Lock()
async with self._approval_locks[chore_id]:
    self.approve_chore(...)
```

**Problem**:

- Blocks second parent indefinitely (not 2s window)
- If Parent 1 is slow, Parent 2 must wait
- Doesn't distinguish intentional vs accidental

---

## 📊 **Recommended Implementation Plan**

### Step 1: Concurrent Parent Notifications (1-1.5 hours)

**File**: `coordinator.py`, method `_notify_parents()` (lines 8095-8162)

```python
async def _notify_parents(self, kid_id, title, message, actions=None, extra_data=None):
    # Collect all notification tasks
    notification_tasks = []
    parent_info_list = []

    for parent_id, parent_info in self.parents_data.items():
        if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            continue
        if not parent_info.get(const.DATA_PARENT_ENABLE_NOTIFICATIONS, True):
            continue

        mobile_enabled = parent_info.get(const.CONF_ENABLE_MOBILE_NOTIFICATIONS, True)
        persistent_enabled = parent_info.get(const.CONF_ENABLE_PERSISTENT_NOTIFICATIONS, True)
        mobile_notify_service = parent_info.get(const.CONF_MOBILE_NOTIFY_SERVICE)

        if mobile_enabled and mobile_notify_service:
            notification_tasks.append(
                async_send_notification(
                    self.hass, mobile_notify_service, title, message,
                    actions=actions, extra_data=extra_data
                )
            )
            parent_info_list.append(parent_id)
        elif persistent_enabled:
            notification_tasks.append(
                self.hass.services.async_call(
                    const.NOTIFY_PERSISTENT_NOTIFICATION, const.NOTIFY_CREATE,
                    {
                        const.NOTIFY_TITLE: title,
                        const.NOTIFY_MESSAGE: message,
                        const.NOTIFY_NOTIFICATION_ID: f"parent_{parent_id}",
                    },
                    blocking=True,
                )
            )
            parent_info_list.append(parent_id)

    # Send all notifications concurrently
    if notification_tasks:
        perf_start = time.perf_counter()
        results = await asyncio.gather(*notification_tasks, return_exceptions=True)
        perf_duration = time.perf_counter() - perf_start

        # Log any failures
        for parent_id, result in zip(parent_info_list, results):
            if isinstance(result, Exception):
                const.LOGGER.warning(
                    "Failed to notify parent %s: %s", parent_id, result
                )

        const.LOGGER.debug(
            "PERF: _notify_parents() sent %d notifications concurrently in %.3fs (max latency)",
            len(notification_tasks),
            perf_duration,
        )
```

**Testing**:

- Unit test with 5 parent notifications (measure concurrent vs sequential)
- Verify failure isolation (one parent failure doesn't block others)
- Verify performance improvement

### Step 2: Time-Window Approval Deduplication (45-60 minutes)

**File**: `coordinator.py`, `approve_chore()` method

**Problem Solved**: Prevents duplicate approvals when multiple parents or rapid clicks happen within short timeframe

**Implementation**:

Add to `__init__()`:

```python
# Track in-flight approvals: (kid_id, chore_id) → timestamp
self._approval_in_flight: dict[tuple[str, str], float] = {}
```

Wrap approval logic with time-window check:

```python
def approve_chore(self, parent_name: str, kid_id: str, chore_id: str, points_awarded: Optional[float] = None):
    """Approve a chore for kid_id if assigned."""
    import time  # For timestamp

    key = (kid_id, chore_id)
    now = time.time()

    # Check if approval already in-flight (within 2-second window)
    if key in self._approval_in_flight:
        last_approval_time = self._approval_in_flight[key]
        if now - last_approval_time < 2.0:
            chore_name = self.chores_data.get(chore_id, {}).get(const.DATA_CHORE_NAME, chore_id)
            const.LOGGER.debug(
                "Ignoring duplicate approval within 2s window for kid '%s' chore '%s'",
                kid_id, chore_id
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_ALREADY_CLAIMED,
                translation_placeholders={"entity": chore_name},
            )

    # Mark approval as in-flight (prevents concurrent approvals of same claim)
    self._approval_in_flight[key] = now

    try:
        # ... EXISTING approve_chore() LOGIC HERE ...
        # (All current validation and state updates)

        # Send notifications, update kid points, manage achievements/challenges, etc.
    finally:
        # Clear in-flight marker after approval completes
        self._approval_in_flight.pop(key, None)
```

**Behavior**:

- **Single claim, single click**: Works normally ✅
- **Single claim, double-click (same parent)**: Second click rejected within 2s ✅
- **Single claim, concurrent parents**: First parent succeeds, second rejected within 2s ✅
- **Multiple claims, staggered (allow_multiple)**: Each claim can be approved independently after 2s window expires ✅
- **after 2s, new approval attempt**: Allowed (distinguishes intentional retry from accident) ✅

**Advantages over Async Lock**:

- ✅ Time-window tolerance (allows intentional multi-approvals after 2s)
- ✅ Doesn't block one parent waiting for another
- ✅ Works for both allow_multiple and single-approval chores
- ✅ Synchronous operation (fits current code structure)
- ✅ Clear distinction: accident vs intentional action
- ✅ Prevents all race conditions (notification handler + service calls)

**Update call sites**: No changes needed! Works with existing sync `approve_chore()` calls

**Testing**:

- Unit test: Rapid double-click on same chore (should fail on second)
- Unit test: Two different parents click within 2s (should fail on second)
- Unit test: Same parent clicks after 2s window (should succeed)
- Unit test: Allow_multiple chore with two parents sequential (both succeed if >2s apart)
- Integration test: Mobile notification handler with concurrent clicks

- `notification_action_handler.py`: Use `await coordinator.async_approve_chore()`
- `services.py`: Use `await coordinator.async_approve_chore()` (already async context)
- All other flows: Check if sync or async context

**Testing**:

- Unit test: rapid double-click on same chore (should only approve once)
- Unit test: concurrent clicks on different chores (both should succeed)
- Integration test: Mobile notification action handler

---

## ⚡ **Performance Impact**

### Scenario: Overdue chore notification to 5 parents

**Before** (sequential):

```
Parent 1 notification: 200ms
Parent 2 notification: 150ms
Parent 3 notification: 300ms
Parent 4 notification: 100ms
Parent 5 notification: 250ms
───────────────────────
Total: 1000ms
```

**After** (concurrent):

```
Parent 1:   200ms ┐
Parent 2:   150ms │
Parent 3:   300ms ├─ Concurrent (max = 300ms)
Parent 4:   100ms │
Parent 5:   250ms ┘
───────────────────────
Total: 300ms (70% reduction)
```

### Scenario: Approval with time-window deduplication

**Before** (race condition possible):

```
Parent 1 click: approve_chore() reads ──┐
Parent 2 click: approve_chore() reads ──┼─ Both see CLAIMED → both approve (BUG)
                                        │
Result: 2 approvals, 2x points awarded
```

**After** (time-window debounced):

```
Parent 1 click: approve_chore() at 0ms ┐
                marks in-flight         ├─ Only Parent 1 succeeds
Parent 2 click: approve_chore() at 50ms┤  Parent 2 rejected (within 2s window)
                sees in-flight          │
                throws error            │
                                        │
After 2s, Parent 1 can attempt again (intentional retry)
```

---

## 🧪 **Testing Strategy**

### Unit Tests

1. `test_concurrent_parent_notifications.py`

   - Mock 5 parent info entries
   - Mock async_send_notification() with different latencies
   - Verify all notifications started immediately
   - Verify performance < 350ms (vs 1000ms sequential)
   - Verify failure isolation

2. `test_approval_time_window_deduplication.py`
   - Test rapid double-click (same parent): second rejected ✅
   - Test concurrent parents: first succeeds, second rejected ✅
   - Test allow_multiple chore: both can approve if >2s apart ✅
   - Test single-approval chore: only first approval succeeds ✅
   - Test after 2s window: new approval attempt allowed ✅

### Integration Tests

1. Overdue chore notification flow

   - Trigger overdue condition
   - Verify all parents notified concurrently
   - Measure actual wall-clock time

2. Mobile notification action handler
   - Simulate double-click on mobile button
   - Verify duplicate approval prevented
   - Verify logging messages

---

## 📝 **Summary**

| Item                         | Status            | Details                                                       |
| ---------------------------- | ----------------- | ------------------------------------------------------------- |
| **Concurrent Notifications** | ✅ Proposed       | 1-1.5h to implement                                           |
| **Approval Debouncing**      | ⚠️ Discovered Gap | Race condition possible on double-click                       |
| **Current Protection**       | ⭐ YES            | `approve_chore()` checks for duplicate but vulnerable to race |
| **Recommended Fix**          | Async lock        | 30-45 min to implement                                        |
| **Overall Effort**           | 2-2.5 hours       | Step 1 + Step 2                                               |
| **UX Impact**                | ✅ Positive       | Faster approvals, fewer race conditions                       |

---

## ⚠️ **Open Items Requiring Broader Architecture Review**

### Claim-Specific Notification Identification

**Problem**: Notifications are not currently tied to specific claims. When a kid claims the same chore multiple times:

- Parent receives multiple notifications but can't distinguish which claim each notification is for
- Approval action has no `claim_id`, making it unclear which claim gets approved
- If multiple claims are pending, approval may apply to wrong claim or both

**Current Behavior**:

- Notification message: "Sarah completed 'Clean Bedroom'" (same for all claims)
- Action data: No claim identifier embedded
- Result: Ambiguous which claim is being approved

**Proposed Solution**:

- Embed `claim_id` in notification action data
- Include timestamp in notification message: "Sarah completed 'Clean Bedroom' at 2:05 PM"
- Pass `claim_id` through approval flow to ensure only specific claim gets approved
- Ensure multi-claim scenarios work correctly

**Status**: Deferred pending wholistic claims architecture review
**Effort**: ~30 minutes once claims review is complete
**Priority**: HIGH - foundational issue affecting approval accuracy

---

## 🚀 **Next Steps**

1. **Approve Plan**: Review this proposal
2. **Implement Step 1**: Concurrent notifications (1-1.5h)
3. **Implement Step 2**: Approval debouncing (30-45m)
4. **Investigate**: Wholistic claims architecture (separate initiative)
5. **Test**: Unit + integration tests (30-45m)
6. **Commit**: With full documentation
7. **Validate**: 548 tests should still pass
8. **Performance Check**: Verify concurrent notification latency improvement
