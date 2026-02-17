# Phase 0 Implementation Guide - Supporting Document

**Parent Plan**: [LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md](./LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md)

**Purpose**: Detailed implementation steps for Phase 0 - Event Infrastructure Foundation

---

## Signal Suffix Inventory Summary

**Total Signals Defined**: 56 constants across 6 categories

| Category          | Count | Notes                                                      |
| ----------------- | ----- | ---------------------------------------------------------- |
| Economy           | 2     | Points changes, NSF scenarios                              |
| Chore Operations  | 6     | Claim, approve, disapprove, overdue, reset, skip           |
| Reward Operations | 4     | Claim, approve, disapprove, reset                          |
| Penalty/Bonus     | 4     | Apply and reset operations                                 |
| Gamification      | 9     | Badges (3), achievements (2), challenges (3), progress (1) |
| CRUD Lifecycle    | 31    | Entity creation/update/deletion for all entity types       |

**Implementation Strategy**:

- ✅ **Define all 56 now**: Reserves namespace, prevents future conflicts, enables planning
- 🔄 **Implement incrementally**: Add actual emit/listen logic per phase as needed
- 🧹 **Audit post-refactor**: Remove unused signals after all phases complete

**Phase-by-Phase Usage**:

- **Phase 2 (Notification)**: 0 signals (consumer only)
- **Phase 3 (Economy)**: 4 signals (points + penalty/bonus)
- **Phase 4 (Chore)**: 6 signals
- **Phase 5 (Gamification)**: 9 signals
- **Later**: CRUD signals as needed for entity lifecycle coordination

---

## Event Architecture Standards

These standards ensure consistency and prevent ambiguity as the event system grows.

### 1. Signal Naming Convention (Past Tense Rule)

**Rule**: Signals must describe an event that has already occurred.

- **Format**: `NOUN_VERB_PAST_TENSE`
- **✅ Good**: `chore_approved`, `badge_earned`, `kid_deleted`, `points_changed`
- **❌ Bad**: `approve_chore` (command), `chore_approval` (ambiguous noun), `points_change` (present tense)

**Rationale**: Events are historical facts, not commands. Past tense signals semantic intent and prevents confusion between "trigger this action" vs. "this action occurred."

### 2. Scope & Isolation

**Rule**: All signals must be scoped to the Config Entry ID using `kc_helpers.get_event_signal()`. Never emit raw signal strings.

```python
# ❌ BAD: Global signal (collides with other instances)
async_dispatcher_send(self.hass, "kidschores_points_changed", kid_id=kid_id)

# ✅ GOOD: Instance-scoped signal
signal = kh.get_event_signal(self.entry_id, const.SIGNAL_SUFFIX_POINTS_CHANGED)
async_dispatcher_send(self.hass, signal, kid_id=kid_id, ...)
```

### 3. Payload Requirements

All event payloads must follow these standards:

#### Lifecycle Events (`_created`, `_deleted`)

- **Must include**: `internal_id`, `name` (or `<entity>_name`)
- **Purpose**: Enable logging and entity tracking

```python
self.emit(const.SIGNAL_SUFFIX_KID_CREATED, kid_id=kid_id, kid_name=name)
```

#### Update Events (`_updated`)

- **Must include**: `internal_id`, `changes` (list of changed field names)
- **Purpose**: Allow listeners to filter irrelevant updates

```python
self.emit(
    const.SIGNAL_SUFFIX_CHORE_UPDATED,
    chore_id=chore_id,
    changes=["points", "due_date"]  # Only these fields changed
)
```

**Why?** Without `changes`, listeners react to every typo fix in descriptions. With `changes`, they can filter:

```python
async def _on_chore_updated(self, chore_id: str, changes: list[str], **kwargs):
    if "points" in changes or "assigned_kids" in changes:
        await self.recalculate_badges(chore_id)  # Only react to relevant changes
```

#### Operational Events (`_claimed`, `_approved`, `_applied`)

- **Must include**: `kid_id`, acting `user_name` (or `parent_name`)
- **Purpose**: Enable audit logging and notification targeting

```python
self.emit(
    const.SIGNAL_SUFFIX_CHORE_APPROVED,
    kid_id=kid_id,
    chore_id=chore_id,
    parent_name=parent_name,
    points_awarded=10.0
)
```

### 4. Semantic Clarity for Ambiguous Verbs

**Reset**: Clarify whether it's state/status reset or data deletion

