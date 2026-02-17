# Notification System Improvements - Reality-Checked Plan

**Initiative Code**: NOTIF-FIX-v1  
**Target Release**: v0.6.0  
**Status**: Planning  
**Created**: January 15, 2026  
**Scope**: Right-sized for 25-50 notifications/day

---

## Reality Check: What Was Wrong with the Previous Plans

### Over-Engineered Elements (Removed)

| Previous Proposal | Reality | Verdict |
|-------------------|---------|---------|
| **Priority Queue System** | At 50 msg/day, no queue needed | ❌ REMOVED - just send them |
| **Rate Limiting (60/hr)** | 50/day total, impossible to hit | ❌ REMOVED - unnecessary |
| **Smart Batching (time windows)** | 2-3 parents max, not worth batching | ❌ REMOVED - over-engineering |
| **ML-based timing** | This is a chore app, not Gmail | ❌ REMOVED - absurd |
| **Quiet Hours Scheduling** | HA automations can do this already | ❌ REMOVED - use HA automations |
| **Exponential Backoff Retry** | Simple 1x retry is fine for 50/day | ❌ SIMPLIFIED - one retry max |
| **100 message history** | 20 is plenty for debugging | ❌ REDUCED - 20 entries |
| **4 notification sensors** | 1 diagnostic sensor is enough | ❌ REDUCED - keep it simple |
| **Per-type notification prefs** | On/off per person is sufficient | ❌ REMOVED - existing is fine |
| **New schema version** | No storage changes needed | ❌ REMOVED - keep v42 |
| **NotificationManager class** | Just fix existing methods | ❌ REMOVED - no new abstractions |
| **NotificationQueue class** | Not needed at this volume | ❌ REMOVED |
| **DeliveryTracker class** | Add to diagnostics instead | ❌ SIMPLIFIED |

### What Actually Matters

| Real Problem | Real Solution | Effort |
|--------------|---------------|--------|
| Sequential parent notifications | `asyncio.gather()` | 2 hours |
| Race condition on approval | `asyncio.Lock` | 2 hours |
| Translation loaded per-parent | Simple dict cache | 1 hour |
| Hardcoded strings in handler | Move to constants | 1 hour |
| Debugging notification issues | Add to diagnostics | 1 hour |

**Total realistic effort: 7-9 hours** (not 24-32 hours)

---

## What Home Assistant Actually Provides

### Notification Services ✅
- `notify.mobile_app_*` - Push to phones (works great)
- `persistent_notification.create` - Dashboard notifications (works great)
- Both are async service calls via `hass.services.async_call()`
- **Mobile app already has rate limiting built-in** (HA server-side)

### Async Patterns ✅
- `asyncio.gather(*tasks, return_exceptions=True)` - Concurrent execution
- `asyncio.Lock()` - Mutual exclusion for race conditions
- Both are standard Python, fully supported in HA

### What HA Doesn't Do (And We Shouldn't Either)
- ❌ No notification history tracking built-in
- ❌ No batching/coalescing built-in
- ❌ No "priority" concept for notifications
- **These are all things we'd be inventing** - keep scope minimal

---

## Right-Sized Solution

### Architecture: Keep It Simple

```
Current Flow (keep mostly unchanged):
┌─────────────────┐     ┌─────────────────────────┐
│   Coordinator   │────▶│ _notify_parents_trans() │
└─────────────────┘     └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │   For each parent:      │
                        │   - Get translation     │◀── ADD: Cache here
                        │   - await send_notif()  │◀── CHANGE: gather()
                        └─────────────────────────┘

Proposed Changes (minimal):
1. Cache translations in memory (simple dict)
2. Use asyncio.gather() for concurrent sends
3. Add lock to action handler (prevent double-clicks)
4. Clean up hardcoded strings (maintainability)
```

### What We're NOT Building
- ❌ No new `NotificationManager` class
- ❌ No new `NotificationQueue` class
- ❌ No new sensor entities
- ❌ No schema version bump
- ❌ No new config flow options
- ❌ No new user preferences

---

## Phase Breakdown (Realistic)

### Phase 1: Concurrent Parent Notifications (2-3 hours)

**Goal**: Make `_notify_parents_translated()` send to all parents concurrently

#### Step 1.1: Update `_notify_parents_translated()` in coordinator.py

**Current** (sequential - lines 10651-10805):
```python
async def _notify_parents_translated(...):
    for parent_id, parent_info in self.parents_data.items():
        # ... translation loading per parent ...
        await async_send_notification(...)  # Sequential
```

**After** (concurrent):
```python
async def _notify_parents_translated(...):
    # Build list of notification tasks
    tasks = []
    parent_ids = []
    
    for parent_id, parent_info in self.parents_data.items():
        if kid_id not in parent_info.get(const.DATA_PARENT_ASSOCIATED_KIDS, []):
            continue
        if not parent_info.get(const.DATA_PARENT_ENABLE_NOTIFICATIONS, True):
            continue
        
        # ... translation logic (moved to helper or cached) ...
        
        task = async_send_notification(
            self.hass, mobile_notify_service, title, message,
            actions=translated_actions, extra_data=extra_data
        )
        tasks.append(task)
        parent_ids.append(parent_id)
    
    # Send all concurrently
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for parent_id, result in zip(parent_ids, results):
            if isinstance(result, Exception):
                const.LOGGER.warning(
                    "Failed to notify parent %s: %s", parent_id, result
                )
```

