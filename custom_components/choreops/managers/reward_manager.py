"""Reward Manager - Reward redemption lifecycle management.

This manager handles the complete reward lifecycle:
- Redeem: Assignee claims a reward (enters pending approval state)
- Approve: Approver approves pending reward (emits signal, EconomyManager deducts points)
- Disapprove: Approver rejects reward (resets to available)
- Undo: Assignee cancels own pending claim

ARCHITECTURE (v0.5.0+ Signal-First):
- RewardManager owns the entire reward workflow
- Point deductions via REWARD_APPROVED signal (EconomyManager listens)
- GamificationManager listens to POINTS_CHANGED (Event Bus coupling only)
- Coordinator provides data access and persistence

Event Flow:
    RewardManager.approve() -> emit(REWARD_APPROVED) -> EconomyManager.withdraw()
                                                               |
                                                        emit(POINTS_CHANGED)
                                                               |
                    GamificationManager (listener) <-----------+
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast
import uuid

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .. import const, data_builders as db
from ..helpers import entity_helpers as eh
from ..helpers.entity_helpers import remove_entities_by_item_id
from .base_manager import BaseManager
from .notification_manager import NotificationManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator
    from ..type_defs import RewardData, UserData


class RewardManager(BaseManager):
    """Manager for reward redemption lifecycle.

    Responsibilities:
    - Handle reward claims (redeem)
    - Process approvals/disapprovals
    - Track pending reward states
    - Emit signals for EconomyManager to handle point deductions
    - Send notifications via coordinator's notification routing

    NOT responsible for:
    - Point balance management (delegated to EconomyManager via signals)
    - Gamification checks (handled by GamificationManager via events)
    - Direct storage persistence (delegated to coordinator)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ChoreOpsDataCoordinator,
    ) -> None:
        """Initialize the RewardManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main ChoreOps coordinator
        """
        super().__init__(hass, coordinator)
        self._approval_locks: dict[str, asyncio.Lock] = {}

    async def async_setup(self) -> None:
        """Set up the RewardManager.

        Subscribes to BADGE_EARNED events to grant free rewards from badges.
        """
        # Phase 7: Signal-First Logic - listen for badge award manifests
        self.listen(
            const.SIGNAL_SUFFIX_BADGE_EARNED,
            self._on_badge_earned,
        )
        const.LOGGER.debug("RewardManager initialized for entry %s", self.entry_id)

    async def _on_badge_earned(self, payload: dict[str, Any]) -> None:
        """Handle badge earned event - grant free rewards from badge manifest.

        Phase 7 Signal-First Logic: Inventory Manager grants rewards from badges.
        Rewards from badges are free (cost_deducted=0).

        Args:
            payload: Award Manifest containing reward_ids list
        """
        assignee_id = payload.get("assignee_id")
        reward_ids = payload.get("reward_ids", [])
        badge_name = payload.get("badge_name", "Badge")

        if not assignee_id or not reward_ids:
            return

        for reward_id in reward_ids:
            if reward_id in self.coordinator.rewards_data:
                reward_name = str(
                    self.coordinator.rewards_data[reward_id].get(
                        const.DATA_REWARD_NAME, reward_id
                    )
                )
                try:
                    # Use the same approval flow as normal rewards, but force zero cost
                    # so badge-granted rewards stay free and listeners remain consistent.
                    await self.approve(
                        approver_name=badge_name,
                        assignee_id=assignee_id,
                        reward_id=reward_id,
                        cost_override=const.DEFAULT_ZERO,
                    )
                    const.LOGGER.info(
                        "RewardManager: Granted reward '%s' to assignee %s from badge '%s'",
                        reward_name,
                        assignee_id,
                        badge_name,
                    )
                except HomeAssistantError as err:
                    const.LOGGER.warning(
                        "RewardManager: Failed granting reward '%s' to assignee %s from badge '%s': %s",
                        reward_name,
                        assignee_id,
                        badge_name,
                        err,
                    )

    # =========================================================================
    # Lock Management
    # =========================================================================

    def _get_lock(self, operation: str, *identifiers: str) -> asyncio.Lock:
        """Get or create a lock for a specific operation and identifiers.

        This prevents race conditions when multiple requests try to modify
        the same reward state simultaneously (e.g., two approvers clicking approve).

        Args:
            operation: The operation name (e.g., "redeem", "approve")
            *identifiers: Unique identifiers for this lock (e.g., assignee_id, reward_id)

        Returns:
            asyncio.Lock for the specified operation+identifiers combination
        """
        lock_key = f"{operation}:{':'.join(identifiers)}"
        if lock_key not in self._approval_locks:
            self._approval_locks[lock_key] = asyncio.Lock()
        return self._approval_locks[lock_key]

    # =========================================================================
    # Data Access Helpers
    # =========================================================================

    def get_assignee_reward_data(
        self, assignee_id: str, reward_id: str, create: bool = False
    ) -> dict[str, Any]:
        """Get the reward data dict for a specific assignee+reward combination.

        Args:
            assignee_id: The assignee's internal ID
            reward_id: The reward's internal ID
            create: If True, create the entry if it doesn't exist

        Returns:
            Reward tracking dict or empty dict if not found and create=False
        """
        assignee_info: UserData = cast(
            "UserData", self.coordinator.assignees_data.get(assignee_id, {})
        )
        reward_data = assignee_info.setdefault(const.DATA_ASSIGNEE_REWARD_DATA, {})
        if create and reward_id not in reward_data:
            reward_data[reward_id] = {
                const.DATA_ASSIGNEE_REWARD_DATA_NAME: cast(
                    "RewardData", self.coordinator.rewards_data.get(reward_id, {})
                ).get(const.DATA_REWARD_NAME)
                or "",
                const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT: 0,
                const.DATA_ASSIGNEE_REWARD_DATA_LAST_CLAIMED: "",
                const.DATA_ASSIGNEE_REWARD_DATA_LAST_APPROVED: "",
                const.DATA_ASSIGNEE_REWARD_DATA_LAST_DISAPPROVED: "",
                # REMOVED v43: total_* fields - use periods.all_time.* instead
                # REMOVED v43: notification_ids - NotificationManager owns lifecycle
                const.DATA_ASSIGNEE_REWARD_DATA_PERIODS: {
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_DAILY: {},
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_WEEKLY: {},
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_MONTHLY: {},
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIODS_YEARLY: {},
                },
            }
        return cast("dict[str, Any]", reward_data.get(reward_id, {}))

    def _ensure_assignee_structures(
        self, assignee_id: str, reward_id: str | None = None
    ) -> None:
        """Landlord genesis - ensure assignee has reward_periods bucket and per-reward periods.

        Creates empty reward_periods dict if missing. StatisticsEngine (Tenant)
        creates and writes the period sub-keys (daily/weekly/etc.) on-demand.

        Optionally ensures per-reward periods structure exists if reward_id provided.
        This maintains consistency - RewardManager (Landlord) creates containers,
        StatisticsEngine (Tenant) populates data.

        This is the "Landlord" pattern - RewardManager owns assignee.reward_periods
        top-level dict, StatisticsEngine manages everything inside it.

        Args:
            assignee_id: Assignee UUID to ensure structure for
            reward_id: Optional reward UUID to ensure per-reward periods for
        """
        assignees = self.coordinator.users_data
        assignee_record = assignees.get(assignee_id)
        if assignee_record is None:
            return  # Assignee not found - caller should validate first

        assignee_info = cast("dict[str, Any]", assignee_record)

        # Assignee-level reward_periods bucket (v44+)
        if const.DATA_ASSIGNEE_REWARD_PERIODS not in assignee_info:
            assignee_info[
                const.DATA_ASSIGNEE_REWARD_PERIODS
            ] = {}  # Tenant populates sub-keys

        # Per-reward periods structure (if reward_id provided)
        if reward_id:
            assignee_reward_data = self.get_assignee_reward_data(
                assignee_id, reward_id, create=False
            )
            if (
                assignee_reward_data
                and const.DATA_ASSIGNEE_REWARD_DATA_PERIODS not in assignee_reward_data
            ):
                assignee_reward_data[
                    const.DATA_ASSIGNEE_REWARD_DATA_PERIODS
                ] = {}  # Tenant populates sub-keys

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Compute pending reward approvals dynamically from assignee reward data.

        Unlike chores (which allow only one pending claim at a time), rewards
        support multiple pending claims via the pending_count field.

        Returns:
            List of dicts with keys: assignee_id, reward_id, pending_count, timestamp
            One entry per assignee+reward combination with pending_count > 0.
        """
        pending: list[dict[str, Any]] = []
        for assignee_id, assignee_info in self.coordinator.assignees_data.items():
            reward_data = assignee_info.get(const.DATA_ASSIGNEE_REWARD_DATA, {})
            for reward_id, entry in reward_data.items():
                # Skip rewards that no longer exist
                if reward_id not in self.coordinator.rewards_data:
                    continue
                pending_count = entry.get(
                    const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0
                )
                if pending_count > 0:
                    pending.append(
                        {
                            const.DATA_ASSIGNEE_ID: assignee_id,
                            const.DATA_REWARD_ID: reward_id,
                            "pending_count": pending_count,
                            const.DATA_REWARD_TIMESTAMP: entry.get(
                                const.DATA_ASSIGNEE_REWARD_DATA_LAST_CLAIMED, ""
                            ),
                        }
                    )
        return pending

    # =========================================================================
    # Public API: Redeem
    # =========================================================================

    async def redeem(
        self, approver_name: str, assignee_id: str, reward_id: str
    ) -> None:
        """Assignee claims a reward with race condition protection.

        Uses asyncio.Lock to ensure only one redemption processes at a time
        per assignee+reward combination, preventing duplicate claims.

        Args:
            approver_name: Name of the assignee claiming (stored as approver_name for consistency)
            assignee_id: The assignee's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If assignee/reward not found or insufficient points
        """
        lock = self._get_lock("redeem", assignee_id, reward_id)
        async with lock:
            await self._redeem_locked(approver_name, assignee_id, reward_id)

    async def _redeem_locked(
        self, approver_name: str, assignee_id: str, reward_id: str
    ) -> None:
        """Internal redemption logic executed under lock protection.

        Args:
            approver_name: Name of the assignee claiming
            assignee_id: The assignee's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If assignee/reward not found or insufficient points
        """
        # Landlord genesis - ensure reward_periods and per-reward periods exist
        self._ensure_assignee_structures(assignee_id, reward_id)

        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        assignee_info: UserData | None = self.coordinator.assignees_data.get(
            assignee_id
        )
        if not assignee_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ASSIGNEE,
                    "name": assignee_id,
                },
            )

        cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_ZERO)
        if assignee_info[const.DATA_ASSIGNEE_POINTS] < cost:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                translation_placeholders={
                    "assignee": assignee_info[const.DATA_ASSIGNEE_NAME],
                    "current": str(assignee_info[const.DATA_ASSIGNEE_POINTS]),
                    "required": str(cost),
                },
            )

        # Update assignee reward data structure
        reward_entry = self.get_assignee_reward_data(
            assignee_id, reward_id, create=True
        )
        reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT] = (
            reward_entry.get(const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0) + 1
        )
        reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_LAST_CLAIMED] = (
            dt_util.utcnow().isoformat()
        )
        # REMOVED v43: total_claims increment - StatisticsManager writes to periods
        # Phase 4: Period updates handled by StatisticsManager._on_reward_claimed listener

        # REMOVED v43: _recalculate_stats_for_assignee() - reward_stats dict deleted

        # Generate a unique notification ID for signal payload
        # NotificationManager embeds this in action buttons for stale detection
        notif_id = uuid.uuid4().hex

        # Build notification metadata for event
        actions = NotificationManager.build_reward_actions(
            assignee_id, reward_id, notif_id
        )
        extra_data = NotificationManager.build_extra_data(
            assignee_id, reward_id=reward_id, notif_id=notif_id
        )

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Emit event for NotificationManager to send notifications
        # StatisticsManager._on_reward_claimed handles cache refresh and entity notification
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_CLAIMED,
            assignee_id=assignee_id,
            reward_id=reward_id,
            assignee_name=eh.get_assignee_name_by_id(self.coordinator, assignee_id)
            or "",
            reward_name=reward_info[const.DATA_REWARD_NAME],
            points=reward_info[const.DATA_REWARD_COST],
            actions=actions,
            extra_data=extra_data,
        )

    # =========================================================================
    # Public API: Approve
    # =========================================================================

    async def approve(
        self,
        approver_name: str,
        assignee_id: str,
        reward_id: str,
        notif_id: str | None = None,
        cost_override: float | None = None,
    ) -> None:
        """Approver approves the reward => deduct points via EconomyManager.

        Thread-safe implementation using asyncio.Lock to prevent race conditions
        when multiple approvers click approve simultaneously.

        Args:
            approver_name: Name of approving approver (for stale notification feedback).
            assignee_id: Internal ID of the assignee receiving the reward.
            reward_id: Internal ID of the reward being approved.
            notif_id: Optional notification ID to clear.
            cost_override: Optional cost to charge instead of the reward's stored cost.
                If None, uses reward's configured cost. Set to 0 for free grants.
        """
        lock = self._get_lock("approve", assignee_id, reward_id)
        async with lock:
            await self._approve_locked(
                approver_name, assignee_id, reward_id, notif_id, cost_override
            )

    async def _approve_locked(
        self,
        approver_name: str,
        assignee_id: str,
        reward_id: str,
        notif_id: str | None = None,
        cost_override: float | None = None,
    ) -> None:
        """Internal approval logic executed under lock protection."""
        # Landlord genesis - ensure reward_periods and per-reward periods exist
        self._ensure_assignee_structures(assignee_id, reward_id)

        assignee_info: UserData | None = self.coordinator.assignees_data.get(
            assignee_id
        )
        if not assignee_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ASSIGNEE,
                    "name": assignee_id,
                },
            )

        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        # Determine actual cost: use override if provided, else reward's stored cost
        if cost_override is not None:
            cost = cost_override
        else:
            cost = reward_info.get(const.DATA_REWARD_COST, const.DEFAULT_ZERO)

        # Get pending_count from assignee reward data (re-fetch inside lock for safety)
        reward_entry = self.get_assignee_reward_data(
            assignee_id, reward_id, create=False
        )
        pending_count = reward_entry.get(
            const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0
        )

        # Determine if this is a pending claim approval
        is_pending = pending_count > 0

        # Validate sufficient points
        if assignee_info[const.DATA_ASSIGNEE_POINTS] < cost:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                translation_placeholders={
                    "assignee": assignee_info[const.DATA_ASSIGNEE_NAME],
                    "current": str(assignee_info[const.DATA_ASSIGNEE_POINTS]),
                    "required": str(cost),
                },
            )

        # Track the reward grant
        self._grant_to_assignee(
            assignee_id=assignee_id,
            reward_id=reward_id,
            cost_deducted=cost,
            notif_id=notif_id,
            is_pending_claim=is_pending,
        )

        # REMOVED v43: _recalculate_stats_for_assignee() - reward_stats dict deleted

        # NOTE: Badge checks handled by GamificationManager via POINTS_CHANGED event

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Emit event - EconomyManager handles point withdrawal, NotificationManager sends notification
        # (Platinum Architecture: signal-first, no cross-manager writes)
        # StatisticsManager._on_reward_approved handles cache refresh and entity notification
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_APPROVED,
            assignee_id=assignee_id,
            reward_id=reward_id,
            reward_name=reward_info[const.DATA_REWARD_NAME],
            cost=cost,  # Reward cost approved/deducted
        )

    def _grant_to_assignee(
        self,
        assignee_id: str,
        reward_id: str,
        cost_deducted: float,
        notif_id: str | None = None,
        is_pending_claim: bool = False,
    ) -> None:
        """Track a reward grant for an assignee (unified logic for approvals and badge awards).

        This helper consolidates reward tracking. It updates all counters and timestamps
        but does NOT handle point deduction - that must be done by the caller before
        calling this method.

        Args:
            assignee_id: The internal ID of the assignee receiving the reward.
            reward_id: The internal ID of the reward being granted.
            cost_deducted: The actual points cost charged (0 for free grants).
            notif_id: Optional notification ID to remove from tracking list.
            is_pending_claim: True if approving a pending claim (decrements pending_count).
        """
        # Get or create reward tracking entry
        reward_entry = self.get_assignee_reward_data(
            assignee_id, reward_id, create=True
        )

        # Handle pending claim decrement if applicable
        if is_pending_claim:
            reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT] = max(
                0,
                reward_entry.get(const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0) - 1,
            )

        # Update timestamps
        reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_LAST_APPROVED] = (
            dt_util.utcnow().isoformat()
        )

        # If NOT from a pending claim, this is a direct approval or badge grant
        # Set last_claimed to match approval (combined claim+approve action)
        if not is_pending_claim:
            reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_LAST_CLAIMED] = (
                dt_util.utcnow().isoformat()
            )

        # REMOVED v43: total_approved, total_points_spent increments - StatisticsManager writes to periods
        # Phase 4: Period updates handled by StatisticsManager._on_reward_approved listener

        # Note: NotificationManager handles notification lifecycle via signal payloads.
        # notif_id is embedded in action buttons for stale detection, no storage needed.

    # =========================================================================
    # Public API: Disapprove
    # =========================================================================

    async def disapprove(
        self, approver_name: str, assignee_id: str, reward_id: str
    ) -> None:
        """Disapprove a reward with race condition protection.

        Uses asyncio.Lock to ensure only one disapproval processes at a time
        per assignee+reward combination.

        Args:
            approver_name: Name of disapproving approver (for audit/notifications)
            assignee_id: The assignee's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If assignee or reward not found
        """
        lock = self._get_lock("disapprove", assignee_id, reward_id)
        async with lock:
            await self._disapprove_locked(approver_name, assignee_id, reward_id)

    async def _disapprove_locked(
        self, approver_name: str, assignee_id: str, reward_id: str
    ) -> None:
        """Internal disapproval logic executed under lock protection."""
        # Landlord genesis - ensure reward_periods and per-reward periods exist
        self._ensure_assignee_structures(assignee_id, reward_id)

        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        assignee_info: UserData | None = self.coordinator.assignees_data.get(
            assignee_id
        )

        # Update assignee reward data structure
        if assignee_info:
            reward_entry = self.get_assignee_reward_data(
                assignee_id, reward_id, create=False
            )
            if reward_entry:
                reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT] = max(
                    0,
                    reward_entry.get(const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0)
                    - 1,
                )
                reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_LAST_DISAPPROVED] = (
                    dt_util.utcnow().isoformat()
                )
                # REMOVED v43: total_disapproved increment - StatisticsManager writes to periods
                # Phase 4: Period updates handled by StatisticsManager._on_reward_disapproved listener

            # REMOVED v43: _recalculate_stats_for_assignee() - reward_stats dict deleted
            # StatisticsManager derives stats from reward_periods on-demand

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Emit event for NotificationManager to send notification and clear approver claim
        # StatisticsManager._on_reward_disapproved handles cache refresh and entity notification
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_DISAPPROVED,
            assignee_id=assignee_id,
            reward_id=reward_id,
            reward_name=reward_info[const.DATA_REWARD_NAME],
        )

    # =========================================================================
    # Public API: Undo Claim
    # =========================================================================

    async def undo_claim(self, assignee_id: str, reward_id: str) -> None:
        """Allow assignee to undo their own reward claim (no stat tracking).

        This method provides a way for assignees to remove their pending reward claim
        without it counting as a disapproval. Unlike disapprove:
        - Does NOT track disapproval stats (no last_disapproved, no counters)
        - Does NOT send notifications (silent undo)
        - Only decrements pending_count

        Args:
            assignee_id: The assignee's internal ID
            reward_id: The reward's internal ID

        Raises:
            HomeAssistantError: If assignee or reward not found
        """
        reward_info: RewardData | None = self.coordinator.rewards_data.get(reward_id)
        if not reward_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        assignee_info: UserData | None = self.coordinator.assignees_data.get(
            assignee_id
        )
        if not assignee_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ASSIGNEE,
                    "name": assignee_id,
                },
            )

        # Update assignee reward data structure - only decrement pending_count
        # Do NOT update last_disapproved, total_disapproved, or period counters
        reward_entry = self.get_assignee_reward_data(
            assignee_id, reward_id, create=False
        )
        if reward_entry:
            reward_entry[const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT] = max(
                0,
                reward_entry.get(const.DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0) - 1,
            )

        # REMOVED v43: _recalculate_stats_for_assignee() - reward_stats dict deleted

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

        # Emit event for NotificationManager to clear approver claim notifications
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_CLAIM_UNDONE,
            assignee_id=assignee_id,
            reward_id=reward_id,
        )

    # =========================================================================
    # Public API: Reset
    # =========================================================================

    async def reset_rewards(
        self, assignee_id: str | None = None, reward_id: str | None = None
    ) -> None:
        """Reset rewards based on provided assignee_id and reward_id.

        Args:
            assignee_id: Optional assignee ID to reset rewards for
            reward_id: Optional reward ID to reset

        Behavior:
        - assignee_id + reward_id: Reset specific reward for specific assignee
        - reward_id only: Reset that reward for all assignees
        - assignee_id only: Reset all rewards for that assignee
        - Neither: Reset all rewards for all assignees
        """
        if reward_id and assignee_id:
            # Reset a specific reward for a specific assignee
            assignee_info: UserData | None = self.coordinator.assignees_data.get(
                assignee_id
            )
            if not assignee_info:
                const.LOGGER.error(
                    "ERROR: Reset Rewards - Assignee ID '%s' not found", assignee_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_ASSIGNEE,
                        "name": assignee_id,
                    },
                )

            # Clear reward_data entry for this reward
            reward_data = assignee_info.get(const.DATA_ASSIGNEE_REWARD_DATA, {})
            reward_data.pop(reward_id, None)

        elif reward_id:
            # Reset a specific reward for all assignees
            found = False
            for assignee_info_loop in self.coordinator.assignees_data.values():
                reward_data = assignee_info_loop.get(
                    const.DATA_ASSIGNEE_REWARD_DATA, {}
                )
                if reward_id in reward_data:
                    found = True
                    reward_data.pop(reward_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Rewards - Reward '%s' not found in any assignee data",
                    reward_id,
                )

        elif assignee_id:
            # Reset all rewards for a specific assignee
            assignee_info_elif: UserData | None = self.coordinator.assignees_data.get(
                assignee_id
            )
            if not assignee_info_elif:
                const.LOGGER.error(
                    "ERROR: Reset Rewards - Assignee ID '%s' not found", assignee_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_ASSIGNEE,
                        "name": assignee_id,
                    },
                )

            # Clear all reward_data for this assignee
            if const.DATA_ASSIGNEE_REWARD_DATA in assignee_info_elif:
                assignee_info_elif[const.DATA_ASSIGNEE_REWARD_DATA].clear()

        else:
            # Reset all rewards for all assignees
            const.LOGGER.info(
                "INFO: Reset Rewards - Resetting all rewards for all assignees"
            )
            for assignee_info in self.coordinator.assignees_data.values():
                # Clear all reward_data for this assignee
                if const.DATA_ASSIGNEE_REWARD_DATA in assignee_info:
                    assignee_info[const.DATA_ASSIGNEE_REWARD_DATA].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Rewards completed - Assignee ID '%s', Reward ID '%s'",
            assignee_id,
            reward_id,
        )

        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

    # =========================================================================
    # CRUD METHODS (Manager-owned create/update/delete)
    # =========================================================================
    # These methods own the write operations for reward entities.
    # Called by options_flow.py and services.py - they must NOT write directly.

    def create_reward(
        self, user_input: dict[str, Any], *, immediate_persist: bool = False
    ) -> dict[str, Any]:
        """Create a new reward in storage.

        Args:
            user_input: Reward data with DATA_* keys.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Complete RewardData dict ready for use.

        Emits:
            SIGNAL_SUFFIX_REWARD_CREATED with reward_id and reward_name.
        """
        # Build complete reward data structure
        reward_data = dict(db.build_reward(user_input))
        internal_id = str(reward_data[const.DATA_REWARD_INTERNAL_ID])
        reward_name = str(reward_data.get(const.DATA_REWARD_NAME, ""))

        # Store in coordinator data
        self.coordinator._data[const.DATA_REWARDS][internal_id] = reward_data
        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_CREATED,
            reward_id=internal_id,
            reward_name=reward_name,
        )

        const.LOGGER.info(
            "Created reward '%s' (ID: %s)",
            reward_name,
            internal_id,
        )

        return reward_data

    def update_reward(
        self,
        reward_id: str,
        updates: dict[str, Any],
        *,
        immediate_persist: bool = False,
    ) -> dict[str, Any]:
        """Update an existing reward in storage.

        Args:
            reward_id: Internal UUID of the reward to update.
            updates: Partial reward data with DATA_* keys to merge.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Updated RewardData dict.

        Raises:
            HomeAssistantError: If reward not found.

        Emits:
            SIGNAL_SUFFIX_REWARD_UPDATED with reward_id and reward_name.
        """
        rewards_data = self.coordinator._data.get(const.DATA_REWARDS, {})
        if reward_id not in rewards_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        existing = rewards_data[reward_id]
        # Build updated reward (merge existing with updates)
        updated_reward = dict(db.build_reward(updates, existing=existing))

        # Store updated reward
        self.coordinator._data[const.DATA_REWARDS][reward_id] = updated_reward
        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        reward_name = str(updated_reward.get(const.DATA_REWARD_NAME, ""))

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_UPDATED,
            reward_id=reward_id,
            reward_name=reward_name,
        )

        const.LOGGER.debug(
            "Updated reward '%s' (ID: %s)",
            reward_name,
            reward_id,
        )

        return updated_reward

    def delete_reward(self, reward_id: str, *, immediate_persist: bool = False) -> None:
        """Delete a reward from storage and cleanup references.

        Args:
            reward_id: Internal UUID of the reward to delete.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Raises:
            HomeAssistantError: If reward not found.

        Emits:
            SIGNAL_SUFFIX_REWARD_DELETED with reward_id and reward_name.
        """
        rewards_data = self.coordinator._data.get(const.DATA_REWARDS, {})
        if reward_id not in rewards_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_id,
                },
            )

        reward_name = rewards_data[reward_id].get(const.DATA_REWARD_NAME, reward_id)

        # Delete from storage
        del self.coordinator._data[const.DATA_REWARDS][reward_id]

        # Remove HA entities
        remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            reward_id,
        )

        # Clean own domain: remove deleted reward refs from assignee reward data
        valid_reward_ids = set(self.coordinator.rewards_data.keys())
        for assignee_data in self.coordinator.assignees_data.values():
            reward_data = assignee_data.get(const.DATA_ASSIGNEE_REWARD_DATA, {})
            orphaned = [rid for rid in reward_data if rid not in valid_reward_ids]
            for rid in orphaned:
                del reward_data[rid]
                const.LOGGER.debug(
                    "Removed orphaned reward '%s' from assignee reward data", rid
                )

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_DELETED,
            reward_id=reward_id,
            reward_name=reward_name,
        )

        const.LOGGER.info(
            "Deleted reward '%s' (ID: %s)",
            reward_name,
            reward_id,
        )

    # =========================================================================
    # DATA RESET - Transactional Data Reset for Rewards Domain
    # =========================================================================

    async def data_reset_rewards(
        self,
        scope: str,
        assignee_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for rewards domain.

        Clears per-assignee reward_data tracking (claim counts, timestamps)
        while preserving reward definitions and configured values.

        Args:
            scope: Reset scope (global, assignee, item_type, item)
            assignee_id: Target assignee ID for assignee scope (optional)
            item_id: Target reward ID for item scope (optional)

        Emits:
            SIGNAL_SUFFIX_REWARD_DATA_RESET_COMPLETE with scope, assignee_id, item_id
        """
        const.LOGGER.info(
            "Data reset: rewards domain - scope=%s, assignee_id=%s, item_id=%s",
            scope,
            assignee_id,
            item_id,
        )

        assignees_data = self.coordinator.users_data

        # Determine which assignees to process
        if assignee_id:
            assignee_ids = [assignee_id] if assignee_id in assignees_data else []
        else:
            assignee_ids = list(assignees_data.keys())

        for loop_assignee_id in assignee_ids:
            assignee_info = assignees_data.get(loop_assignee_id)
            if not assignee_info:
                continue

            # Reset reward_data tracking
            reward_data = assignee_info.get(const.DATA_ASSIGNEE_REWARD_DATA, {})
            if item_id:
                # Item scope - only clear specific reward tracking
                reward_data.pop(item_id, None)
            else:
                # Clear all reward tracking
                reward_data.clear()

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist()
        self.coordinator.async_set_updated_data(self.coordinator._data)

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_REWARD_DATA_RESET_COMPLETE,
            scope=scope,
            assignee_id=assignee_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: rewards domain complete - %d assignees affected",
            len(assignee_ids),
        )