- ✅ `chore_status_reset` (recurring status back to pending)
- ❌ `chore_reset` (ambiguous - config reset? data wipe?)

**Lost vs. Revoked**: Distinguish accidental from intentional

- ✅ `badge_revoked` (intentional removal by parent/system)
- ❌ `badge_lost` (sounds passive/accidental)

**Skipped vs. Rescheduled**: Clarify action vs. inaction

- ✅ `chore_rescheduled` (due date moved forward)
- ❌ `chore_skipped` (implies missed/ignored)

---

## Implementation Checklist

### Step 1: Add SIGNAL*SUFFIX*\* Constants to `const.py`

**⚠️ CRITICAL PLACEMENT REQUIREMENT**: Add these constants in a NEW section AFTER the Storage section and BEFORE the Float Precision section.

**Exact Location**: `custom_components/kidschores/const.py` at **line 60**

**Context Lines for Placement** (find these lines to locate insertion point):

```python
# Storage
STORE: Final = "store"
STORAGE_KEY: Final = "kidschores_data"
STORAGE_VERSION: Final = 1

# ← INSERT NEW "Event Infrastructure" SECTION HERE ←

# Default timezone (set once hass is available)
# pylint: disable=invalid-name
DEFAULT_TIME_ZONE: ZoneInfo | None = None
```

**Why This Location**:

- ✅ Keeps all integration infrastructure constants grouped (Storage, Event Infrastructure, Schema Management)
- ✅ Logically follows Storage section (both are core infrastructure)
- ✅ Avoids disrupting existing constant groupings (Core Constants, Config Keys sections untouched)
- ✅ Easy to locate for future reference (near top of file, after general integration info)

**Code Block to Add**:

```python
# ==============================================================================
# Event Infrastructure (Phase 0: Layered Architecture Foundation)
# ==============================================================================
# Event Signal Suffixes (Manager-to-Manager Communication)
# ==============================================================================
# Used with kc_helpers.get_event_signal(entry_id, suffix) to create instance-scoped signals
# Pattern: get_event_signal(entry_id, "points_change") → "kidschores_{entry_id}_points_change"
#
# Multi-instance isolation: Each config entry gets its own signal namespace
# - Instance 1 (entry_id=abc123): "kidschores_abc123_points_change"
# - Instance 2 (entry_id=xyz789): "kidschores_xyz789_points_change"
#
# NOTE: This is a comprehensive list based on current coordinator operations.
# Not all signals need to be implemented immediately - add as needed per phase.

# ==============================================================================
# Economy Events (EconomyManager)
# ==============================================================================
SIGNAL_SUFFIX_POINTS_CHANGED: Final = "points_changed"  # deposit/withdraw/adjust (past tense)
SIGNAL_SUFFIX_TRANSACTION_FAILED: Final = "transaction_failed"  # NSF or other failures

# ==============================================================================
# Chore Events (ChoreManager)
# ==============================================================================
SIGNAL_SUFFIX_CHORE_CLAIMED: Final = "chore_claimed"  # claim_chore()
SIGNAL_SUFFIX_CHORE_APPROVED: Final = "chore_approved"  # approve_chore()
SIGNAL_SUFFIX_CHORE_DISAPPROVED: Final = "chore_disapproved"  # disapprove_chore()
SIGNAL_SUFFIX_CHORE_OVERDUE: Final = "chore_overdue"  # _check_overdue_chores()
SIGNAL_SUFFIX_CHORE_STATUS_RESET: Final = "chore_status_reset"  # Recurring status reset (not data deletion)
SIGNAL_SUFFIX_CHORE_RESCHEDULED: Final = "chore_rescheduled"  # skip_chore_due_date() - more accurate than 'skipped'

# ==============================================================================
# Reward Events (RewardManager)
# ==============================================================================
SIGNAL_SUFFIX_REWARD_CLAIMED: Final = "reward_claimed"  # redeem_reward()
SIGNAL_SUFFIX_REWARD_APPROVED: Final = "reward_approved"  # approve_reward()
SIGNAL_SUFFIX_REWARD_DISAPPROVED: Final = "reward_disapproved"  # disapprove_reward()
SIGNAL_SUFFIX_REWARD_STATUS_RESET: Final = "reward_status_reset"  # Recurring status reset

# ==============================================================================
# Penalty Events (PenaltyManager or EconomyManager)
# ==============================================================================
SIGNAL_SUFFIX_PENALTY_APPLIED: Final = "penalty_applied"  # apply_penalty()
SIGNAL_SUFFIX_PENALTY_STATUS_RESET: Final = "penalty_status_reset"  # Status reset (not deletion)

# ==============================================================================
# Bonus Events (BonusManager or EconomyManager)
# ==============================================================================
SIGNAL_SUFFIX_BONUS_APPLIED: Final = "bonus_applied"  # apply_bonus()
SIGNAL_SUFFIX_BONUS_STATUS_RESET: Final = "bonus_status_reset"  # Status reset (not deletion)

# ==============================================================================
# Gamification Events (GamificationManager)
# ==============================================================================
# Badge events
SIGNAL_SUFFIX_BADGE_EARNED: Final = "badge_earned"  # _award_badge()
SIGNAL_SUFFIX_BADGE_REVOKED: Final = "badge_revoked"  # remove_awarded_badges(), maintenance decay (intentional)
SIGNAL_SUFFIX_BADGE_PROGRESS_UPDATED: Final = "badge_progress_updated"  # _check_badges_for_kid()

# Achievement events
SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED: Final = "achievement_unlocked"  # _check_achievements_for_kid()
SIGNAL_SUFFIX_ACHIEVEMENT_PROGRESS_UPDATED: Final = "achievement_progress_updated"  # progress tracking

# Challenge events
SIGNAL_SUFFIX_CHALLENGE_COMPLETED: Final = "challenge_completed"  # _check_challenges_for_kid()
SIGNAL_SUFFIX_CHALLENGE_PROGRESS_UPDATED: Final = "challenge_progress_updated"  # progress tracking
SIGNAL_SUFFIX_CHALLENGE_EXPIRED: Final = "challenge_expired"  # End date passed

# ==============================================================================
# System/Entity Lifecycle Events (Coordinator)
# ==============================================================================
SIGNAL_SUFFIX_KID_CREATED: Final = "kid_created"  # Config flow: kid addition
SIGNAL_SUFFIX_KID_UPDATED: Final = "kid_updated"  # Config flow: kid modification
SIGNAL_SUFFIX_KID_DELETED: Final = "kid_deleted"  # delete_kid_entity()

SIGNAL_SUFFIX_PARENT_CREATED: Final = "parent_created"  # Config flow: parent addition
SIGNAL_SUFFIX_PARENT_UPDATED: Final = "parent_updated"  # Config flow: parent modification
SIGNAL_SUFFIX_PARENT_DELETED: Final = "parent_deleted"  # delete_parent_entity()

SIGNAL_SUFFIX_CHORE_CREATED: Final = "chore_created"  # Config flow: chore addition
SIGNAL_SUFFIX_CHORE_UPDATED: Final = "chore_updated"  # Config flow: chore modification
SIGNAL_SUFFIX_CHORE_DELETED: Final = "chore_deleted"  # delete_chore_entity()

SIGNAL_SUFFIX_BADGE_CREATED: Final = "badge_created"  # Config flow: badge addition
SIGNAL_SUFFIX_BADGE_UPDATED: Final = "badge_updated"  # Config flow: badge modification
SIGNAL_SUFFIX_BADGE_DELETED: Final = "badge_deleted"  # delete_badge_entity()

SIGNAL_SUFFIX_REWARD_CREATED: Final = "reward_created"  # Config flow: reward addition
SIGNAL_SUFFIX_REWARD_UPDATED: Final = "reward_updated"  # Config flow: reward modification
SIGNAL_SUFFIX_REWARD_DELETED: Final = "reward_deleted"  # delete_reward_entity()

SIGNAL_SUFFIX_ACHIEVEMENT_CREATED: Final = "achievement_created"  # Config flow
SIGNAL_SUFFIX_ACHIEVEMENT_UPDATED: Final = "achievement_updated"  # Config flow
SIGNAL_SUFFIX_ACHIEVEMENT_DELETED: Final = "achievement_deleted"  # delete_achievement_entity()

SIGNAL_SUFFIX_CHALLENGE_CREATED: Final = "challenge_created"  # Config flow
SIGNAL_SUFFIX_CHALLENGE_UPDATED: Final = "challenge_updated"  # Config flow
SIGNAL_SUFFIX_CHALLENGE_DELETED: Final = "challenge_deleted"  # delete_challenge_entity()

SIGNAL_SUFFIX_PENALTY_CREATED: Final = "penalty_created"  # Config flow
SIGNAL_SUFFIX_PENALTY_UPDATED: Final = "penalty_updated"  # Config flow
SIGNAL_SUFFIX_PENALTY_DELETED: Final = "penalty_deleted"  # delete_penalty_entity()

SIGNAL_SUFFIX_BONUS_CREATED: Final = "bonus_created"  # Config flow
SIGNAL_SUFFIX_BONUS_UPDATED: Final = "bonus_updated"  # Config flow
SIGNAL_SUFFIX_BONUS_DELETED: Final = "bonus_deleted"  # delete_bonus_entity()
```

