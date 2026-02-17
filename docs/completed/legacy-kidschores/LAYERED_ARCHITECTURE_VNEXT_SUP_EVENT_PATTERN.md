# Event Pattern Analysis - Supporting Document

**Parent Plan**: [LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md](./LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md)

## Purpose

This document analyzes event communication patterns for the manager-to-manager communication layer in the layered architecture refactor.

---

## Option 1: Home Assistant Dispatcher (Recommended)

Home Assistant provides `async_dispatcher_send` and `async_dispatcher_connect` for in-process pub/sub communication.

### Pros

- ✅ Built into Home Assistant - no external dependencies
- ✅ Already used by many HA integrations
- ✅ Async-native design
- ✅ Automatic cleanup with `async_dispatcher_connect` + `entry.async_on_unload`
- ✅ Type-safe signal names with constants

### Cons

- ⚠️ Signals are global to the HA instance (namespace carefully)
- ⚠️ No built-in filtering (receivers get all signals of that name)

### Implementation Pattern

#### Base Manager with emit/listen (Recommended)

```python
# managers/base_manager.py
from abc import ABC, abstractmethod
from typing import Any, Callable
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .. import const, kc_helpers as kh

class BaseManager(ABC):
    """Base class for all KidsChores managers with scoped event support."""

    def __init__(self, hass: HomeAssistant, coordinator) -> None:
        """Initialize manager."""
        self.hass = hass
        self.coordinator = coordinator
        self.entry_id = coordinator.config_entry.entry_id

    def emit(self, suffix: str, **payload: Any) -> None:
        """Emit instance-scoped event.

        Args:
            suffix: Signal suffix constant (e.g., const.SIGNAL_SUFFIX_POINTS_CHANGE)
            **payload: Event data passed to listeners

        Example:
            self.emit(const.SIGNAL_SUFFIX_POINTS_CHANGE, kid_id=kid_id, new_balance=50)
        """
        signal = kh.get_event_signal(self.entry_id, suffix)
        const.LOGGER.debug("Event '%s' emitted for instance %s", suffix, self.entry_id)
        async_dispatcher_send(self.hass, signal, **payload)

    def listen(self, suffix: str, callback: Callable) -> None:
        """Subscribe to instance-scoped event with automatic cleanup.

        Args:
            suffix: Signal suffix constant to listen for
            callback: Async function to call when event fires

        Example:
            self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGE, self._on_points_change)
        """
        signal = kh.get_event_signal(self.entry_id, suffix)
        unsub = async_dispatcher_connect(self.hass, signal, callback)
        self.coordinator.config_entry.async_on_unload(unsub)

    @abstractmethod
    async def async_setup(self) -> None:
        """Set up the manager (subscribe to events, etc.)."""
```

#### Usage in Concrete Managers

```python
# managers/economy_manager.py
from .base_manager import BaseManager

class EconomyManager(BaseManager):
    async def async_setup(self) -> None:
        """Set up economy manager."""
        # No events to listen to for economy manager
        pass

    async def deposit(self, kid_id: str, amount: float, source: str) -> float:
        """Add points and emit change event."""
        # ... business logic ...
        old_balance = kid_data["points"]
        kid_data["points"] += amount
        new_balance = kid_data["points"]

        # Emit scoped event
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_CHANGE,
            kid_id=kid_id,
            old_balance=old_balance,
            new_balance=new_balance,
            delta=amount,
            source=source,
        )
        return new_balance

# managers/gamification_manager.py
class GamificationManager(BaseManager):
    async def async_setup(self) -> None:
        """Set up gamification manager and subscribe to events."""
        # Listen to points changes
        self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGE, self._on_points_change)
        # Listen to chore approvals
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)

    async def _on_points_change(self, kid_id: str, new_balance: float, **kwargs) -> None:
        """React to point changes."""
        await self.evaluate_badges_for_kid(kid_id)

    async def _on_chore_approved(self, kid_id: str, chore_id: str, **kwargs) -> None:
        """React to chore approvals."""
        await self.update_achievements(kid_id)
```

### Cleanup Pattern

```python
# __init__.py (async_setup_entry)
async def async_setup_entry(hass, entry):
    coordinator = KidsChoresDataCoordinator(...)

    # Register cleanup for all managers
    entry.async_on_unload(coordinator.gamification_manager.unsubscribe)
    entry.async_on_unload(coordinator.economy_manager.unsubscribe)
```

---

## Option 2: Custom Event Bus (Not Recommended)

Build a custom pub/sub system within the integration.

### Pros

- ✅ Full control over implementation
- ✅ Can add filtering, priorities, etc.

### Cons