**Expected speedup**: 
- 2 parents: 600ms → 300ms (2x faster)
- 3 parents: 900ms → 300ms (3x faster)
- Real-world: Probably 2x improvement since most families have 2 parents

#### Step 1.2: Similar change for `_notify_parents()` (non-translated version)

Same pattern applied to lines 10583-10649.

**Validation**:
```bash
pytest tests/test_notifications.py -v
# Manual: Approve chore, check logs for PERF timing
```

---

### Phase 2: Translation Caching (1-2 hours)

**Goal**: Don't reload translation files for every notification

#### Step 2.1: Add simple cache to coordinator

```python
# In coordinator __init__
self._translation_cache: dict[str, dict] = {}
self._translation_cache_loaded: set[str] = set()

async def _get_cached_translation(self, language: str) -> dict:
    """Get translation with simple caching."""
    if language not in self._translation_cache:
        self._translation_cache[language] = await kh.load_notification_translation(
            self.hass, language
        )
    return self._translation_cache[language]
```

#### Step 2.2: Update `_notify_parents_translated()` to use cache

Replace:
```python
translations = await kh.load_notification_translation(self.hass, parent_language)
```

With:
```python
translations = await self._get_cached_translation(parent_language)
```

**No TTL needed**: Cache persists until HA restart. Translations don't change at runtime.

**Validation**:
```bash
# Check cache hits in debug logs
grep "Loaded.*notification translations" home-assistant.log
# Should only see this once per language, not per notification
```

---

### Phase 3: Race Condition Fix (2 hours)

**Goal**: Prevent double-approval when parent double-clicks notification button

#### Step 3.1: Add approval lock to coordinator

```python
# In coordinator __init__
self._approval_locks: dict[str, asyncio.Lock] = {}

def _get_approval_lock(self, kid_id: str, entity_id: str) -> asyncio.Lock:
    """Get or create a lock for approval operations."""
    key = f"{kid_id}:{entity_id}"
    if key not in self._approval_locks:
        self._approval_locks[key] = asyncio.Lock()
    return self._approval_locks[key]
```

#### Step 3.2: Update action handler to use lock

**File**: `notification_action_handler.py`

```python
async def async_handle_notification_action(hass: HomeAssistant, event: Event) -> None:
    # ... existing validation ...
    
    # Get lock for this specific approval
    lock = coordinator._get_approval_lock(kid_id, chore_id or reward_id)
    
    async with lock:
        # Check if already processed (inside lock to prevent race)
        if base_action == const.ACTION_APPROVE_CHORE:
            if coordinator.is_approved_in_current_period(kid_id, chore_id):
                const.LOGGER.debug("Chore already approved, skipping duplicate")
                return
            coordinator.approve_chore(...)
        # ... rest of actions ...
```

**Why this works**:
- `asyncio.Lock` ensures only one approval processes at a time per (kid, entity)
- Second click waits for lock, then sees "already approved", returns early
- No complex debouncing needed - the lock IS the debounce

**Memory concern**: Locks are ~100 bytes each. Even 1000 locks = 100KB. Not an issue.

**Validation**:
```bash
pytest tests/test_notification_action_handler.py::test_double_click_protection -v
```

---

### Phase 4: Constants Cleanup (1-2 hours)

**Goal**: Remove hardcoded strings from action handler

#### Step 4.1: Add missing constants to const.py

```python
# Notification Action Handler (add near line 1474)
NOTIF_HANDLER_LOG_PREFIX: Final = "[NotifAction]"

# Already exist, just verify they're used:
# ACTION_APPROVE_CHORE, ACTION_APPROVE_REWARD, etc.
```

#### Step 4.2: Update notification_action_handler.py

- Replace all string literals with constants
- Add `LOG_PREFIX` to all log messages
- Ensure lazy logging (`%s` not f-strings)

**Before**:
```python
const.LOGGER.error("ERROR: No action found in event data: %s", event.data)
```

**After**:
```python
const.LOGGER.error(
    "%s No action found in event data: %s", 
    const.NOTIF_HANDLER_LOG_PREFIX, 
    event.data
)
```

**Validation**:
```bash
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/notification_action_handler.py
```

---

### Phase 5: Diagnostics Addition (1 hour)

**Goal**: Add notification stats to existing diagnostics (not new entities)

#### Step 5.1: Add to diagnostics.py

```python
async def async_get_config_entry_diagnostics(...):
    # ... existing code ...
    
    return {
        # ... existing sections ...
        "notification_stats": {
            "translation_cache_languages": list(coordinator._translation_cache.keys()),
            "active_approval_locks": len(coordinator._approval_locks),
            "last_notification_sent": coordinator._last_notification_timestamp,
        }
    }
```