**Validation**:

- [ ] Run: `grep "SIGNAL_SUFFIX_" custom_components/kidschores/const.py | wc -l` (should return 56 total)
- [ ] No import errors when importing const
- [ ] Verify grouping: 2 economy, 6 chore, 4 reward, 4 penalty/bonus, 9 gamification, 31 CRUD lifecycle

**Implementation Strategy**:
This is a comprehensive list of **all** potential signals based on current coordinator operations. However:

1. **Phase-by-phase implementation**: Only add the signals actually needed in each phase:
   - **Phase 2 (Notification)**: No signals emitted (notifications are consumers only)
   - **Phase 3 (Economy)**: `POINTS_CHANGE`, `POINTS_INSUFFICIENT`, `PENALTY_APPLIED`, `BONUS_APPLIED`
   - **Phase 4 (Chore)**: All chore signals (6 total)
   - **Phase 5 (Gamification)**: All gamification signals (9 total)
   - **Later phases**: CRUD lifecycle signals as needed

2. **Why define all now?**:
   - **Namespace reservation**: Prevents naming conflicts later
   - **Planning visibility**: Easier to see cross-manager dependencies
   - **Minimal cost**: Constants are cheap; implementation is deferred

3. **Dead code elimination**: After refactor completes, audit and remove unused signals

---

### Step 2: Add `get_event_signal()` Helper to `kc_helpers.py`

**⚠️ CRITICAL PLACEMENT REQUIREMENT**: Add this as a NEW section AFTER the Entity Registry Utilities section.

**Exact Location**: `custom_components/kidschores/kc_helpers.py` at **line 210** (after Entity Registry section, before "Get Coordinator" section)

**Context Lines for Placement** (find these lines to locate insertion point):

```python
    return None


# ==============================================================================
# Get Coordinator
# ==============================================================================
# ← INSERT NEW "Event Signal Helpers" SECTION HERE ←


def _get_kidschores_coordinator(
    hass: HomeAssistant, entry_id: str
) -> KidsChoresDataCoordinator:
```

**Why This Location**:

- ✅ After Entity Registry Utilities (both are infrastructure helpers)
- ✅ Before Get Coordinator (event signals are more foundational)
- ✅ Maintains file's logical section organization (documented in file header)
- ✅ Close to top of file for easy reference (foundational infrastructure)

**Code Block to Add**:

```python
# ==============================================================================
# Event Signal Helpers (Manager Communication)
# ==============================================================================


def get_event_signal(entry_id: str, suffix: str) -> str:
    """Build instance-scoped event signal name for dispatcher.

    This ensures complete isolation between multiple KidsChores config entries.
    Each instance gets its own signal namespace using its config_entry.entry_id.

    Format: 'kidschores_{entry_id}_{suffix}'

    Multi-instance example:
        - Instance 1 (entry_id="abc123"):
          get_event_signal("abc123", "points_change") → "kidschores_abc123_points_change"
        - Instance 2 (entry_id="xyz789"):
          get_event_signal("xyz789", "points_change") → "kidschores_xyz789_points_change"

    Managers can emit/listen without cross-talk between instances.

    Args:
        entry_id: ConfigEntry.entry_id from coordinator
        suffix: Signal suffix constant from const.py (e.g., SIGNAL_SUFFIX_POINTS_CHANGE)

    Returns:
        Fully qualified signal name scoped to this integration instance

    Example:
        >>> from . import const
        >>> get_event_signal("abc123", const.SIGNAL_SUFFIX_POINTS_CHANGE)
        'kidschores_abc123_points_change'
    """
    return f"{const.DOMAIN}_{entry_id}_{suffix}"
```

**Validation**:

- [ ] Test in Python shell:
  ```python
  from custom_components.kidschores import kc_helpers as kh, const
  signal = kh.get_event_signal("test123", const.SIGNAL_SUFFIX_POINTS_CHANGE)
  assert signal == "kidschores_test123_points_change"
  ```

---

### Step 3: Create managers/base_manager.py

