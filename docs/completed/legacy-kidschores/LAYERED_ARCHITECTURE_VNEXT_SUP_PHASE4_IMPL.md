# Phase 4 Implementation Guide: Chore Stack

**Document Type:** Supporting Implementation Guide
**Parent Plan:** [LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md](./LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md)
**Phase:** 4 – Chore Stack ("The Job")
**Status:** Ready for Implementation
**Created:** 2026-01-25

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Method Extraction Map](#2-method-extraction-map)
3. [State Machine Specification](#3-state-machine-specification)
4. [TransitionEffect Data Structure](#4-transitioneffect-data-structure)
5. [ChoreEngine Implementation](#5-choreengine-implementation)
6. [ChoreManager Implementation](#6-choremanager-implementation)
7. [Event Payload Enrichment](#7-event-payload-enrichment)
8. [Scheduler Delegation Contract](#8-scheduler-delegation-contract)
9. [Migration Strategy](#9-migration-strategy)
10. [Test Strategy](#10-test-strategy)
11. [Validation Checklist](#11-validation-checklist)

---

## 1. Architecture Overview

### Core Philosophy: "Plan, Commit, Emit"

The Phase 4 refactor transforms procedural if/else blocks into a **Planning Pattern**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ChoreEngine (engines/chore_engine.py) - THE BRAIN                       │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Pure Python, NO HA dependencies                                       │
│ • Stateless static methods                                              │
│ • Returns TransitionEffect plans describing WHAT should happen          │
│ • Handles SHARED vs INDEPENDENT logic centrally                         │
│ • Validates state transitions against VALID_TRANSITIONS matrix          │
└─────────────────────────────────────────────────────────────────────────┘
                              │ returns plan ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ ChoreManager (managers/chore_manager.py) - THE MUSCLE                   │
│ ─────────────────────────────────────────────────────────────────────── │
│ • Extends BaseManager (emit/listen)                                     │
│ • Stateful: owns _approval_locks, references coordinator                │
│ • Executes lifecycle: Plan → Commit → Emit → Persist → Notify           │
│ • Invokes StatisticsEngine for stat tracking                            │
│ • Invokes EconomyManager for point operations                           │
│ • Invokes NotificationManager for alerts                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Engine = Pure Logic**: No `hass`, no `coordinator`, no side effects
2. **Manager = Orchestration**: Owns locks, emits events, calls other managers
3. **TransitionEffect = Plan**: Engine returns effects, Manager executes them
4. **update_stats Flag**: Controls whether stats (streaks, totals) are updated
5. **Rich Event Payloads**: Include all context Phase 5 (Gamification) needs

---

## 2. Method Extraction Map

### Source File Analysis

**File:** `custom_components/kidschores/coordinator_chore_operations.py`
**Total Lines:** 4,138
**Total Methods:** 43 (organized in 11 sections)

### Extraction Decision Matrix

| Section                              | Method                                      | Lines     | Target                             | Rationale                                         |
| ------------------------------------ | ------------------------------------------- | --------- | ---------------------------------- | ------------------------------------------------- |
| **§1 Service Entry Points**          |                                             |           |                                    |                                                   |
|                                      | `claim_chore()`                             | 170-370   | **Manager**                        | Side effects: notifications, state mutation       |
|                                      | `approve_chore()`                           | 373-820   | **Manager**                        | Complex: points, stats, challenges, notifications |
|                                      | `disapprove_chore()`                        | 823-1000  | **Manager**                        | Side effects: state reset, notifications          |
|                                      | `set_chore_due_date()`                      | 1002-1133 | **Manager**                        | Data mutation, validation                         |
|                                      | `skip_chore_due_date()`                     | 1136-1314 | **Manager**                        | Rescheduling, state reset                         |
|                                      | `reset_all_chores()`                        | 1317-1365 | **Manager**                        | Bulk data mutation                                |
|                                      | `reset_overdue_chores()`                    | 1368-1495 | **Manager**                        | State transitions, rescheduling                   |
| **§2 Coordinator Public API**        |                                             |           |                                    |                                                   |
|                                      | `chore_has_pending_claim()`                 | 1500-1516 | **Engine**                         | Pure query, no side effects                       |
|                                      | `chore_is_overdue()`                        | 1519-1532 | **Engine**                         | Pure query, no side effects                       |
|                                      | `chore_is_due()`                            | 1535-1603 | **Engine**                         | Pure calculation                                  |
|                                      | `get_chore_due_date()`                      | 1606-1640 | **Engine**                         | Pure query                                        |
|                                      | `get_chore_due_window_start()`              | 1643-1680 | **Engine**                         | Pure calculation                                  |
|                                      | `chore_is_approved_in_period()`             | 1683-1712 | **Engine**                         | Pure query                                        |
|                                      | `get_pending_chore_approvals()`             | 1715-1742 | **Engine**                         | Pure query (computed)                             |
|                                      | `pending_chore_approvals` (property)        | 1745-1752 | **Manager**                        | Wrapper for get_pending_chore_approvals           |
|                                      | `pending_chore_changed` (property)          | 1755-1758 | **Manager**                        | Runtime state flag                                |
|                                      | `undo_chore_claim()`                        | 1761-1850 | **Manager**                        | State mutation, skip_stats logic                  |
| **§3 Validation & Authorization**    |                                             |           |                                    |                                                   |
|                                      | `_can_claim_chore()`                        | 1854-1902 | **Engine**                         | Pure validation logic                             |
|                                      | `_can_approve_chore()`                      | 1905-1943 | **Engine**                         | Pure validation logic                             |
| **§4 State Machine**                 |                                             |           |                                    |                                                   |
|                                      | `_transition_chore_state()`                 | 1946-2100 | **Manager**                        | Core orchestration (calls Engine for validation)  |
| **§5 Data Management**               |                                             |           |                                    |                                                   |
|                                      | `_update_kid_chore_data()`                  | 2222-2495 | **Manager** (via StatisticsEngine) | Stats tracking - delegate to StatisticsEngine     |
|                                      | `_set_chore_claimed_completed_by()`         | 2570-2645 | **Manager**                        | Data mutation based on completion criteria        |
|                                      | `_clear_chore_claimed_completed_by()`       | 2648-2680 | **Manager**                        | Data mutation                                     |
|                                      | `_get_chore_data_for_kid()`                 | 2683-2692 | **Engine**                         | Pure query                                        |
|                                      | `_recalculate_chore_stats_for_kid()`        | 2695-2708 | **Manager** (via StatisticsEngine) | Delegates to StatisticsEngine                     |
|                                      | `_assign_kid_to_independent_chores()`       | 2711-2740 | **Manager**                        | Data mutation                                     |
|                                      | `_remove_kid_from_independent_chores()`     | 2743-2765 | **Manager**                        | Data mutation                                     |
| **§6 Query & Status Helpers**        |                                             |           |                                    |                                                   |
|                                      | `_chore_allows_multiple_claims()`           | 2770-2790 | **Engine**                         | Pure query                                        |
|                                      | `_count_chores_pending_for_kid()`           | 2793-2815 | **Engine**                         | Pure query (computed)                             |
|                                      | `_get_latest_chore_pending()`               | 2818-2855 | **Engine**                         | Pure query                                        |
|                                      | `_get_chore_effective_due_date()`           | 2858-2888 | **Engine**                         | Pure query                                        |
|                                      | `_get_chore_approval_period_start()`        | 2891-2918 | **Engine**                         | Pure query                                        |
| **§7 Scheduling & Rescheduling**     |                                             |           |                                    |                                                   |
|                                      | `_reschedule_chore_next_due()`              | 2920-2998 | **Manager**                        | Uses RecurrenceEngine, mutates data               |
|                                      | `_reschedule_chore_next_due_date_for_kid()` | 3001-3098 | **Manager**                        | Uses RecurrenceEngine, mutates data               |
|                                      | `_is_chore_approval_after_reset()`          | 3101-3160 | **Engine**                         | Pure calculation                                  |
| **§8 Recurring Chore Operations**    |                                             |           |                                    |                                                   |
|                                      | `_process_recurring_chore_resets()`         | 3165-3195 | **Manager**                        | Timer callback, calls other methods               |
|                                      | `_reset_chore_counts()`                     | 3198-3215 | **Manager**                        | Timer callback                                    |
|                                      | `_reschedule_recurring_chores()`            | 3218-3275 | **Manager**                        | Timer callback, iterates chores                   |
|                                      | `_reschedule_shared_recurring_chore()`      | 3278-3313 | **Manager**                        | Helper for §8                                     |
|                                      | `_reschedule_independent_recurring_chore()` | 3316-3370 | **Manager**                        | Helper for §8                                     |
| **§9 Daily Reset Operations**        |                                             |           |                                    |                                                   |
|                                      | `_reset_daily_chore_statuses()`             | 3375-3430 | **Manager**                        | Timer callback                                    |
|                                      | `_reset_shared_chore_status()`              | 3433-3505 | **Manager**                        | Helper for §9                                     |
|                                      | `_reset_independent_chore_status()`         | 3508-3590 | **Manager**                        | Helper for §9                                     |
|                                      | `_handle_pending_chore_claim_at_reset()`    | 3593-3645 | **Manager**                        | Complex logic with AUTO_APPROVE                   |
| **§10 Overdue Detection & Handling** |                                             |           |                                    |                                                   |
|                                      | `_check_chore_overdue_status()`             | 3650-3760 | **Manager**                        | Iterates kids, applies state                      |
|                                      | `_notify_overdue_chore()`                   | 3763-3855 | **Manager**                        | Side effects: notifications                       |
|                                      | `_check_overdue_chores()`                   | 3858-3920 | **Manager**                        | Timer callback                                    |
|                                      | `_handle_overdue_chore_state()`             | 3923-4010 | **Manager**                        | State mutation, notifications                     |
| **§11 Reminder System**              |                                             |           |                                    |                                                   |
|                                      | `_check_chore_due_reminders()`              | 4015-4125 | **Manager**                        | Timer callback, notifications                     |
|                                      | `_clear_chore_due_reminder()`               | 4128-4138 | **Manager**                        | Runtime state mutation                            |

### Summary Statistics

| Target           | Count      | Approximate Lines |
| ---------------- | ---------- | ----------------- |
| **ChoreEngine**  | 14 methods | ~600 lines        |
| **ChoreManager** | 29 methods | ~3,500 lines      |
| **Total**        | 43 methods | ~4,100 lines      |

---

## 3. State Machine Specification

### Chore States (from const.py lines 1531-1540)

```python
CHORE_STATE_PENDING = "pending"              # Available for claim
CHORE_STATE_CLAIMED = "claimed"              # Kid claimed, awaiting approval
CHORE_STATE_CLAIMED_IN_PART = "claimed_in_part"  # SHARED: Some kids claimed
CHORE_STATE_APPROVED = "approved"            # Completed and approved
CHORE_STATE_APPROVED_IN_PART = "approved_in_part"  # SHARED: Some kids approved
CHORE_STATE_OVERDUE = "overdue"              # Past due date
CHORE_STATE_COMPLETED_BY_OTHER = "completed_by_other"  # SHARED_FIRST: Another kid completed
CHORE_STATE_DUE = "due"                      # Within due window (before due date)
CHORE_STATE_INDEPENDENT = "independent"      # Multi-kid, different states
CHORE_STATE_UNKNOWN = "unknown"              # Error state
```

### Valid State Transitions Matrix

```python
VALID_TRANSITIONS: dict[str, list[str]] = {
    # From PENDING: Can be claimed, go overdue, or skipped
    CHORE_STATE_PENDING: [
        CHORE_STATE_CLAIMED,
        CHORE_STATE_OVERDUE,
        CHORE_STATE_COMPLETED_BY_OTHER,  # SHARED_FIRST: Another kid claimed
    ],

    # From CLAIMED: Awaiting parent decision
    CHORE_STATE_CLAIMED: [
        CHORE_STATE_APPROVED,
        CHORE_STATE_PENDING,      # Disapproved or undo
        CHORE_STATE_OVERDUE,      # Due date passed while claimed
    ],

    # From APPROVED: Reset for next occurrence
    CHORE_STATE_APPROVED: [
        CHORE_STATE_PENDING,      # Scheduled reset
    ],

    # From OVERDUE: Can still be claimed or reset
    CHORE_STATE_OVERDUE: [
        CHORE_STATE_CLAIMED,      # Kid claims overdue chore
        CHORE_STATE_PENDING,      # Manual/scheduled reset
        CHORE_STATE_APPROVED,     # Parent completes on behalf
    ],

    # From COMPLETED_BY_OTHER: Reset at scheduled time
    CHORE_STATE_COMPLETED_BY_OTHER: [
        CHORE_STATE_PENDING,      # Scheduled reset
    ],

    # Global states (multi-kid aggregation)
    CHORE_STATE_CLAIMED_IN_PART: [
        CHORE_STATE_APPROVED_IN_PART,
        CHORE_STATE_CLAIMED,
        CHORE_STATE_PENDING,
    ],

    CHORE_STATE_APPROVED_IN_PART: [
        CHORE_STATE_APPROVED,
        CHORE_STATE_PENDING,
    ],
}
```

### Completion Criteria Logic

| Criteria         | Behavior on Claim                          | Behavior on Approve    | Global State Calculation   |
| ---------------- | ------------------------------------------ | ---------------------- | -------------------------- |
| **INDEPENDENT**  | Kid's state → CLAIMED                      | Kid's state → APPROVED | INDEPENDENT if kids differ |
| **SHARED**       | Kid's state → CLAIMED                      | Kid's state → APPROVED | All must complete          |
| **SHARED_FIRST** | Kid → CLAIMED, others → COMPLETED_BY_OTHER | Completes for all      | First claimant wins        |

---

## 4. TransitionEffect Data Structure

### Definition (add to type_defs.py)

```python
from dataclasses import dataclass

@dataclass
class TransitionEffect:
    """Effect of a chore state transition for a single kid.

    Returned by ChoreEngine.calculate_transition() to describe
    what should happen for each affected kid.

    Attributes:
        kid_id: The kid affected by this transition
        new_state: Target chore state for this kid
        update_stats: Whether this transition counts toward stats (streaks, totals)
                     True for normal actions, False for undo/corrections
        points: Points to award (positive) or deduct (negative), 0 for no change
        clear_claimed_by: Whether to clear claimed_by field
        clear_completed_by: Whether to clear completed_by field
        set_claimed_by: Name to set as claimed_by (or None)
        set_completed_by: Name to set as completed_by (or None)
    """
    kid_id: str
    new_state: str
    update_stats: bool = True
    points: float = 0.0
    clear_claimed_by: bool = False
    clear_completed_by: bool = False
    set_claimed_by: str | None = None
    set_completed_by: str | None = None
```

### Usage Example

```python
# Engine calculates plan for SHARED_FIRST claim
effects = ChoreEngine.calculate_transition(
    chore_data=chore_info,
    actor_kid_id="kid-123",
    action=const.CHORE_ACTION_CLAIM,
    kids_assigned=["kid-123", "kid-456", "kid-789"],
)

# Returns:
# [
#     TransitionEffect(kid_id="kid-123", new_state="claimed", update_stats=True, set_claimed_by="Sarah"),
#     TransitionEffect(kid_id="kid-456", new_state="completed_by_other", update_stats=False),
#     TransitionEffect(kid_id="kid-789", new_state="completed_by_other", update_stats=False),
# ]

# Manager executes each effect
for effect in effects:
    await manager._apply_transition_effect(effect, chore_id)
```

---

## 5. ChoreEngine Implementation

### File: `engines/chore_engine.py`

```python
"""Chore Engine - Pure logic for chore state transitions and calculations.

This engine provides stateless, pure Python functions for:
- State transition validation and calculation
- TransitionEffect planning for multi-kid scenarios
- Point calculations with multipliers
- Completion criteria logic (SHARED, INDEPENDENT, SHARED_FIRST)
- Query functions for chore status checks

ARCHITECTURE: This is a pure logic engine with NO Home Assistant dependencies.
All functions are static methods that operate on passed-in data.
State management belongs in ChoreManager.

See docs/ARCHITECTURE.md for the Engine vs Manager distinction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from .. import const

if TYPE_CHECKING:
    from ..type_defs import ChoreData, KidChoreDataEntry, KidData


@dataclass
class TransitionEffect:
    """Effect of a chore state transition for a single kid."""
    kid_id: str
    new_state: str
    update_stats: bool = True
    points: float = 0.0
    clear_claimed_by: bool = False
    clear_completed_by: bool = False
    set_claimed_by: str | None = None
    set_completed_by: str | None = None


class ChoreEngine:
    """Pure logic engine for chore state transitions and calculations.

    All methods are static - no instance state. This enables easy unit testing
    without any Home Assistant mocking.
    """

    # Valid state transitions matrix
    VALID_TRANSITIONS: dict[str, list[str]] = {
        const.CHORE_STATE_PENDING: [
            const.CHORE_STATE_CLAIMED,
            const.CHORE_STATE_OVERDUE,
            const.CHORE_STATE_COMPLETED_BY_OTHER,
        ],
        const.CHORE_STATE_CLAIMED: [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_PENDING,
            const.CHORE_STATE_OVERDUE,
        ],
        const.CHORE_STATE_APPROVED: [
            const.CHORE_STATE_PENDING,
        ],
        const.CHORE_STATE_OVERDUE: [
            const.CHORE_STATE_CLAIMED,
            const.CHORE_STATE_PENDING,
            const.CHORE_STATE_APPROVED,
        ],
        const.CHORE_STATE_COMPLETED_BY_OTHER: [
            const.CHORE_STATE_PENDING,
        ],
        const.CHORE_STATE_CLAIMED_IN_PART: [
            const.CHORE_STATE_APPROVED_IN_PART,
            const.CHORE_STATE_CLAIMED,
            const.CHORE_STATE_PENDING,
        ],
        const.CHORE_STATE_APPROVED_IN_PART: [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_PENDING,
        ],
    }

    # =========================================================================
    # STATE TRANSITION LOGIC
    # =========================================================================

    @staticmethod
    def can_transition(current_state: str, target_state: str) -> bool:
        """Validate if a state transition is allowed.

        Args:
            current_state: Current chore state
            target_state: Desired new state

        Returns:
            True if transition is valid, False otherwise
        """
        valid_targets = ChoreEngine.VALID_TRANSITIONS.get(current_state, [])
        return target_state in valid_targets

    @staticmethod
    def calculate_transition(
        chore_data: ChoreData,
        actor_kid_id: str,
        action: str,
        kids_assigned: list[str],
        kid_name: str = "Unknown",
        skip_stats: bool = False,
    ) -> list[TransitionEffect]:
        """Calculate transition effects for ALL kids based on ONE action.

        This is the core planning method. It determines what state changes
        and side effects should occur for each assigned kid when one kid
        performs an action.

        Args:
            chore_data: The chore being acted upon
            actor_kid_id: The kid performing the action
            action: One of const.CHORE_ACTION_* values
            kids_assigned: All kids assigned to this chore
            kid_name: Display name of actor kid (for claimed_by/completed_by)
            skip_stats: If True, mark effects as update_stats=False

        Returns:
            List of TransitionEffect describing changes for each affected kid
        """
        effects: list[TransitionEffect] = []
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        points = chore_data.get(const.DATA_CHORE_DEFAULT_POINTS, 0.0)

        # === CLAIM ACTION ===
        if action == const.CHORE_ACTION_CLAIM:
            effects = ChoreEngine._plan_claim_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
                kid_name,
            )

        # === APPROVE ACTION ===
        elif action == const.CHORE_ACTION_APPROVE:
            effects = ChoreEngine._plan_approve_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
                kid_name,
                points,
            )

        # === DISAPPROVE ACTION ===
        elif action == const.CHORE_ACTION_DISAPPROVE:
            effects = ChoreEngine._plan_disapprove_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
            )

        # === UNDO ACTION ===
        elif action == const.CHORE_ACTION_UNDO:
            effects = ChoreEngine._plan_undo_effects(
                completion_criteria,
                actor_kid_id,
                kids_assigned,
            )
            # Undo never updates stats
            skip_stats = True

        # === RESET ACTION (scheduled) ===
        elif action == const.CHORE_ACTION_RESET:
            effects = ChoreEngine._plan_reset_effects(kids_assigned)

        # === OVERDUE ACTION ===
        elif action == const.CHORE_ACTION_OVERDUE:
            effects.append(TransitionEffect(
                kid_id=actor_kid_id,
                new_state=const.CHORE_STATE_OVERDUE,
                update_stats=True,
            ))

        # Apply skip_stats flag if set
        if skip_stats:
            for effect in effects:
                effect.update_stats = False

        return effects

    @staticmethod
    def _plan_claim_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
        kid_name: str,
    ) -> list[TransitionEffect]:
        """Plan effects for a claim action."""
        effects: list[TransitionEffect] = []

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Actor claims, others become completed_by_other
            effects.append(TransitionEffect(
                kid_id=actor_kid_id,
                new_state=const.CHORE_STATE_CLAIMED,
                update_stats=True,
                set_claimed_by=kid_name,
            ))
            for other_kid_id in kids_assigned:
                if other_kid_id != actor_kid_id:
                    effects.append(TransitionEffect(
                        kid_id=other_kid_id,
                        new_state=const.CHORE_STATE_COMPLETED_BY_OTHER,
                        update_stats=False,
                        set_claimed_by=kid_name,
                    ))
        else:
            # INDEPENDENT or SHARED: Only actor transitions
            effects.append(TransitionEffect(
                kid_id=actor_kid_id,
                new_state=const.CHORE_STATE_CLAIMED,
                update_stats=True,
                set_claimed_by=kid_name,
            ))

        return effects

    @staticmethod
    def _plan_approve_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
        kid_name: str,
        points: float,
    ) -> list[TransitionEffect]:
        """Plan effects for an approve action."""
        effects: list[TransitionEffect] = []

        effects.append(TransitionEffect(
            kid_id=actor_kid_id,
            new_state=const.CHORE_STATE_APPROVED,
            update_stats=True,
            points=points,
            set_completed_by=kid_name,
        ))

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Update completed_by for other kids (who are in completed_by_other state)
            for other_kid_id in kids_assigned:
                if other_kid_id != actor_kid_id:
                    effects.append(TransitionEffect(
                        kid_id=other_kid_id,
                        new_state=const.CHORE_STATE_COMPLETED_BY_OTHER,
                        update_stats=False,
                        set_completed_by=kid_name,
                    ))

        return effects

    @staticmethod
    def _plan_disapprove_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
    ) -> list[TransitionEffect]:
        """Plan effects for a disapprove action."""
        effects: list[TransitionEffect] = []

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Reset ALL kids to pending
            for kid_id in kids_assigned:
                effects.append(TransitionEffect(
                    kid_id=kid_id,
                    new_state=const.CHORE_STATE_PENDING,
                    update_stats=(kid_id == actor_kid_id),  # Only actor gets stat
                    clear_claimed_by=True,
                    clear_completed_by=True,
                ))
        else:
            # INDEPENDENT or SHARED: Only actor transitions
            effects.append(TransitionEffect(
                kid_id=actor_kid_id,
                new_state=const.CHORE_STATE_PENDING,
                update_stats=True,
            ))

        return effects

    @staticmethod
    def _plan_undo_effects(
        criteria: str,
        actor_kid_id: str,
        kids_assigned: list[str],
    ) -> list[TransitionEffect]:
        """Plan effects for an undo (kid self-undo) action."""
        effects: list[TransitionEffect] = []

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Reset ALL kids to pending (same as disapproval)
            for kid_id in kids_assigned:
                effects.append(TransitionEffect(
                    kid_id=kid_id,
                    new_state=const.CHORE_STATE_PENDING,
                    update_stats=False,  # Undo never updates stats
                    clear_claimed_by=True,
                    clear_completed_by=True,
                ))
        else:
            effects.append(TransitionEffect(
                kid_id=actor_kid_id,
                new_state=const.CHORE_STATE_PENDING,
                update_stats=False,
            ))

        return effects

    @staticmethod
    def _plan_reset_effects(kids_assigned: list[str]) -> list[TransitionEffect]:
        """Plan effects for a scheduled reset."""
        return [
            TransitionEffect(
                kid_id=kid_id,
                new_state=const.CHORE_STATE_PENDING,
                update_stats=False,
                clear_claimed_by=True,
                clear_completed_by=True,
            )
            for kid_id in kids_assigned
        ]

    # =========================================================================
    # VALIDATION LOGIC (from §3)
    # =========================================================================

    @staticmethod
    def can_claim_chore(
        kid_chore_data: KidChoreDataEntry | dict[str, Any],
        chore_data: ChoreData,
        has_pending_claim: bool,
        is_approved_in_period: bool,
    ) -> tuple[bool, str | None]:
        """Check if a kid can claim a specific chore.

        Args:
            kid_chore_data: The kid's tracking data for this chore
            chore_data: The chore definition
            has_pending_claim: Result of chore_has_pending_claim()
            is_approved_in_period: Result of chore_is_approved_in_period()

        Returns:
            Tuple of (can_claim: bool, error_key: str | None)
        """
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all claims
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Check multi-claim allowed
        allow_multiple = ChoreEngine.chore_allows_multiple_claims(chore_data)

        # Check 2: pending claim blocks new claims (unless multi-claim)
        if not allow_multiple and has_pending_claim:
            return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)

        # Check 3: already approved in current period (unless multi-claim)
        if not allow_multiple and is_approved_in_period:
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    @staticmethod
    def can_approve_chore(
        kid_chore_data: KidChoreDataEntry | dict[str, Any],
        chore_data: ChoreData,
        is_approved_in_period: bool,
    ) -> tuple[bool, str | None]:
        """Check if a chore can be approved for a specific kid.

        Args:
            kid_chore_data: The kid's tracking data for this chore
            chore_data: The chore definition
            is_approved_in_period: Result of chore_is_approved_in_period()

        Returns:
            Tuple of (can_approve: bool, error_key: str | None)
        """
        current_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Check 1: completed_by_other blocks all approvals
        if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
            return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Check 2: already approved (unless multi-claim)
        allow_multiple = ChoreEngine.chore_allows_multiple_claims(chore_data)
        if not allow_multiple and is_approved_in_period:
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    # =========================================================================
    # QUERY FUNCTIONS (from §2, §6)
    # =========================================================================

    @staticmethod
    def chore_has_pending_claim(
        kid_chore_data: KidChoreDataEntry | dict[str, Any],
    ) -> bool:
        """Check if a chore has a pending claim.

        Uses the pending_count counter which is incremented on claim and
        decremented on approve/disapprove.
        """
        pending_count = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        return pending_count > 0

    @staticmethod
    def chore_is_overdue(
        kid_chore_data: KidChoreDataEntry | dict[str, Any],
    ) -> bool:
        """Check if a chore is in overdue state for a specific kid."""
        current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
        return current_state == const.CHORE_STATE_OVERDUE

    @staticmethod
    def chore_allows_multiple_claims(chore_data: ChoreData) -> bool:
        """Check if chore allows multiple claims per approval period."""
        approval_reset_type = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        return approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        )

    @staticmethod
    def is_shared_chore(chore_data: ChoreData) -> bool:
        """Check if chore uses shared completion criteria."""
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        return criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        )

    @staticmethod
    def get_chore_data_for_kid(
        kid_data: KidData,
        chore_id: str,
    ) -> KidChoreDataEntry | dict[str, Any]:
        """Get the chore data dict for a specific kid+chore combination."""
        return kid_data.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})

    # =========================================================================
    # POINT CALCULATIONS
    # =========================================================================

    @staticmethod
    def calculate_points(
        chore_data: ChoreData,
        multiplier: float = 1.0,
    ) -> float:
        """Calculate points for chore completion with optional multiplier.

        Args:
            chore_data: The chore definition
            multiplier: Point multiplier (default 1.0)

        Returns:
            Calculated points, rounded to DATA_FLOAT_PRECISION
        """
        base_points = chore_data.get(
            const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS
        )
        result = base_points * multiplier
        return round(result, const.DATA_FLOAT_PRECISION)

    # =========================================================================
    # GLOBAL STATE CALCULATION
    # =========================================================================

    @staticmethod
    def compute_global_chore_state(
        chore_data: ChoreData,
        kid_states: dict[str, str],
    ) -> str:
        """Compute the aggregate chore state from per-kid states.

        Args:
            chore_data: The chore definition
            kid_states: Dict mapping kid_id to their current state

        Returns:
            The global chore state string
        """
        if not kid_states:
            return const.CHORE_STATE_UNKNOWN

        assigned_kids = list(kid_states.keys())
        total = len(assigned_kids)

        if total == 1:
            return next(iter(kid_states.values()))

        # Count states
        count_pending = sum(1 for s in kid_states.values() if s == const.CHORE_STATE_PENDING)
        count_claimed = sum(1 for s in kid_states.values() if s == const.CHORE_STATE_CLAIMED)
        count_approved = sum(1 for s in kid_states.values() if s == const.CHORE_STATE_APPROVED)
        count_overdue = sum(1 for s in kid_states.values() if s == const.CHORE_STATE_OVERDUE)
        count_completed_by_other = sum(1 for s in kid_states.values() if s == const.CHORE_STATE_COMPLETED_BY_OTHER)

        # All same state
        if count_pending == total:
            return const.CHORE_STATE_PENDING
        if count_claimed == total:
            return const.CHORE_STATE_CLAIMED
        if count_approved == total:
            return const.CHORE_STATE_APPROVED
        if count_overdue == total:
            return const.CHORE_STATE_OVERDUE

        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # SHARED_FIRST: Global state tracks the claimant's progression
        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            if count_approved > 0:
                return const.CHORE_STATE_APPROVED
            if count_claimed > 0:
                return const.CHORE_STATE_CLAIMED
            if count_overdue > 0:
                return const.CHORE_STATE_OVERDUE
            return const.CHORE_STATE_PENDING

        # SHARED: Partial states
        if criteria == const.COMPLETION_CRITERIA_SHARED:
            if count_overdue > 0:
                return const.CHORE_STATE_OVERDUE
            if count_approved > 0:
                return const.CHORE_STATE_APPROVED_IN_PART
            if count_claimed > 0:
                return const.CHORE_STATE_CLAIMED_IN_PART
            return const.CHORE_STATE_UNKNOWN

        # INDEPENDENT: Different states
        return const.CHORE_STATE_INDEPENDENT
```

---

## 6. ChoreManager Implementation

### File: `managers/chore_manager.py`

**Note:** This is an outline. Full implementation is ~3,500 lines.

```python
"""Chore Manager - Stateful chore workflow orchestration.

This manager handles all chore lifecycle operations:
- Claim, approve, disapprove workflows
- State transitions with lock protection
- Point awards via EconomyManager
- Notifications via NotificationManager
- Statistics tracking via StatisticsEngine
- Event emission for Gamification listeners

ARCHITECTURE: This manager owns data mutations and side effects.
Business logic decisions are delegated to ChoreEngine.

See docs/ARCHITECTURE.md for the Manager vs Engine distinction.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .. import const
from ..engines.chore_engine import ChoreEngine, TransitionEffect
from ..engines.statistics import StatisticsEngine
from .base_manager import BaseManager

if TYPE_CHECKING:
    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import ChoreData, KidData
    from .economy_manager import EconomyManager
    from .notification_manager import NotificationManager


class ChoreManager(BaseManager):
    """Stateful manager for chore workflows.

    Lifecycle for state-changing operations:
    1. Plan: Call ChoreEngine to get list[TransitionEffect]
    2. Commit: Mutate coordinator.data, update StatisticsEngine
    3. Emit: Fire SIGNAL_SUFFIX_CHORE_* events
    4. Persist: Call coordinator._persist()
    5. Notify: Call NotificationManager
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
        economy_manager: EconomyManager,
        notification_manager: NotificationManager,
    ) -> None:
        """Initialize ChoreManager with dependencies."""
        super().__init__(hass, coordinator)
        self.economy_manager = economy_manager
        self.notification_manager = notification_manager
        self._approval_locks: dict[str, asyncio.Lock] = {}
        self._due_soon_reminders_sent: set[str] = set()
        self._pending_chore_changed: bool = False

    async def async_setup(self) -> None:
        """Set up the chore manager (no-op for now)."""
        pass

    # =========================================================================
    # LOCK MANAGEMENT (Trap 3 mitigation)
    # =========================================================================

    def _get_lock(self, chore_id: str) -> asyncio.Lock:
        """Get or create lock for a chore to prevent race conditions."""
        if chore_id not in self._approval_locks:
            self._approval_locks[chore_id] = asyncio.Lock()
        return self._approval_locks[chore_id]

    # =========================================================================
    # SERVICE ENTRY POINTS (from §1)
    # =========================================================================

    async def claim(
        self,
        kid_id: str,
        chore_id: str,
        user_name: str,
    ) -> None:
        """Kid claims chore - validates, transitions state, notifies parents.

        Lifecycle:
        1. Validate kid and chore exist
        2. Check can_claim via Engine
        3. Get TransitionEffects from Engine
        4. Apply effects (state changes)
        5. Emit SIGNAL_SUFFIX_CHORE_CLAIMED
        6. Persist and notify
        """
        # Implementation follows existing claim_chore() logic
        # but uses ChoreEngine.calculate_transition() for planning
        ...

    async def approve(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        points_override: float | None = None,
    ) -> None:
        """Parent approves chore - awards points, emits event.

        Lifecycle (with lock protection):
        1. Acquire lock for kid+chore
        2. Re-validate inside lock (race condition protection)
        3. Get TransitionEffects from Engine
        4. Apply effects (state changes)
        5. Call economy_manager.deposit() for points
        6. Update achievements/challenges (inline for now, Phase 5 moves to listener)
        7. Emit SIGNAL_SUFFIX_CHORE_APPROVED with rich payload
        8. Persist and notify
        """
        lock = self._get_lock(chore_id)
        async with lock:
            # Implementation follows existing approve_chore() logic
            # Event payload includes: chore_labels, multiplier_applied, previous_state, update_stats
            ...

    async def disapprove(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        reason: str | None = None,
    ) -> None:
        """Parent disapproves - resets state, notifies kid."""
        ...

    async def undo_claim(
        self,
        kid_id: str,
        chore_id: str,
    ) -> None:
        """Kid undoes their own claim (no stat tracking)."""
        ...

    # =========================================================================
    # SCHEDULER CALLBACKS (Trap 1 mitigation)
    # =========================================================================

    async def update_recurring_chores(self, now: datetime) -> None:
        """Process recurring chore resets.

        Called by coordinator's time-based scheduler.
        Coordinator owns the timer, Manager owns the logic.
        """
        # Implementation from _process_recurring_chore_resets()
        ...

    async def update_overdue_status(self, now: datetime) -> None:
        """Check for overdue chores and apply state changes.

        Called by coordinator's time-based scheduler.
        """
        # Implementation from _check_overdue_chores()
        ...

    async def check_due_reminders(self) -> None:
        """Check for chores due soon and send reminders.

        Called by coordinator's refresh cycle.
        """
        # Implementation from _check_chore_due_reminders()
        ...

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _apply_transition_effects(
        self,
        effects: list[TransitionEffect],
        chore_id: str,
        chore_data: ChoreData,
    ) -> None:
        """Apply a list of transition effects to coordinator data.

        For each effect:
        1. Update kid_chore_data state
        2. Update claimed_by/completed_by fields
        3. Track statistics if update_stats=True (Trap 2 mitigation)
        4. Award/deduct points if effect.points != 0
        """
        for effect in effects:
            kid_data = self.coordinator.kids_data.get(effect.kid_id)
            if not kid_data:
                continue

            # Update state
            kid_chore_data = kid_data.setdefault(const.DATA_KID_CHORE_DATA, {})
            chore_entry = kid_chore_data.setdefault(chore_id, {})
            chore_entry[const.DATA_KID_CHORE_DATA_STATE] = effect.new_state

            # Update claimed_by/completed_by
            if effect.clear_claimed_by:
                chore_entry.pop(const.DATA_CHORE_CLAIMED_BY, None)
            if effect.clear_completed_by:
                chore_entry.pop(const.DATA_CHORE_COMPLETED_BY, None)
            if effect.set_claimed_by:
                chore_entry[const.DATA_CHORE_CLAIMED_BY] = effect.set_claimed_by
            if effect.set_completed_by:
                chore_entry[const.DATA_CHORE_COMPLETED_BY] = effect.set_completed_by

            # Track statistics (Trap 2 mitigation)
            if effect.update_stats:
                self.coordinator.stats.record_transaction(
                    # ... stats params
                )

            # Award points
            if effect.points != 0:
                await self.economy_manager.deposit(
                    effect.kid_id,
                    effect.points,
                    source=const.LEDGER_SOURCE_CHORE,
                    reference_id=chore_id,
                )

    def _emit_chore_event(
        self,
        signal_suffix: str,
        kid_id: str,
        chore_id: str,
        chore_data: ChoreData,
        **extra_fields: Any,
    ) -> None:
        """Emit a chore event with rich payload for Phase 5.

        All chore events include:
        - kid_id, chore_id, chore_name
        - chore_labels (for badge criteria)
        - update_stats (for gamification filtering)
        """
        payload = {
            "kid_id": kid_id,
            "chore_id": chore_id,
            "chore_name": chore_data.get(const.DATA_CHORE_NAME, ""),
            "chore_labels": chore_data.get(const.DATA_CHORE_LABELS, []),
            "update_stats": extra_fields.pop("update_stats", True),
            **extra_fields,
        }
        self.emit(signal_suffix, payload)
```

---

## 7. Event Payload Enrichment

### Updates to type_defs.py

Add/modify these TypedDicts:

```python
class ChoreClaimedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_CLAIMED."""
    kid_id: str  # Required
    chore_id: str  # Required
    chore_name: str  # Required
    user_name: str  # Required (who initiated claim)
    chore_labels: list[str]  # NEW: For badge criteria
    update_stats: bool  # NEW: Whether to update statistics


class ChoreApprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_APPROVED."""
    kid_id: str  # Required
    chore_id: str  # Required
    parent_name: str  # Required
    points_awarded: float  # Required
    is_shared: bool  # Required
    is_multi_claim: bool  # Required
    chore_labels: list[str]  # NEW: For badge criteria ("Clean 5 Kitchen chores")
    multiplier_applied: float  # NEW: For point calculation verification
    previous_state: str  # NEW: To detect re-approvals vs new approvals
    update_stats: bool  # NEW: Whether to update statistics


class ChoreDisapprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_DISAPPROVED."""
    kid_id: str  # Required
    chore_id: str  # Required
    parent_name: str  # Required
    reason: str | None  # Optional
    chore_labels: list[str]  # NEW
    previous_state: str  # NEW
    update_stats: bool  # NEW
```

---

## 8. Scheduler Delegation Contract

### Trap 1 Mitigation: "Orphaned Scheduler"

**Problem:** Coordinator owns timers (`async_track_time_change`), but if logic moves to Manager without clear contract, recurring chores break.

**Solution:** Coordinator keeps timers, delegates to Manager methods.

### Coordinator Side (coordinator.py)

```python
class KidsChoresDataCoordinator:
    def __init__(self, ...):
        ...
        self.chore_manager = ChoreManager(
            hass, self, self.economy_manager, self.notification_manager
        )

    async def _async_update_data(self):
        """Coordinator refresh cycle."""
        now = dt_util.utcnow()

        # Delegate to ChoreManager
        await self.chore_manager.update_recurring_chores(now)
        await self.chore_manager.update_overdue_status(now)
        await self.chore_manager.check_due_reminders()

        return self._data

    async def _handle_midnight_reset(self, now: datetime):
        """Timer callback for midnight."""
        await self.chore_manager.reset_daily_chore_statuses([const.FREQUENCY_DAILY])
```

### Manager Side (chore_manager.py)

```python
class ChoreManager:
    async def update_recurring_chores(self, now: datetime) -> None:
        """Called by coordinator timer - owns all logic."""
        # Full implementation from _process_recurring_chore_resets

    async def update_overdue_status(self, now: datetime) -> None:
        """Called by coordinator timer - owns all logic."""
        # Full implementation from _check_overdue_chores
```

---

## 9. Migration Strategy

### Phase 4 Deprecation Approach

**DO NOT delete `coordinator_chore_operations.py` immediately.**

### Step 1: Create New Files

1. `engines/chore_engine.py` - Pure logic (new)
2. `managers/chore_manager.py` - Stateful workflows (new)

### Step 2: Add Deprecation Wrapper

```python
# coordinator_chore_operations.py (existing file)
"""
DEPRECATED: This file is being phased out in favor of ChoreManager.
All methods now delegate to self.chore_manager.

Migration status:
- claim_chore: ✅ Delegated
- approve_chore: ✅ Delegated
- disapprove_chore: ✅ Delegated
- ... etc
"""

class ChoreOperations:
    def claim_chore(self, kid_id: str, chore_id: str, user_name: str):
        """DEPRECATED: Delegates to ChoreManager.claim()."""
        return self.hass.async_create_task(
            self.chore_manager.claim(kid_id, chore_id, user_name)
        )
```

### Step 3: Gradual Migration

Migrate methods one at a time:

1. Implement in ChoreManager
2. Update wrapper to delegate
3. Run tests
4. Repeat

### Step 4: Final Cleanup (Phase 6)

Once all methods migrated and tests pass:

1. Remove ChoreOperations mixin from coordinator inheritance
2. Delete `coordinator_chore_operations.py`
3. Update imports

---

## 10. Test Strategy

### Existing Tests to Preserve (MUST PASS)

```bash
# Primary regression tests
pytest tests/test_workflow_chores.py -v

# Service integration tests
pytest tests/test_services.py -v -k "chore"

# Sensor tests (state display)
pytest tests/test_sensor.py -v -k "chore"
```

### New Tests to Create

#### 10.1 ChoreEngine Tests (Pure Python)

**File:** `tests/test_chore_engine.py`

```python
"""Tests for ChoreEngine - pure logic, no HA fixtures needed."""

import pytest
from custom_components.kidschores.engines.chore_engine import (
    ChoreEngine,
    TransitionEffect,
)
from custom_components.kidschores import const


class TestStateTransitions:
    """Test state transition validation."""

    def test_pending_to_claimed_allowed(self):
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_PENDING, const.CHORE_STATE_CLAIMED
        )

    def test_approved_to_claimed_not_allowed(self):
        assert not ChoreEngine.can_transition(
            const.CHORE_STATE_APPROVED, const.CHORE_STATE_CLAIMED
        )


class TestCalculateTransition:
    """Test transition effect planning."""

    def test_claim_shared_first_affects_all_kids(self):
        """SHARED_FIRST: Claiming kid → CLAIMED, others → COMPLETED_BY_OTHER."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id="kid-1",
            action=const.CHORE_ACTION_CLAIM,
            kids_assigned=["kid-1", "kid-2", "kid-3"],
            kid_name="Sarah",
        )

        assert len(effects) == 3

        # Actor kid
        actor_effect = next(e for e in effects if e.kid_id == "kid-1")
        assert actor_effect.new_state == const.CHORE_STATE_CLAIMED
        assert actor_effect.update_stats is True
        assert actor_effect.set_claimed_by == "Sarah"

        # Other kids
        for kid_id in ["kid-2", "kid-3"]:
            effect = next(e for e in effects if e.kid_id == kid_id)
            assert effect.new_state == const.CHORE_STATE_COMPLETED_BY_OTHER
            assert effect.update_stats is False

    def test_undo_never_updates_stats(self):
        """Undo action should always set update_stats=False."""
        effects = ChoreEngine.calculate_transition(
            chore_data={const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT},
            actor_kid_id="kid-1",
            action=const.CHORE_ACTION_UNDO,
            kids_assigned=["kid-1"],
        )

        assert all(e.update_stats is False for e in effects)


class TestValidation:
    """Test claim/approve validation logic."""

    def test_completed_by_other_blocks_claim(self):
        kid_chore_data = {
            const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_COMPLETED_BY_OTHER,
        }
        chore_data = {}

        can_claim, error = ChoreEngine.can_claim_chore(
            kid_chore_data, chore_data, False, False
        )

        assert can_claim is False
        assert error == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER
```

#### 10.2 ChoreManager Tests (Integration)

**File:** `tests/test_chore_manager.py`

```python
"""Tests for ChoreManager - integration tests with mocked dependencies."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.kidschores.managers.chore_manager import ChoreManager
from custom_components.kidschores import const


@pytest.fixture
def mock_coordinator(scenario_medium):
    """Coordinator with medium scenario data."""
    return scenario_medium


@pytest.fixture
def mock_economy_manager():
    """Mocked EconomyManager."""
    manager = MagicMock()
    manager.deposit = AsyncMock()
    manager.withdraw = AsyncMock()
    return manager


@pytest.fixture
def mock_notification_manager():
    """Mocked NotificationManager."""
    manager = MagicMock()
    manager.send_kid_notification = AsyncMock()
    manager.send_parent_notification = AsyncMock()
    return manager


class TestClaimWorkflow:
    """Test claim operation end-to-end."""

    async def test_claim_emits_event_with_labels(
        self,
        hass,
        mock_coordinator,
        mock_economy_manager,
        mock_notification_manager,
    ):
        """Verify claim emits event with chore_labels for Phase 5."""
        manager = ChoreManager(
            hass, mock_coordinator, mock_economy_manager, mock_notification_manager
        )

        # Add chore with labels
        chore_id = "test-chore"
        mock_coordinator.chores_data[chore_id] = {
            const.DATA_CHORE_NAME: "Test Chore",
            const.DATA_CHORE_LABELS: ["kitchen", "daily"],
            const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1"],
        }

        with patch.object(manager, "emit") as mock_emit:
            await manager.claim("kid-1", chore_id, "Sarah")

            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            payload = call_args[0][1]

            assert payload["chore_labels"] == ["kitchen", "daily"]
            assert payload["update_stats"] is True


class TestApproveWithLock:
    """Test approval race condition protection."""

    async def test_concurrent_approvals_prevented(
        self,
        hass,
        mock_coordinator,
        mock_economy_manager,
        mock_notification_manager,
    ):
        """Only first approval should succeed when called concurrently."""
        manager = ChoreManager(
            hass, mock_coordinator, mock_economy_manager, mock_notification_manager
        )

        # Setup claimed chore
        # ... test concurrent approve calls
```

---

## 11. Validation Checklist

### Pre-Implementation

- [ ] Read full `coordinator_chore_operations.py` (4,138 lines)
- [ ] Understand all 43 methods and their interactions
- [ ] Review existing test coverage in `test_workflow_chores.py`
- [ ] Confirm Phase 3 (Economy) is complete and working

### During Implementation

- [ ] **Step 1**: Create `engines/chore_engine.py` with TransitionEffect
- [ ] **Step 2**: Implement Engine query/validation methods (§2, §3, §6)
- [ ] **Step 3**: Implement `calculate_transition()` with all action types
- [ ] **Step 4**: Create `managers/chore_manager.py` scaffold
- [ ] **Step 5**: Implement `claim()` with Engine delegation
- [ ] **Step 6**: Run `test_workflow_chores.py` - verify claim tests pass
- [ ] **Step 7**: Implement `approve()` with lock protection
- [ ] **Step 8**: Enrich event payloads in `type_defs.py`
- [ ] **Step 9**: Run full test suite
- [ ] **Step 10**: Implement scheduler delegation methods
- [ ] **Step 11**: Deprecate ChoreOperations methods (wrapper pattern)

### Post-Implementation

- [ ] `./utils/quick_lint.sh --fix` passes (9.5+/10)
- [ ] `mypy custom_components/kidschores/` has 0 errors
- [ ] `pytest tests/ -v --tb=line` all tests pass
- [ ] `pytest tests/test_workflow_chores.py -v` passes without modification
- [ ] Manual test: Approve chore → Points increase → Notification → Badge check

### Definition of Done

1. ✅ ChoreEngine exists with all query/validation methods
2. ✅ ChoreManager implements claim/approve/disapprove via Engine
3. ✅ Event payloads include `chore_labels`, `multiplier_applied`, `previous_state`, `update_stats`
4. ✅ Scheduler callbacks delegate to Manager
5. ✅ All existing workflow tests pass
6. ✅ New Engine tests pass (pure Python)
7. ✅ New Manager tests pass (integration)
8. ✅ Zero mypy errors
9. ✅ Lint score ≥ 9.5/10

---

## Appendix A: Action Constants

Add to `const.py` if not present:

```python
# Chore Actions (for ChoreEngine.calculate_transition)
CHORE_ACTION_CLAIM = "claim"
CHORE_ACTION_APPROVE = "approve"
CHORE_ACTION_DISAPPROVE = "disapprove"
CHORE_ACTION_UNDO = "undo"
CHORE_ACTION_RESET = "reset"
CHORE_ACTION_OVERDUE = "overdue"
```

---

## Appendix B: File Size Estimates

| File                          | Estimated Lines | Notes                        |
| ----------------------------- | --------------- | ---------------------------- |
| `engines/chore_engine.py`     | ~600            | Pure logic, well-documented  |
| `managers/chore_manager.py`   | ~3,500          | Orchestration, notifications |
| `tests/test_chore_engine.py`  | ~400            | Pure Python tests            |
| `tests/test_chore_manager.py` | ~600            | Integration tests            |

---

## Appendix C: Lessons Learned (Post-Implementation)

**Added:** 2026-01-25 after Phase 4.5 implementation

### Critical Discovery: "Zombie Manager" Problem

The initial Phase 4 implementation created managers but **did not wire them into the active execution path**. The coordinator delegated to managers, but managers called back to legacy coordinator methods, creating a circular pattern where new logic was never executed.

#### Root Cause Analysis

| Problem                                                 | Symptom                                             | Root Cause                                                         |
| ------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------ |
| ChoreManager `_apply_effect()` delegated to coordinator | New state machine logic bypassed                    | Manager wasn't the source of truth                                 |
| Tests passed without managers                           | Workflow tests hit legacy paths only                | No integration tests verifying manager was called                  |
| `immediate_on_late` feature missing                     | 4 tests failed in `test_overdue_immediate_reset.py` | ChoreManager only handled `UPON_COMPLETION`, not overdue scenarios |

#### What We Should Have Done Differently

1. **Verify Active Execution Path FIRST**
   - Before writing any new code, trace the full call path from service → coordinator → manager → effect
   - Add debug logging at each layer to confirm code is actually reached
   - A simple `print("ChoreManager._apply_effect called")` would have caught this in 5 minutes

2. **Write "Canary" Tests Before Implementation**

   ```python
   async def test_approve_calls_chore_manager(hass, scenario):
       """Verify ChoreManager is actually used, not legacy code."""
       with patch.object(coordinator.chore_manager, 'approve_chore') as mock:
           await coordinator.approve_chore("Parent", kid_id, chore_id)
           mock.assert_called_once()  # Would have caught the zombie manager
   ```

3. **Implement SHARED vs INDEPENDENT Logic From Day One**
   - The Phase 4 plan mentioned completion criteria but implementation assumed single-kid scenarios
   - Multi-kid scenarios (SHARED, INDEPENDENT) have fundamentally different reset behaviors:
     - **SHARED**: Reset ALL kids only when ALL have approved
     - **INDEPENDENT**: Reset ONLY the approving kid
   - This should have been explicit in the implementation checklist, not discovered via test failures

4. **Don't Trust "All Tests Pass" After Major Refactor**
   - If tests pass but new code wasn't exercised, the tests are testing the old code path
   - Add assertions that specifically verify new code paths are hit
   - Consider mutation testing or coverage for new files specifically

### Specific Implementation Gaps Found

| Feature                                   | Expected Behavior                            | What Was Missing                                      | Fix Applied                                     |
| ----------------------------------------- | -------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------- |
| `immediate_on_late` for AT_MIDNIGHT types | Reset to PENDING if due date < last midnight | `_is_approval_after_reset_boundary()` not implemented | Added 80-line helper method                     |
| `immediate_on_late` for AT_DUE_DATE types | Reset to PENDING if now > due date           | Same as above                                         | Same fix                                        |
| SHARED chore reset timing                 | Reset ALL kids when ALL approve              | Reset triggered on first kid's approval               | Added `_all_kids_approved()` helper             |
| INDEPENDENT chore reset scope             | Reset ONLY the approving kid                 | Reset triggered ALL kids                              | Modified to pass `[kid_id]` not `kids_assigned` |

### Type System Lessons

1. **Match TypedDict to Actual Usage**
   - `chore_data` was typed as `dict[str, Any]` in some places but actually `ChoreData` (TypedDict)
   - Caused mypy errors when passing between functions
   - **Solution**: Be consistent with types, import `ChoreData` where needed

2. **Dynamic Key Patterns Break TypedDict**
   - `day_map.get(d.lower(), d)` where `d` is string but map returns int
   - Can't use dynamic default with typed dict
   - **Solution**: Use explicit loops with `if isinstance()` checks

### Testing Lessons

1. **Multi-Kid Scenarios Need Explicit Tests**
   - `test_overdue_immediate_reset.py` was correctly written to test:
     - Single kid (MULTI approval type)
     - INDEPENDENT (each kid resets independently)
     - SHARED (all kids must approve before reset)
   - These tests caught real bugs that unit tests missed

2. **State Machine Tests Should Verify Side Effects**
   - Not just "state changed to X" but "state changed AND due date rescheduled AND other kids unaffected"

### Recommended Checklist Additions for Future Phases

Add to validation checklist:

```markdown
### Active Execution Path Verification

- [ ] Add temporary debug log to new Manager method
- [ ] Run workflow test, confirm log appears
- [ ] Remove debug log after verification

### Multi-Entity Scenarios

- [ ] Single-kid case tested
- [ ] Two-kid SHARED case tested (reset timing)
- [ ] Two-kid INDEPENDENT case tested (isolation)
- [ ] Edge case: One kid approved, one pending, then pending kid approves
```

### Summary: The 5-Minute Check That Would Have Saved Hours

Before considering any Phase 4+ implementation "complete":

```bash
# 1. Verify new code is actually called
grep -n "LOGGER.debug.*ChoreManager" custom_components/kidschores/managers/chore_manager.py
# If no logs, add them and run a workflow test

# 2. Run the specific tests for the feature being implemented
pytest tests/test_overdue_immediate_reset.py -v  # Don't rely on full suite passing

# 3. Check that multi-kid scenarios are covered
grep -l "INDEPENDENT\|SHARED" tests/test_*.py  # Find relevant test files
```

---

## Appendix D: Phase 4 Architectural Review (2026-01-25)

**Added:** Post-implementation review identifying remaining gaps

### 🔴 Critical Misses Assessment

#### 1. "Orphaned Scheduler" Status: ❌ BLOCKS PHASE 5 (Requires Phase 4.5b)

**Finding:** The timer callbacks (`_process_recurring_chore_resets`, `_check_overdue_chores`) are registered in `coordinator.py` but implemented in the `ChoreOperationsMixin` (`coordinator_chore_operations.py`).

**Original Assessment (REVISED):**

- ~~"This is acceptable because timers fire correctly"~~
- **CORRECTION**: Legacy timer logic does NOT emit `SIGNAL_SUFFIX_CHORE_*` events
- Phase 5's Event-Driven Gamification Manager REQUIRES these events to react to time-based state changes

**Why This Blocks Phase 5:**

```
Timer fires → Legacy Mixin → State changes (no events) → ❌ GamificationManager deaf
```

**Required Fix (Phase 4.5b):**

1. Add `ChoreManager.update_overdue_status(now)` - calls `mark_overdue()` which emits events
2. Add `ChoreManager.update_recurring_chores(now)` - calls `reset_chore()` which emits events
3. Modify Coordinator timer callbacks to delegate to Manager methods

**Tracking:** See [SCHEDULER_DELEGATION_PHASE4_5B_IN-PROCESS.md](SCHEDULER_DELEGATION_PHASE4_5B_IN-PROCESS.md)

**Risk Level:** 🔴 HIGH - Must complete before Phase 5

#### 2. `update_stats` Utilization: ✅ IMPLEMENTED (via `_update_chore_stats`)

**Finding:** The `_apply_effect()` method does NOT use `effect.update_stats` directly.

**Assessment:**

- ChoreManager implements stats tracking **differently** than planned:
  - Instead of inside `_apply_effect()`, stats are updated via `_update_chore_stats()` called after effects are applied
  - This is called at line 578 in `_approve_chore_locked()`
  - Pattern: `self._update_chore_stats(kid_id, "approved", points_to_award)`
- The `update_stats` flag in `TransitionEffect` is passed to **event payloads** for downstream consumers (Phase 5 gamification)
- Stats ARE being recorded correctly

**Evidence:**

```python
# Line 578 in chore_manager.py
self._update_chore_stats(kid_id, "approved", points_to_award)
```

**Risk Level:** 🟢 NONE - Implemented via different (but correct) pattern

#### 3. `_update_kid_chore_data` Duplication: ⚠️ PARTIAL CONCERN

**Finding:** Legacy `_update_kid_chore_data` (~270 lines) still exists in `coordinator_chore_operations.py`.

**Assessment:**

- ChoreManager does NOT call this legacy method
- ChoreManager has its own implementation:
  - `_apply_effect()` for state changes
  - `_update_chore_stats()` for statistics
  - Streak calculation in `_approve_chore_locked()`
- Legacy method is used by other parts of the system (sensors, diagnostics)

**Risk Level:** 🟡 MEDIUM - Code divergence possible but currently contained

**Recommendation:** Add deprecation comment to legacy method indicating ChoreManager owns approval/claim flows

---

### 🟢 Confirmed Working Features

| Feature                         | Status     | Evidence                                                                          |
| ------------------------------- | ---------- | --------------------------------------------------------------------------------- |
| Streak Calculation              | ✅ Working | `ChoreEngine.calculate_streak()` called from `_approve_chore_locked()` (line 552) |
| RecurrenceEngine Integration    | ✅ Working | `ChoreEngine.calculate_streak()` imports and uses `RecurrenceEngine` internally   |
| Event Payloads - `chore_labels` | ✅ Working | Present in claim, approve, disapprove events (8 occurrences)                      |
| Event Payloads - `update_stats` | ✅ Working | Set to `True` in all emitted events                                               |
| SHARED vs INDEPENDENT Logic     | ✅ Working | Fixed in Phase 4.5 remediation with `_all_kids_approved()`                        |
| `immediate_on_late`             | ✅ Working | Fixed in Phase 4.5 with `_is_approval_after_reset_boundary()`                     |

---

### 📝 Remaining Action Items (Optional Refinements)

These are NOT blockers but would improve code quality:

1. **Add Deprecation Notice to Legacy Method**

   ```python
   # In coordinator_chore_operations.py
   def _update_kid_chore_data(self, ...):
       """DEPRECATED: Approval/claim flows now handled by ChoreManager.

       This method is retained for:
       - Sensor state computation
       - Diagnostic data collection
       - Legacy timer callbacks

       Do not use for new approval/claim implementations.
       """
   ```

2. ~~**Consider Timer Callback Delegation** (Phase 6+)~~ → **PROMOTED TO PHASE 4.5b (REQUIRED)**
   - See [SCHEDULER_DELEGATION_PHASE4_5B_IN-PROCESS.md](SCHEDULER_DELEGATION_PHASE4_5B_IN-PROCESS.md)
   - Move `_process_recurring_chore_resets` body to `ChoreManager.update_recurring_chores()`
   - Move `_check_overdue_chores` body to `ChoreManager.update_overdue_status()`
   - **Now required before Phase 5** - events must emit for gamification

3. **Test Coverage for Timer Paths**
   - Add tests verifying timer callbacks execute Manager methods
   - Included in Phase 4.5b plan

---

### ⚠️ Phase 4 Close-Out Assessment (REVISED)

| Criterion                                        | Status     | Notes                                |
| ------------------------------------------------ | ---------- | ------------------------------------ |
| ChoreEngine exists with query/validation         | ✅ DONE    | 730 lines, pure Python               |
| ChoreManager implements claim/approve/disapprove | ✅ DONE    | 1360 lines, uses Engine              |
| Event payloads enriched                          | ✅ DONE    | `chore_labels`, `update_stats`, etc. |
| Streak calculation working                       | ✅ DONE    | Schedule-aware via RecurrenceEngine  |
| Multi-kid scenarios working                      | ✅ DONE    | SHARED/INDEPENDENT fixed in 4.5      |
| All 1045 tests pass                              | ✅ DONE    | Including 11 immediate_reset tests   |
| mypy zero errors                                 | ✅ DONE    | Clean type checking                  |
| Lint score ≥ 9.5/10                              | ✅ DONE    | `quick_lint.sh` passes               |
| **Timer callbacks emit events**                  | ❌ BLOCKED | **Requires Phase 4.5b**              |

**Verdict:** Phase 4 core functionality is **COMPLETE**, but **Phase 4.5b (Scheduler Delegation) is REQUIRED** before Phase 5 can begin. Time-based events (`CHORE_OVERDUE`, `CHORE_STATUS_RESET`) must emit through the Manager pattern.

---

> **Document Version:** 1.3
> **Last Updated:** 2026-01-25
> **Author:** Strategic Planning Agent
> **Revision Notes:**
>
> - v1.2: Added Appendix D with architectural review assessment
> - v1.3: Revised "Orphaned Scheduler" to BLOCKED, promoted to Phase 4.5b requirement
