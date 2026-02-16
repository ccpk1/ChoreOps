# Critical Race Condition Fix - Immediate Action Required

**Issue**: Multiple parents can approve same chore/reward simultaneously, causing duplicate points

**User Impact**:

- Kid gets double/triple points for one chore
- Points get drained multiple times for one reward approval
- Family loses trust in the point system

**Root Cause**: No locking mechanism in approval methods

---

## The Race Condition (Confirmed in Code)

### Scenario 1: Multiple Parent Approval

```
Timeline:
0ms: Parent 1 taps "Approve" → approve_chore() starts
5ms: Parent 2 taps "Approve" → approve_chore() starts
10ms: Both read _can_approve_chore() → both return "Yes, approvable"
20ms: Both award points (e.g., +5 points each)
Result: Kid gets +10 points instead of +5
```

### Scenario 2: Button Mashing

```
Timeline:
0ms: Parent taps "Approve" rapidly 3x
5ms: All 3 approve_reward() calls start
10ms: All see pending_count = 1 (same value)
15ms: All deduct points (e.g., -10 each)
Result: Kid loses -30 points instead of -10
```

---

## Immediate Fix (2 hours to implement)

### Step 1: Add Locks to Coordinator

**File**: `custom_components/kidschores/coordinator.py`

**Add to `__init__` method** (around line 1400):

```python
# Add after existing initialization
self._approval_locks: dict[str, asyncio.Lock] = {}
```

**Add helper method** (around line 3800):

```python
def _get_approval_lock(self, operation: str, kid_id: str, entity_id: str) -> asyncio.Lock:
    """Get or create a lock for approval operations to prevent race conditions.

    Args:
        operation: Type of operation ('approve_chore', 'approve_reward', etc.)
        kid_id: Internal ID of the kid
        entity_id: Internal ID of the chore/reward

    Returns:
        asyncio.Lock for this specific operation
    """
    lock_key = f"{operation}:{kid_id}:{entity_id}"
    if lock_key not in self._approval_locks:
        self._approval_locks[lock_key] = asyncio.Lock()
    return self._approval_locks[lock_key]
```

### Step 2: Update `approve_chore` Method

**File**: `custom_components/kidschores/coordinator.py`

**Replace line 2951-2988** (the vulnerability section):

```python
def approve_chore(
    self,
    parent_name: str,  # Reserved for future feature
    kid_id: str,
    chore_id: str,
    points_awarded: float | None = None,  # Reserved for future feature
):
    """Approve a chore for kid_id if assigned."""
    # This needs to be async to use locks, but changing the signature
    # would break existing callers. Instead, we'll use asyncio.run_coroutine_threadsafe
    # or make the actual approval logic async internally

    return asyncio.create_task(self._approve_chore_with_lock(
        parent_name, kid_id, chore_id, points_awarded
    ))

async def _approve_chore_with_lock(
    self,
    parent_name: str,
    kid_id: str,
    chore_id: str,
    points_awarded: float | None = None,
):
    """Approve a chore with race condition protection."""

    # Get lock for this specific chore approval
    lock = self._get_approval_lock("approve_chore", kid_id, chore_id)

    async with lock:
        # All the existing approval logic goes here, wrapped in the lock
        # This ensures only one approval can proceed at a time per (kid, chore)

        perf_start = time.perf_counter()
        if chore_id not in self.chores_data:
            raise HomeAssistantError(...)  # existing validation

        # ... rest of existing method unchanged ...
        # The key difference: now only one approval processes at a time

        # Re-check can_approve inside the lock (defensive programming)
        can_approve, error_key = self._can_approve_chore(kid_id, chore_id)
        if not can_approve:
            # Second parent will hit this after first approval completes
            chore_name = chore_info[const.DATA_CHORE_NAME]
            const.LOGGER.debug(
                "Race condition prevented: Chore '%s' already processed for kid '%s'",
                chore_name, kid_info[const.DATA_KID_NAME]
            )
            return  # Silently skip - not an error, just timing

        # ... rest of approval logic unchanged ...
```

### Step 3: Update `approve_reward` Method

**Similar pattern** - wrap the vulnerable section (lines 5154-5220) with:

```python
async def _approve_reward_with_lock(...):
    lock = self._get_approval_lock("approve_reward", kid_id, reward_id)

    async with lock:
        # Re-check pending_count inside lock
        reward_entry = self._get_kid_reward_data(kid_id, reward_id, create=False)
        pending_count = reward_entry.get(const.DATA_KID_REWARD_DATA_PENDING_COUNT, 0)

        if pending_count <= 0:
            const.LOGGER.debug("Race condition prevented: No pending rewards to approve")
            return  # Second/third click - nothing to do

        # ... rest of approval logic unchanged ...
```

### Step 4: Update Notification Action Handler

**File**: `custom_components/kidschores/notification_action_handler.py`

**No changes needed** - the coordinator methods already handle locking internally.

---

## Why This Fix Works

| Problem                                     | Solution                                                                 |
| ------------------------------------------- | ------------------------------------------------------------------------ |
| **Multiple parents approve simultaneously** | Lock ensures only one approval processes at a time                       |
| **Button mashing**                          | Second+ clicks wait for lock, then see "already approved", skip silently |
| **Point draining**                          | Only first approval deducts points, others are no-ops                    |
| **No user disruption**                      | Invisible to users - they just see correct behavior                      |

---

## Testing the Fix

### Manual Test 1: Multiple Parents

1. Kid claims a chore
2. Both parents rapidly click "Approve" on their phones
3. **Expected**: Kid gets +5 points (not +10)
4. **Expected**: Only one approval notification sent

### Manual Test 2: Button Mashing

1. Kid claims a 10-point reward
2. Parent rapidly taps "Approve" 5 times
3. **Expected**: Kid loses -10 points (not -50)
4. **Expected**: Only one approval processed

### Log Verification

```bash
grep "Race condition prevented" home-assistant.log
# Should see entries when fix is working
```

---

## Why This is the #1 Priority

| Aspect               | Impact                                        |
| -------------------- | --------------------------------------------- |
| **User Trust**       | Parents lose confidence when points are wrong |
| **Kid Motivation**   | Unfair points kill engagement                 |
| **Family Harmony**   | Arguments over "who approved what"            |
| **System Integrity** | Core feature must be reliable                 |

**This should be implemented immediately** - it's a critical bug affecting the core functionality.

---

## Implementation Notes

- **Lock granularity**: Per (operation, kid, entity) - allows concurrent approvals for different kids/chores
- **Memory usage**: ~100 bytes per lock, auto-created on demand
- **Performance**: Minimal - only blocks concurrent identical approvals
- **Backward compatibility**: Internal change, no API changes
- **Error handling**: Silent skip for duplicate approvals (better UX than error messages)

---

## After Implementation

Once this is deployed, the other notification improvements (concurrent sends, translation caching) become lower priority quality-of-life improvements rather than critical bug fixes.