**File**: `custom_components/kidschores/managers/base_manager.py` (new file)

**Full File Content**:

```python
"""Base manager class for KidsChores managers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .. import const
from .. import kc_helpers as kh

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator


class BaseManager(ABC):
    """Base class for all KidsChores managers with scoped event support.

    Provides:
    - Instance-scoped event emitting (emit)
    - Instance-scoped event listening (listen)
    - Automatic cleanup via coordinator's config_entry.async_on_unload

    Subclasses must implement:
    - async_setup(): Subscribe to events, initialize state
    """

    def __init__(self, hass: HomeAssistant, coordinator: KidsChoresDataCoordinator) -> None:
        """Initialize manager.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator managing this integration instance
        """
        self.hass = hass
        self.coordinator = coordinator
        self.entry_id = coordinator.config_entry.entry_id

    def emit(self, suffix: str, **payload: Any) -> None:
        """Emit instance-scoped event to other managers.

        Args:
            suffix: Signal suffix constant (e.g., const.SIGNAL_SUFFIX_POINTS_CHANGE)
            **payload: Event data dict passed to listeners (must be JSON-serializable)

        Example:
            self.emit(
                const.SIGNAL_SUFFIX_POINTS_CHANGE,
                kid_id=kid_id,
                old_balance=50.0,
                new_balance=60.0,
                delta=10.0,
                source="chore_approval"
            )
        """
        signal = kh.get_event_signal(self.entry_id, suffix)
        const.LOGGER.debug(
            "Emitting event '%s' for instance %s with payload keys: %s",
            suffix,
            self.entry_id,
            list(payload.keys()),
        )
        async_dispatcher_send(self.hass, signal, **payload)

    def listen(self, suffix: str, callback: Callable[..., None]) -> None:
        """Subscribe to instance-scoped event with automatic cleanup.

        The subscription is automatically cleaned up when the config entry is unloaded.

        Args:
            suffix: Signal suffix constant to listen for
            callback: Async function called when event fires (receives **payload)

        Example:
            async def _on_points_change(self, kid_id: str, new_balance: float, **kwargs):
                await self.recalculate_badges(kid_id)

            # In async_setup():
            self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGE, self._on_points_change)
        """
        signal = kh.get_event_signal(self.entry_id, suffix)
        unsub = async_dispatcher_connect(self.hass, signal, callback)
        self.coordinator.config_entry.async_on_unload(unsub)
        const.LOGGER.debug(
            "Manager %s listening to event '%s' for instance %s",
            self.__class__.__name__,
            suffix,
            self.entry_id,
        )

    @abstractmethod
    async def async_setup(self) -> None:
        """Set up the manager (subscribe to events, initialize state).

        Called once during coordinator initialization.
        Subclasses should subscribe to events here using self.listen().
        """
```

**Validation**:

- [ ] MyPy passes: `mypy custom_components/kidschores/managers/base_manager.py`
- [ ] Pylint passes: `pylint custom_components/kidschores/managers/base_manager.py`

---

### Step 4: Create managers/**init**.py

**File**: `custom_components/kidschores/managers/__init__.py` (new file)

**Full File Content**:

```python
"""Manager modules for KidsChores integration.

Managers orchestrate workflows and coordinate between engines.
They are stateful, event-aware, and handle cross-cutting concerns.
"""

from .base_manager import BaseManager

__all__ = [
    "BaseManager",
]
```

**Validation**:

- [ ] Test import: `from custom_components.kidschores.managers import BaseManager`
- [ ] No circular import errors

---

### Step 5: Add Event Payload TypedDicts

**File**: `custom_components/kidschores/type_defs.py` (append to end, ~line 800+)

**Code Block to Add**:

```python
# ==============================================================================
# Event Payload Types (Manager-to-Manager Communication)
# ==============================================================================
# Used for type-safe event payloads in BaseManager.emit() calls


class PointsChangeEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_POINTS_CHANGED (past tense).

    Emitted by: EconomyManager.deposit(), EconomyManager.withdraw()
    Consumed by: GamificationManager (badge evaluation), NotificationManager
    """

    kid_id: str  # Required
    old_balance: float  # Required
    new_balance: float  # Required
    delta: float  # Required (positive for deposit, negative for withdraw)
    source: str  # Required: "chore_approval", "reward_redemption", "penalty", "bonus", "adjustment"
    reference_id: str | None  # Optional: chore_id, reward_id, etc.


class TransactionFailedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_TRANSACTION_FAILED.

    Emitted by: EconomyManager when transaction cannot complete
    Consumed by: NotificationManager (alert user)
    """

    kid_id: str  # Required
    attempted_amount: float  # Required
    current_balance: float  # Required
    failure_reason: str  # Required: "insufficient_funds", "daily_limit_exceeded", "account_locked", etc.
    reference_id: str | None  # Optional: reward_id, penalty_id causing the attempt


class ChoreApprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_APPROVED.

    Emitted by: ChoreManager.approve()
    Consumed by: GamificationManager (achievement/streak tracking)
    """

    kid_id: str  # Required
    chore_id: str  # Required
    parent_name: str  # Required
    points_awarded: float  # Required
    is_shared: bool  # Required
    is_multi_claim: bool  # Required


class ChoreDisapprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_DISAPPROVED.

    Emitted by: ChoreManager.disapprove()
    Consumed by: GamificationManager (streak reset?), NotificationManager
    """

    kid_id: str  # Required
    chore_id: str  # Required
    parent_name: str  # Required
    reason: str | None  # Optional: disapproval reason


class RewardApprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_REWARD_APPROVED.

    Emitted by: RewardManager.approve()
    Consumed by: NotificationManager, GamificationManager (milestone tracking?)
    """

    kid_id: str  # Required
    reward_id: str  # Required
    reward_name: str  # Required
    points_spent: float  # Required
    parent_name: str  # Required


class RewardDisapprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_REWARD_DISAPPROVED.

    Emitted by: RewardManager.disapprove()
    Consumed by: NotificationManager
    """

    kid_id: str  # Required
    reward_id: str  # Required
    reward_name: str  # Required
    parent_name: str  # Required
    reason: str | None  # Optional: disapproval reason


class BadgeEarnedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_BADGE_EARNED.

    Emitted by: GamificationManager.evaluate_badges()
    Consumed by: NotificationManager, EconomyManager (if badge has point bonus)
    """

    kid_id: str  # Required
    badge_id: str  # Required
    badge_name: str  # Required
    badge_type: str  # Required: "cumulative" or "periodic"
    level: int | None  # Optional: For cumulative badges (1, 2, 3, ...)
    points_bonus: float | None  # Optional: Bonus points awarded


class BadgeLostEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_BADGE_REVOKED (intentional removal).

    Emitted by: GamificationManager (maintenance decay, manual removal)
    Consumed by: NotificationManager
    """

    kid_id: str  # Required
    badge_id: str  # Required
    badge_name: str  # Required
    reason: str  # Required: "maintenance_decay", "manual_removal", "criteria_no_longer_met", etc.


class AchievementUnlockedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED.

    Emitted by: GamificationManager.evaluate_achievements()
    Consumed by: NotificationManager
    """

    kid_id: str  # Required
    achievement_id: str  # Required
    achievement_name: str  # Required
    milestone_reached: str  # Required: Description of what was achieved


class ChallengeCompletedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHALLENGE_COMPLETED.

    Emitted by: GamificationManager.evaluate_challenges()
    Consumed by: NotificationManager, EconomyManager (challenge rewards)
    """

    kid_id: str  # Required
    challenge_id: str  # Required
    challenge_name: str  # Required
    points_awarded: float  # Required
    completion_date: str  # Required: ISO format


class PenaltyAppliedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_PENALTY_APPLIED.

    Emitted by: EconomyManager.apply_penalty() (or PenaltyManager)
    Consumed by: NotificationManager, GamificationManager (badge impacts?)
    """

    kid_id: str  # Required
    penalty_id: str  # Required
    penalty_name: str  # Required
    points_deducted: float  # Required
    parent_name: str  # Required
    reason: str | None  # Optional


class BonusAppliedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_BONUS_APPLIED.

    Emitted by: EconomyManager.apply_bonus() (or BonusManager)
    Consumed by: NotificationManager, GamificationManager (badge impacts?)
    """

    kid_id: str  # Required
    bonus_id: str  # Required
    bonus_name: str  # Required
    points_added: float  # Required
    parent_name: str  # Required
    reason: str | None  # Optional


class ChoreClaimedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_CLAIMED.

    Emitted by: ChoreManager.claim()
    Consumed by: NotificationManager (parent notification)
    """

    kid_id: str  # Required
    chore_id: str  # Required
    chore_name: str  # Required
    user_name: str  # Required (who initiated claim)


class ChoreOverdueEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_OVERDUE.

    Emitted by: ChoreManager._check_overdue_chores()
    Consumed by: NotificationManager, GamificationManager (badge/streak impacts)
    """

    kid_id: str  # Required
    chore_id: str  # Required
    chore_name: str  # Required
    days_overdue: int  # Required
    due_date: str  # Required: ISO format


class ChoreRescheduledEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_RESCHEDULED (not skipped).

    Emitted by: ChoreManager.skip_chore_due_date()
    Consumed by: NotificationManager (optional notification)
    """

    kid_id: str | None  # Optional: If kid-specific, else null for all assigned kids
    chore_id: str  # Required
    chore_name: str  # Required
    old_due_date: str  # Required: ISO format
    new_due_date: str  # Required: ISO format
    rescheduled_by: str  # Required: parent_name or "system"


# ==============================================================================
# NOTE: CRUD Lifecycle Events (31 total) omitted for now
# ==============================================================================
# Entity creation/update/deletion events can be added as TypedDicts later if needed.
# These are lower priority since most CRUD operations don't require manager coordination.
# Pattern for future addition:
#
# class KidCreatedEvent(TypedDict, total=False):
#     kid_id: str
#     kid_name: str
#     created_by: str
#
# class ChoreDeletedEvent(TypedDict, total=False):
#     chore_id: str
#     chore_name: str
#     deleted_by: str
```