- ❌ Reinventing the wheel
- ❌ More code to maintain
- ❌ No automatic lifecycle management
- ❌ Not consistent with HA patterns

### Verdict: Skip this option

---

## Option 3: HA Event Bus (hass.bus.async_fire)

Use Home Assistant's core event bus.

### Pros

- ✅ Can be listened to by automations
- ✅ Visible in HA Developer Tools → Events

### Cons

- ❌ Heavier weight than dispatcher (serialization overhead)
- ❌ Events are global and visible to all integrations
- ❌ Designed for external consumption, not internal coordination

### When to Use

- Only use `hass.bus.async_fire` when you want **external consumers** (automations, other integrations) to react
- For internal manager-to-manager communication, use dispatcher

---

## Recommendation

**Use Home Assistant Dispatcher** (`async_dispatcher_send` / `async_dispatcher_connect`) for all internal manager communication.

### Multi-Instance Considerations

**Critical Issue**: If a user installs KidsChores twice (two separate config entries), global signal names would collide.

**Solution**: Scope all signals to `config_entry.entry_id` to ensure complete isolation between instances.

```python
# ❌ BAD: Global signal (collides with other instances)
SIGNAL_POINTS_CHANGE = f"{DOMAIN}_points_change"

# ✅ GOOD: Scoped signal per instance
def get_event_signal(entry_id: str, suffix: str) -> str:
    """Returns 'kidschores_ENTRYID123_points_change'."""
    return f"{DOMAIN}_{entry_id}_{suffix}"
```

### Event Naming Convention

**Pattern**: Store signal _suffixes_ in `const.py`, build scoped signals at runtime using `entry_id`.

#### const.py - Signal Suffixes

```python
# ==============================================================================
# Event Signal Suffixes (Manager-to-Manager Communication)
# ==============================================================================
# Used with kc_helpers.get_event_signal(entry_id, suffix) to create instance-scoped signals
# Pattern: get_event_signal(entry_id, "points_change") → "kidschores_{entry_id}_points_change"

# Economy events
SIGNAL_SUFFIX_POINTS_CHANGE = "points_change"
SIGNAL_SUFFIX_POINTS_INSUFFICIENT = "points_insufficient"  # NSF

# Chore events
SIGNAL_SUFFIX_CHORE_CLAIMED = "chore_claimed"
SIGNAL_SUFFIX_CHORE_APPROVED = "chore_approved"
SIGNAL_SUFFIX_CHORE_DISAPPROVED = "chore_disapproved"
SIGNAL_SUFFIX_CHORE_OVERDUE = "chore_overdue"
SIGNAL_SUFFIX_CHORE_RESET = "chore_reset"
SIGNAL_SUFFIX_CHORE_SKIPPED = "chore_skipped"

# Reward events
SIGNAL_SUFFIX_REWARD_CLAIMED = "reward_claimed"
SIGNAL_SUFFIX_REWARD_APPROVED = "reward_approved"
SIGNAL_SUFFIX_REWARD_DISAPPROVED = "reward_disapproved"

# Gamification events
SIGNAL_SUFFIX_BADGE_EARNED = "badge_earned"
SIGNAL_SUFFIX_BADGE_LOST = "badge_lost"  # Maintenance decay
SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
SIGNAL_SUFFIX_CHALLENGE_COMPLETED = "challenge_completed"

# System events
SIGNAL_SUFFIX_KID_CREATED = "kid_created"
SIGNAL_SUFFIX_KID_DELETED = "kid_deleted"
```

#### kc_helpers.py - Scoping Helper

```python
def get_event_signal(entry_id: str, suffix: str) -> str:
    """Build instance-scoped event signal name.

    Returns signal in format: 'kidschores_{entry_id}_{suffix}'

    This ensures complete isolation between multiple KidsChores instances:
    - Instance 1 (entry_id=abc123): 'kidschores_abc123_points_change'
    - Instance 2 (entry_id=xyz789): 'kidschores_xyz789_points_change'

    Args:
        entry_id: ConfigEntry.entry_id from coordinator
        suffix: Signal suffix constant (e.g., SIGNAL_SUFFIX_POINTS_CHANGE)

    Returns:
        Fully qualified signal name scoped to this instance

    Example:
        >>> get_event_signal("abc123", const.SIGNAL_SUFFIX_POINTS_CHANGE)
        'kidschores_abc123_points_change'
    """
    return f"{const.DOMAIN}_{entry_id}_{suffix}"
```

### Event Payload Patterns

**Recommendation**: Define TypedDicts for all event payloads in `type_defs.py` for type safety.