That's it. No sensors, no history tracking, no metrics. Just basic stats for debugging.

**Validation**:
```bash
pytest tests/test_diagnostics.py -v
```

---

## What We're Explicitly NOT Doing

| Feature | Why Not |
|---------|---------|
| **Notification history** | HA's logbook already tracks service calls |
| **Delivery success tracking** | Mobile app shows delivery status |
| **Priority queues** | 50 msgs/day doesn't need queuing |
| **Batching** | 2-3 parents doesn't need batching |
| **Rate limiting** | HA mobile app already does this |
| **Retry logic** | One attempt is fine; failures are rare |
| **New sensors** | Diagnostics is sufficient |
| **Per-type preferences** | On/off is enough; use HA automations for more control |
| **Quiet hours** | Use HA automations (`time` condition) |

---

## Summary Table

| Phase | Description | Hours | Deliverable |
|-------|-------------|-------|-------------|
| **Phase 1** | Concurrent notifications | 2-3h | 2-3x faster parent notifications |
| **Phase 2** | Translation caching | 1-2h | Eliminate redundant file I/O |
| **Phase 3** | Race condition fix | 2h | Zero double-approvals |
| **Phase 4** | Constants cleanup | 1-2h | Maintainable code |
| **Phase 5** | Diagnostics | 1h | Debugging visibility |
| **Total** | | **7-10h** | Solid, reliable notifications |

---

## Success Criteria (Realistic)

### Must Have ✅
- [ ] Parent notifications sent concurrently (`asyncio.gather`)
- [ ] Translation cached per language (simple dict)
- [ ] No race conditions on approval (asyncio.Lock)
- [ ] All strings use constants (no hardcoding)
- [ ] 100% type hints in notification code
- [ ] Existing tests still pass

### Nice to Have (If Time)
- [ ] Performance logging (PERF: prefix)
- [ ] Basic stats in diagnostics
- [ ] Clean up dead code

### Explicitly Out of Scope
- ❌ New entities or sensors
- ❌ New config options
- ❌ Schema version changes
- ❌ New manager/queue classes
- ❌ Notification history
- ❌ User preferences beyond on/off

---

## Testing Strategy (Simple)

### Unit Tests
```bash
# Existing tests should still pass
pytest tests/test_notifications.py -v

# Add one test for race condition
pytest tests/test_notification_action_handler.py::test_double_click_protection -v
```

### Manual Testing
1. **Concurrent**: Approve chore, watch logs for timing
2. **Cache**: Approve multiple chores, check translation only loads once
3. **Race condition**: Rapidly click approve button twice, verify only one approval
4. **Constants**: Run linter, no hardcoded strings

### No Load Testing Needed
At 50 messages/day, load testing is overkill.

---

## Files Changed

| File | Change |
|------|--------|
| `coordinator.py` | Concurrent sends, translation cache, approval locks |
| `notification_action_handler.py` | Use locks, constants cleanup |
| `const.py` | Add `NOTIF_HANDLER_LOG_PREFIX` constant |
| `diagnostics.py` | Add notification stats section |
| `tests/test_notification_action_handler.py` | Add double-click test |

**No new files created.**

---

## Decision Summary

### Why This Plan Instead of the Previous

| Aspect | Previous Plan | This Plan |
|--------|---------------|-----------|
| **Scope** | 6 phases, 24-32 hours | 5 phases, 7-10 hours |
| **New files** | 5 new files | 0 new files |
| **New classes** | 3 manager/queue classes | 0 new classes |
| **Schema change** | v42 → v43 | None |
| **New entities** | 4 sensors | 0 new entities |
| **Complexity** | Enterprise messaging | Right-sized for family app |

### Core Philosophy
**Do less, do it well.** 

The notification system needs to be:
1. **Reliable** - No double approvals, no lost notifications
2. **Fast enough** - 300ms instead of 900ms is fine
3. **Debuggable** - Logs and diagnostics, not dashboards
4. **Maintainable** - Constants, types, clean code

It does NOT need to be:
- A message queue
- A rate limiter
- A notification preference engine
- A delivery tracking system
- An enterprise messaging platform

---

## Next Steps

1. **Approve this simplified plan**
2. **Implement Phase 1** (concurrent notifications) - biggest win
3. **Implement Phase 3** (race condition) - most important fix
4. **Remaining phases** - cleanup and polish

**Estimated total time: 7-10 hours**  
**Risk: Very Low** (minimal changes, no new abstractions)

---

## References

- [coordinator.py#L10583-10805](../../custom_components/kidschores/coordinator.py) - Current notification code
- [notification_action_handler.py](../../custom_components/kidschores/notification_action_handler.py) - Action handler
- [notification_helper.py](../../custom_components/kidschores/notification_helper.py) - Send notification helper
- HA Mobile App: Already has rate limiting, delivery tracking built-in