**Validation**:

- [ ] MyPy passes: `mypy custom_components/kidschores/type_defs.py`
- [ ] Import test: `from custom_components.kidschores.type_defs import PointsChangeEvent, ChoreApprovedEvent`
- [ ] Verify count: 14 event payload TypedDicts defined (11 operational + note about 31 CRUD deferred)

---

### Step 6: Create Test File

**File**: `tests/test_event_infrastructure.py` (new file)

**Full File Content**:

```python
"""Tests for event infrastructure (BaseManager, signal scoping)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.kidschores import const
from custom_components.kidschores.kc_helpers import get_event_signal
from custom_components.kidschores.managers.base_manager import BaseManager


class MockManager(BaseManager):
    """Concrete manager for testing BaseManager."""

    async def async_setup(self) -> None:
        """Mock setup (no subscriptions)."""


def test_get_event_signal():
    """Test event signal scoping with entry_id."""
    entry_id_1 = "abc123"
    entry_id_2 = "xyz789"
    suffix = const.SIGNAL_SUFFIX_POINTS_CHANGE

    signal_1 = get_event_signal(entry_id_1, suffix)
    signal_2 = get_event_signal(entry_id_2, suffix)

    # Verify format
    assert signal_1 == f"{const.DOMAIN}_{entry_id_1}_{suffix}"
    assert signal_2 == f"{const.DOMAIN}_{entry_id_2}_{suffix}"

    # Verify isolation (different instances get different signals)
    assert signal_1 != signal_2
    assert "abc123" in signal_1
    assert "xyz789" in signal_2


@pytest.mark.asyncio
async def test_base_manager_emit(hass: HomeAssistant):
    """Test BaseManager.emit() dispatches events correctly."""
    mock_coordinator = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry_123"
    mock_coordinator.config_entry.async_on_unload = MagicMock()

    manager = MockManager(hass, mock_coordinator)

    with patch("custom_components.kidschores.managers.base_manager.async_dispatcher_send") as mock_send:
        manager.emit(
            const.SIGNAL_SUFFIX_POINTS_CHANGE,
            kid_id="kid1",
            old_balance=50.0,
            new_balance=60.0,
            delta=10.0,
            source="chore_approval"
        )

        # Verify dispatcher was called with correct signal
        expected_signal = get_event_signal("test_entry_123", const.SIGNAL_SUFFIX_POINTS_CHANGE)
        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == expected_signal  # Second arg is signal name


@pytest.mark.asyncio
async def test_base_manager_listen(hass: HomeAssistant):
    """Test BaseManager.listen() subscribes to events correctly."""
    mock_coordinator = MagicMock()
    mock_coordinator.config_entry.entry_id = "test_entry_456"
    mock_coordinator.config_entry.async_on_unload = MagicMock()

    manager = MockManager(hass, mock_coordinator)

    callback = AsyncMock()

    with patch("custom_components.kidschores.managers.base_manager.async_dispatcher_connect") as mock_connect:
        mock_unsub = MagicMock()
        mock_connect.return_value = mock_unsub

        manager.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, callback)

        # Verify dispatcher connect was called
        expected_signal = get_event_signal("test_entry_456", const.SIGNAL_SUFFIX_CHORE_APPROVED)
        mock_connect.assert_called_once()
        assert mock_connect.call_args[0][1] == expected_signal

        # Verify cleanup registration
        mock_coordinator.config_entry.async_on_unload.assert_called_once_with(mock_unsub)


@pytest.mark.asyncio
async def test_multi_instance_isolation(hass: HomeAssistant):
    """Test that two instances don't cross-talk via events."""
    # Create two mock coordinators (two config entries)
    mock_coord_1 = MagicMock()
    mock_coord_1.config_entry.entry_id = "instance_1"
    mock_coord_1.config_entry.async_on_unload = MagicMock()

    mock_coord_2 = MagicMock()
    mock_coord_2.config_entry.entry_id = "instance_2"
    mock_coord_2.config_entry.async_on_unload = MagicMock()

    manager_1 = MockManager(hass, mock_coord_1)
    manager_2 = MockManager(hass, mock_coord_2)

    # Set up listeners
    callback_1 = AsyncMock()
    callback_2 = AsyncMock()

    manager_1.listen(const.SIGNAL_SUFFIX_POINTS_CHANGE, callback_1)
    manager_2.listen(const.SIGNAL_SUFFIX_POINTS_CHANGE, callback_2)

    # Emit from instance 1
    manager_1.emit(const.SIGNAL_SUFFIX_POINTS_CHANGE, kid_id="kid1", delta=10.0)

    # Wait for dispatch
    await hass.async_block_till_done()

    # Verify callback_1 was called but callback_2 was NOT
    callback_1.assert_called_once()
    callback_2.assert_not_called()  # Isolated!

    # Reset and test reverse
    callback_1.reset_mock()
    callback_2.reset_mock()

    manager_2.emit(const.SIGNAL_SUFFIX_POINTS_CHANGE, kid_id="kid2", delta=5.0)
    await hass.async_block_till_done()

    callback_1.assert_not_called()  # Isolated!
    callback_2.assert_called_once()
```