```python
# type_defs.py
from typing import TypedDict

class PointsChangeEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_POINTS_CHANGE."""
    kid_id: str
    old_balance: float
    new_balance: float
    delta: float
    source: str  # "chore_approval", "reward_redemption", "penalty", "bonus", "adjustment"
    reference_id: str | None  # chore_id, reward_id, etc.

class ChoreApprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_APPROVED."""
    kid_id: str
    chore_id: str
    parent_name: str
    points_awarded: float
    is_shared: bool

class BadgeEarnedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_BADGE_EARNED."""
    kid_id: str
    badge_id: str
    badge_name: str
    level: int | None  # For cumulative badges
    points_bonus: float | None
```

#### Example Payload Structures

```python
# SIGNAL_SUFFIX_POINTS_CHANGE payload:
{
    "kid_id": str,
    "old_balance": float,
    "new_balance": float,
    "delta": float,
    "source": str,  # "chore_approval", "reward_redemption", "penalty", "bonus", "adjustment"
    "reference_id": str | None,  # chore_id, reward_id, etc.
}

# SIGNAL_CHORE_APPROVED payload:
{
    "kid_id": str,
    "chore_id": str,
    "parent_name": str,
    "points_awarded": float,
    "is_shared": bool,
}

# SIGNAL_BADGE_EARNED payload:
{
    "kid_id": str,
    "badge_id": str,
    "badge_name": str,
    "level": int | None,  # For cumulative badges
    "points_bonus": float | None,
}
```

---

## Event Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EVENT FLOW                                       │
└─────────────────────────────────────────────────────────────────────────┘

User Action: Parent approves chore
       │
       ▼
┌──────────────────┐
│   ChoreManager   │ ──── SIGNAL_CHORE_APPROVED ────┐
│  approve(...)    │                                │
└────────┬─────────┘                                │
         │ calls                                    │
         ▼                                          ▼
┌──────────────────┐                    ┌──────────────────────┐
│  EconomyManager  │                    │ GamificationManager  │
│  deposit(...)    │                    │ _on_chore_approved() │
└────────┬─────────┘                    │ - update streak      │
         │                              │ - check achievements │
         │ emits                        └──────────────────────┘
         ▼
  SIGNAL_POINTS_CHANGE
         │
         ▼
┌──────────────────────┐
│ GamificationManager  │
│ _on_points_change()  │
│ - check badges       │
│ - emit if earned     │
└────────┬─────────────┘
         │ emits (if badge earned)
         ▼
  SIGNAL_BADGE_EARNED
         │
         ▼
┌──────────────────────┐
│ NotificationManager  │
│ _on_badge_earned()   │
│ - send notification  │
└──────────────────────┘
```

---

## Loop Prevention

**Critical**: Prevent infinite event loops where one event triggers another that triggers the first.

### Common Loop Patterns

```python
# ❌ BAD: Can cause infinite loop
class EconomyManager:
    async def deposit(self, kid_id: str, amount: float) -> None:
        kid_data["points"] += amount
        self.emit(SIGNAL_SUFFIX_POINTS_CHANGE, kid_id=kid_id)
        await self._check_milestones(kid_id)  # Might trigger another deposit!

# ✅ GOOD: Use flags or limit recursion depth
class EconomyManager:
    def __init__(self, ...):
        super().__init__(...)
        self._updating_points: set[str] = set()  # Track in-progress updates

    async def deposit(self, kid_id: str, amount: float) -> None:
        if kid_id in self._updating_points:
            const.LOGGER.warning("Recursive point update detected for %s", kid_id)
            return

        try:
            self._updating_points.add(kid_id)
            kid_data["points"] += amount
            self.emit(SIGNAL_SUFFIX_POINTS_CHANGE, kid_id=kid_id)
        finally:
            self._updating_points.discard(kid_id)
```

### Guidelines

1. **Never emit events from event handlers** (listeners should not emit the same event type)
2. **Use flags** to track in-progress operations
3. **Emit at the end** of operations, not in the middle
4. **Document** which events can trigger which managers

---

## Implementation Checklist

- [ ] Add `SIGNAL_SUFFIX_*` constants to `const.py`
- [ ] Add `get_event_signal()` helper to `kc_helpers.py`
- [ ] Create `BaseManager` class with `emit()` and `listen()` methods
- [ ] Define event payload TypedDicts in `type_defs.py`
- [ ] Implement `async_setup()` in each concrete manager to subscribe to events
- [ ] Add loop prevention flags where needed (e.g., `_updating_points`)
- [ ] Register manager cleanup via `entry.async_on_unload` in coordinator init
- [ ] Add integration tests for event propagation
- [ ] Add multi-instance test (two config entries, verify isolation)
- [ ] Document event payloads and flow in `ARCHITECTURE.md`