**Validation**:

- [ ] Run: `pytest tests/test_event_infrastructure.py -v`
- [ ] All 5 tests pass

---

### Step 7: Run Full Validation Suite

**Commands**:

```bash
# Lint and format
./utils/quick_lint.sh --fix

# Type checking
mypy custom_components/kidschores/

# Event infrastructure tests
pytest tests/test_event_infrastructure.py -v

# Full regression suite
pytest tests/ -v --tb=line
```

**Success Criteria**:

- [ ] Quick lint: Score 9.5+/10
- [ ] MyPy: Zero errors
- [ ] Event tests: 5/5 passing
- [ ] Full suite: All tests passing (no regressions)

---

## Post-Implementation Verification

### File Checklist

- [ ] `const.py` has 56 new `SIGNAL_SUFFIX_*` constants (refined naming with past tense)
- [ ] `kc_helpers.py` has `get_event_signal()` function
- [ ] `managers/base_manager.py` exists with BaseManager class
- [ ] `managers/__init__.py` exports BaseManager
- [ ] `type_defs.py` has 15 event payload TypedDicts (includes TransactionFailedEvent, ChoreRescheduledEvent)
- [ ] `tests/test_event_infrastructure.py` exists with 5 tests

### Behavioral Verification

- [ ] Two mock managers can emit/listen without errors
- [ ] Multi-instance isolation works (test proves it)
- [ ] No circular imports (all imports resolve)
- [ ] No test regressions (existing tests still pass)

---

## Next Phase

Once Phase 0 is complete, proceed to **Phase 1 - Infrastructure Cleanup**:

- Verify `data_builders.py` imports
- Move cleanup helpers from coordinator to `kc_helpers.py`
- Prepare for first manager extraction (NotificationManager)

### Documentation Follow-Up

After Phase 0 implementation, add Event Architecture Standards to project documentation:

1. **Add to `DEVELOPMENT_STANDARDS.md`**:
   - Copy "Event Architecture Standards" section (lines 27-116 above)
   - Insert after "§4. DateTime & Scheduling Standards"
   - Update table of contents

2. **Benefits of formalized standards**:
   - Enforces past-tense convention for all future signals
   - Standardizes payload requirements (`changes` for updates, `user_name` for operations)
   - Prevents semantic ambiguity (reset vs. status_reset, lost vs. revoked)
   - Serves as reference for code reviews and new contributors
