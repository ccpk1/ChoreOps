"""Economy Manager - Point transactions and ledger management.

This manager handles all point-related operations:
- Deposits (adding points)
- Withdrawals (removing points with NSF checks)
- Ledger management (transaction history)
- Penalty application (point deductions)
- Bonus application (point additions)
- Event emission for point changes

ARCHITECTURE (v0.5.0+ "Clean Break"):
- EconomyManager = "The Bank" (STATEFUL point operations)
- EconomyEngine = Pure math and ledger logic (STATELESS)
- GamificationManager listens to POINTS_CHANGED events (Event Bus coupling)

Point transactions emit POINTS_CHANGED events which trigger GamificationManager
to evaluate badges/achievements/challenges automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError

from .. import const, data_builders as db
from ..engines.economy_engine import EconomyEngine, InsufficientFundsError
from ..helpers.entity_helpers import remove_entities_by_item_id
from ..utils.math_utils import parse_points_adjust_values
from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import KidData, LedgerEntry


# Re-export exception for external use
__all__ = ["EconomyManager", "InsufficientFundsError"]


class EconomyManager(BaseManager):
    """Manager for all point transactions and ledger operations.

    Responsibilities:
    - Execute deposits and withdrawals
    - Maintain transaction ledger per kid
    - Emit SIGNAL_SUFFIX_POINTS_CHANGED events
    - Prune ledger to prevent storage bloat

    NOT responsible for:
    - Gamification checks (handled by Coordinator in Phase 3)
    - Notifications (handled by Coordinator calling NotificationManager)
    - Period-based statistics (handled by StatisticsEngine via Coordinator)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize the EconomyManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main KidsChores coordinator
        """
        super().__init__(hass, coordinator)
        self._coordinator = coordinator

    @property
    def adjustment_deltas(self) -> list[float]:
        """Get the authorized list of point adjustment values.

        Returns normalized float values from config, with defaults if not configured.
        Values are rounded to DATA_FLOAT_PRECISION for stable unique_id generation.

        Returns:
            List of adjustment delta floats (e.g., [1.0, -1.0, 5.0, -5.0])
        """
        raw = self.coordinator.config_entry.options.get(const.CONF_POINTS_ADJUST_VALUES)
        return parse_points_adjust_values(raw)

    async def async_setup(self) -> None:
        """Set up the EconomyManager.

        Subscribe to gamification award events to handle point deposits.
        This decouples GamificationManager from direct deposit calls.
        """
        # Listen for gamification award events (Phase 7.2 - Event-Driven Awards)
        self.listen(
            const.SIGNAL_SUFFIX_BADGE_EARNED,
            self._on_badge_earned,
        )
        self.listen(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_EARNED,
            self._on_achievement_earned,
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHALLENGE_COMPLETED,
            self._on_challenge_completed,
        )
        # Listen for chore workflow events (Platinum Architecture - Signal-First)
        # EconomyManager handles point transactions when chores are approved/undone
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_APPROVED,
            self._on_chore_approved,
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_UNDONE,
            self._on_chore_undone,
        )
        # Listen for reward workflow events (Platinum Architecture - Signal-First)
        # EconomyManager handles point withdrawals when rewards are approved
        self.listen(
            const.SIGNAL_SUFFIX_REWARD_APPROVED,
            self._on_reward_approved,
        )
        # Listen for multiplier change requests (Phase 3B Landlord/Tenant ownership)
        # EconomyManager owns all kid point data - GamificationManager emits requests
        self.listen(
            const.SIGNAL_SUFFIX_POINTS_MULTIPLIER_CHANGE_REQUESTED,
            self._on_points_multiplier_change_requested,
        )

    def _on_points_multiplier_change_requested(self, payload: dict[str, Any]) -> None:
        """Handle points multiplier change request - EconomyManager owns multiplier writes.

        Phase 3B Landlord/Tenant: GamificationManager calculates multipliers,
        but EconomyManager (the Landlord) performs the actual write to kid data.

        Args:
            payload: Event data containing:
                - kid_id: Kid's internal ID
                - multiplier: New multiplier value
                - reference_id: Optional reference (badge_id, etc.) for audit
        """
        kid_id = payload.get("kid_id")
        multiplier = payload.get("multiplier")
        reference_id = payload.get("reference_id")

        if not kid_id or multiplier is None:
            const.LOGGER.warning(
                "EconomyManager: Invalid multiplier change request - kid_id=%s, multiplier=%s",
                kid_id,
                multiplier,
            )
            return

        self._update_multiplier(kid_id, float(multiplier), reference_id)

    async def _on_badge_earned(self, payload: dict[str, Any]) -> None:
        """Handle badge earned event - process full Award Manifest.

        Phase 7 Signal-First Logic: The "Banker" (EconomyManager) owns all
        currency-related awards. GamificationManager emits the Award Manifest,
        and we handle: points, multiplier, bonuses, penalties.

        Args:
            payload: Award Manifest containing:
                - kid_id, badge_id, badge_name (identifiers)
                - points: float (deposit amount)
                - multiplier: float | None (currency rule update)
                - bonus_ids: list[str] (bonus applications)
                - penalty_ids: list[str] (penalty applications)
        """
        kid_id = payload.get("kid_id")
        badge_id = payload.get("badge_id")
        badge_name = payload.get("badge_name")
        if not kid_id:
            return

        # 1. Points - deposit to kid's balance
        points = payload.get("points", 0.0)
        if points > 0:
            await self.deposit(
                kid_id,
                points,
                source=const.POINTS_SOURCE_BADGES,
                reference_id=badge_id,
                item_name=badge_name,
            )

        # 2. Multiplier - Banker owns currency rules
        multiplier = payload.get("multiplier")
        if multiplier is not None:
            kid_info = self._get_kid(kid_id)
            if kid_info:
                old_multiplier = float(
                    kid_info.get(
                        const.DATA_KID_POINTS_MULTIPLIER,
                        const.DEFAULT_KID_POINTS_MULTIPLIER,
                    )
                )
                new_multiplier = float(multiplier)
                self.emit(
                    const.SIGNAL_SUFFIX_POINTS_MULTIPLIER_CHANGE_REQUESTED,
                    kid_id=kid_id,
                    multiplier=new_multiplier,
                    old_multiplier=old_multiplier,
                    new_multiplier=new_multiplier,
                    reference_id=badge_id,
                )

        # 3. Bonuses - apply each bonus
        bonus_ids = payload.get("bonus_ids", [])
        for bonus_id in bonus_ids:
            if bonus_id in self._coordinator.bonuses_data:
                await self.apply_bonus(
                    "Badge Award",
                    kid_id,
                    bonus_id,
                )

        # 4. Penalties - apply each penalty
        penalty_ids = payload.get("penalty_ids", [])
        for penalty_id in penalty_ids:
            if penalty_id in self._coordinator.penalties_data:
                await self.apply_penalty(
                    "Badge Award",
                    kid_id,
                    penalty_id,
                )

    def _update_multiplier(
        self, kid_id: str, multiplier: float, reference_id: str | None = None
    ) -> None:
        """Update kid's points multiplier (Banker owns currency rules).

        Args:
            kid_id: The kid's internal ID
            multiplier: New multiplier value
            reference_id: Optional reference (badge_id, etc.) for audit
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        old_multiplier = kid_info.get(
            const.DATA_KID_POINTS_MULTIPLIER, const.DEFAULT_KID_POINTS_MULTIPLIER
        )
        if multiplier > const.DEFAULT_ZERO:
            kid_info[const.DATA_KID_POINTS_MULTIPLIER] = multiplier
            const.LOGGER.info(
                "EconomyManager: Updated multiplier for kid %s: %.2f -> %.2f (ref: %s)",
                kid_id,
                old_multiplier,
                multiplier,
                reference_id or "manual",
            )
            self._coordinator._persist_and_update()

    async def _on_achievement_earned(self, payload: dict[str, Any]) -> None:
        """Handle achievement earned event - deposit award points.

        Args:
            payload: Event data containing kid_id, achievement_id, achievement_points
        """
        kid_id = payload.get("kid_id")
        achievement_id = payload.get("achievement_id")
        achievement_points = payload.get("achievement_points", 0.0)

        if achievement_points > 0 and kid_id:
            await self.deposit(
                kid_id,
                achievement_points,
                source=const.POINTS_SOURCE_ACHIEVEMENTS,
                reference_id=achievement_id,
            )

    async def _on_challenge_completed(self, payload: dict[str, Any]) -> None:
        """Handle challenge completed event - deposit award points.

        Args:
            payload: Event data containing kid_id, challenge_id, challenge_points
        """
        kid_id = payload.get("kid_id")
        challenge_id = payload.get("challenge_id")
        challenge_points = payload.get("challenge_points", 0.0)

        if challenge_points > 0 and kid_id:
            await self.deposit(
                kid_id,
                challenge_points,
                source=const.POINTS_SOURCE_CHALLENGES,
                reference_id=challenge_id,
            )

    async def _on_chore_approved(self, payload: dict[str, Any]) -> None:
        """Handle chore approved event - deposit points to kid's balance.

        Follows Platinum Architecture (Choreography): EconomyManager reacts to
        CHORE_APPROVED signal and handles its own domain (point transactions).
        ChoreManager no longer calls deposit() directly.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal UUID
                - chore_id: The chore's internal UUID
                - base_points: Raw points before multiplier
                - apply_multiplier: Whether to apply kid's multiplier
        """
        kid_id = payload.get("kid_id")
        chore_id = payload.get("chore_id")
        base_points = payload.get("base_points", 0.0)
        apply_multiplier = payload.get("apply_multiplier", True)
        chore_name = payload.get("chore_name")

        if base_points > 0 and kid_id:
            await self.deposit(
                kid_id=kid_id,
                amount=base_points,
                source=const.POINTS_SOURCE_CHORES,
                reference_id=chore_id,
                item_name=chore_name,
                apply_multiplier=apply_multiplier,
            )

    async def _on_reward_approved(self, payload: dict[str, Any]) -> None:
        """Handle reward approved event - withdraw points from kid's balance.

        Follows Platinum Architecture (Choreography): EconomyManager reacts to
        REWARD_APPROVED signal and handles its own domain (point transactions).
        RewardManager no longer calls withdraw() directly.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal UUID
                - reward_id: The reward's internal UUID
                - cost: Points to deduct
        """
        kid_id = payload.get("kid_id")
        reward_id = payload.get("reward_id")
        cost = payload.get("cost", 0.0)
        reward_name = payload.get("reward_name")

        if cost > 0 and kid_id:
            await self.withdraw(
                kid_id=kid_id,
                amount=cost,
                source=const.POINTS_SOURCE_REWARDS,
                reference_id=reward_id,
                item_name=reward_name,
                allow_negative=False,  # Kids must afford rewards
            )

    async def _on_chore_undone(self, payload: dict[str, Any]) -> None:
        """Handle chore undone event - withdraw points from kid's balance.

        Follows Platinum Architecture: EconomyManager handles point reclamation
        when a chore approval is undone. NSF (insufficient funds) is handled
        gracefully - logged but doesn't fail the undo operation.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal UUID
                - chore_id: The chore's internal UUID
                - points_to_reclaim: Amount to withdraw
        """
        kid_id = payload.get("kid_id")
        chore_id = payload.get("chore_id")
        points_to_reclaim = payload.get("points_to_reclaim", 0.0)

        if points_to_reclaim > 0 and kid_id:
            await self.withdraw(
                kid_id=kid_id,
                amount=points_to_reclaim,
                source=const.POINTS_SOURCE_OTHER,
                reference_id=chore_id,
                # allow_negative=True by default - undo can go negative
            )

    def _get_kid(self, kid_id: str) -> KidData | None:
        """Get kid data by ID.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            KidData dict or None if not found
        """
        return self._coordinator.kids_data.get(kid_id)

    def _ensure_ledger(self, kid_data: KidData) -> list[LedgerEntry]:
        """Ensure kid has a ledger list, creating if needed.

        Args:
            kid_data: The kid's data dict

        Returns:
            The ledger list (possibly empty but never None)
        """
        if const.DATA_KID_LEDGER not in kid_data:
            kid_data[const.DATA_KID_LEDGER] = []  # type: ignore[typeddict-unknown-key]
        return kid_data[const.DATA_KID_LEDGER]  # type: ignore[typeddict-item]

    def _ensure_point_structures(self, kid_data: KidData) -> None:
        """Ensure point_periods structure exists (Landlord duty).

        Phase 3B Landlord/Tenant: EconomyManager owns this structure.
        Creates it on-demand before first transaction, not at kid genesis.
        StatisticsManager (tenant) writes to sub-keys but never creates top-level.

        Args:
            kid_data: The kid's data dict (modified in-place)
        """
        # point_periods: Flat period buckets container (v43+)
        # StatisticsManager (tenant) creates and writes the period sub-keys
        if const.DATA_KID_POINT_PERIODS not in kid_data:
            kid_data[const.DATA_KID_POINT_PERIODS] = {}

    def get_balance(self, kid_id: str) -> float:
        """Get current point balance for a kid.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            Current point balance, or 0.0 if kid not found
        """
        kid = self._get_kid(kid_id)
        if not kid:
            const.LOGGER.warning(
                "EconomyManager.get_balance: Kid ID '%s' not found",
                kid_id,
            )
            return 0.0

        try:
            return float(kid.get(const.DATA_KID_POINTS, 0.0))
        except (ValueError, TypeError):
            return 0.0

    def get_history(
        self,
        kid_id: str,
        limit: int = const.DEFAULT_LEDGER_MAX_ENTRIES,
    ) -> list[LedgerEntry]:
        """Get recent transaction history for a kid.

        Args:
            kid_id: The internal UUID of the kid
            limit: Maximum entries to return (newest first)

        Returns:
            List of LedgerEntry dicts (newest last in storage, but we could reverse)
        """
        kid = self._get_kid(kid_id)
        if not kid:
            return []

        ledger = kid.get(const.DATA_KID_LEDGER, [])
        if not isinstance(ledger, list):
            return []

        # Return most recent entries (end of list = newest)
        return ledger[-limit:] if len(ledger) > limit else ledger

    async def deposit(
        self,
        kid_id: str,
        amount: float,
        *,
        source: str,
        reference_id: str | None = None,
        item_name: str | None = None,
        apply_multiplier: bool = False,
    ) -> float:
        """Add points to a kid's balance.

        Args:
            kid_id: The internal UUID of the kid
            amount: Amount to add (must be positive)
            source: Transaction source (POINTS_SOURCE_CHORES, POINTS_SOURCE_BONUSES, etc.)
            reference_id: Optional related entity ID (chore_id, etc.)
            item_name: Optional human-readable name of related item (Phase 4C)
            apply_multiplier: If True, apply kid's points_multiplier

        Returns:
            New balance after deposit

        Raises:
            ValueError: If kid not found or amount is negative
        """
        kid = self._get_kid(kid_id)
        if not kid:
            const.LOGGER.error(
                "EconomyManager.deposit: Kid ID '%s' not found",
                kid_id,
            )
            raise ValueError(f"Kid not found: {kid_id}")

        if amount < 0:
            raise ValueError(f"Deposit amount must be positive, got {amount}")

        # Apply multiplier if requested (e.g., for chore approvals)
        actual_amount = amount
        if apply_multiplier:
            multiplier = float(kid.get(const.DATA_KID_POINTS_MULTIPLIER, 1.0))
            actual_amount = EconomyEngine.calculate_with_multiplier(amount, multiplier)

        # Get current balance
        current_balance = self.get_balance(kid_id)

        # Create ledger entry
        entry = EconomyEngine.create_ledger_entry(
            current_balance=current_balance,
            delta=actual_amount,
            source=source,
            reference_id=reference_id,
            item_name=item_name,
        )

        # Update balance
        new_balance = EconomyEngine.calculate_new_balance(
            current_balance, actual_amount
        )
        kid[const.DATA_KID_POINTS] = new_balance

        # Append to ledger and prune
        ledger = self._ensure_ledger(kid)
        ledger.append(entry)
        retention_days = int(
            self._coordinator.statistics_manager.get_retention_config().get(
                const.PERIOD_DAILY,
                const.DEFAULT_RETENTION_DAILY,
            )
        )
        EconomyEngine.prune_ledger(
            ledger,
            max_entries=const.DEFAULT_LEDGER_MAX_ENTRIES,
            max_age_days=retention_days,
        )

        # Ensure point structures exist (Landlord duty) before emitting signal
        # StatisticsManager (tenant) expects these to exist when it receives the event
        self._ensure_point_structures(kid)

        # Emit event for listeners (StatisticsManager will handle stats)
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_CHANGED,
            kid_id=kid_id,
            old_balance=current_balance,
            new_balance=new_balance,
            delta=actual_amount,
            source=source,
            reference_id=reference_id,
        )

        const.LOGGER.debug(
            "EconomyManager.deposit: kid=%s, amount=%.2f (actual=%.2f), "
            "old=%.2f, new=%.2f, source=%s",
            kid_id,
            amount,
            actual_amount,
            current_balance,
            new_balance,
            source,
        )

        return new_balance

    async def withdraw(
        self,
        kid_id: str,
        amount: float,
        *,
        source: str,
        reference_id: str | None = None,
        item_name: str | None = None,
        allow_negative: bool = True,
    ) -> float:
        """Remove points from a kid's balance.

        Args:
            kid_id: The internal UUID of the kid
            amount: Amount to remove (must be positive - will be negated internally)
            source: Transaction source (POINTS_SOURCE_REWARDS, POINTS_SOURCE_PENALTIES, etc.)
            reference_id: Optional related entity ID (reward_id, etc.)
            item_name: Optional human-readable name of related item (Phase 4C)
            allow_negative: If True (default), allows balance to go negative (parent actions).
                           If False, raises InsufficientFundsError on NSF (reward claims).

        Returns:
            New balance after withdrawal

        Raises:
            ValueError: If kid not found or amount is negative
            InsufficientFundsError: If allow_negative=False and balance < amount (NSF)
        """
        kid = self._get_kid(kid_id)
        if not kid:
            const.LOGGER.error(
                "EconomyManager.withdraw: Kid ID '%s' not found",
                kid_id,
            )
            raise ValueError(f"Kid not found: {kid_id}")

        if amount < 0:
            raise ValueError(f"Withdraw amount must be positive, got {amount}")

        # Get current balance
        current_balance = self.get_balance(kid_id)

        # NSF check - only enforced when allow_negative=False (e.g., reward claims)
        if not allow_negative and not EconomyEngine.validate_sufficient_funds(
            current_balance, amount
        ):
            const.LOGGER.warning(
                "EconomyManager.withdraw: NSF for kid=%s, balance=%.2f, requested=%.2f",
                kid_id,
                current_balance,
                amount,
            )
            raise InsufficientFundsError(
                kid_id=kid_id,
                current_balance=current_balance,
                requested_amount=amount,
            )

        # Create ledger entry (negative delta for withdrawal)
        entry = EconomyEngine.create_ledger_entry(
            current_balance=current_balance,
            delta=-amount,  # Negative for withdrawal
            source=source,
            reference_id=reference_id,
            item_name=item_name,
        )

        # Update balance
        new_balance = EconomyEngine.calculate_new_balance(current_balance, -amount)
        kid[const.DATA_KID_POINTS] = new_balance

        # Append to ledger and prune
        ledger = self._ensure_ledger(kid)
        ledger.append(entry)
        retention_days = int(
            self._coordinator.statistics_manager.get_retention_config().get(
                const.PERIOD_DAILY,
                const.DEFAULT_RETENTION_DAILY,
            )
        )
        EconomyEngine.prune_ledger(
            ledger,
            max_entries=const.DEFAULT_LEDGER_MAX_ENTRIES,
            max_age_days=retention_days,
        )

        # Ensure point structures exist (Landlord duty) before emitting signal
        # StatisticsManager (tenant) expects these to exist when it receives the event
        self._ensure_point_structures(kid)

        # Emit event for listeners (StatisticsManager will handle stats)
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_CHANGED,
            kid_id=kid_id,
            old_balance=current_balance,
            new_balance=new_balance,
            delta=-amount,
            source=source,
            reference_id=reference_id,
        )

        const.LOGGER.debug(
            "EconomyManager.withdraw: kid=%s, amount=%.2f, old=%.2f, new=%.2f, source=%s",
            kid_id,
            amount,
            current_balance,
            new_balance,
            source,
        )

        return new_balance

    # =========================================================================
    # Penalty Operations
    # =========================================================================

    async def apply_penalty(
        self, parent_name: str, kid_id: str, penalty_id: str
    ) -> float:
        """Apply penalty to kid - deducts points via withdraw().

        This method:
        1. Validates penalty and kid exist
        2. Withdraws points (emits POINTS_CHANGED)
        3. Updates penalty tracking counter
        4. Sends notification to kid
        5. Persists changes

        Args:
            parent_name: Name of parent applying penalty (for audit trail)
            kid_id: The kid's internal ID
            penalty_id: The penalty's internal ID

        Returns:
            New balance after penalty

        Raises:
            HomeAssistantError: If kid or penalty not found
        """
        penalty_info = self._coordinator.penalties_data.get(penalty_id)
        if not penalty_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PENALTY,
                    "name": penalty_id,
                },
            )

        kid_info: KidData | None = self._get_kid(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        penalty_pts = penalty_info.get(const.DATA_PENALTY_POINTS, const.DEFAULT_ZERO)
        penalty_name = penalty_info.get(const.DATA_PENALTY_NAME, "")

        # Use withdraw() with allow_negative=True (default) for penalties
        # Parent authority actions can take balance negative
        new_balance = await self.withdraw(
            kid_id=kid_id,
            amount=abs(penalty_pts),
            source=const.POINTS_SOURCE_PENALTIES,
            reference_id=penalty_id,
            item_name=penalty_name,
            # allow_negative=True by default
        )

        # Landlord: Ensure penalty_applies entry exists with periods structure
        # StatisticsEngine (via StatisticsManager) creates period buckets (daily/weekly/etc)
        # on-demand via record_transaction() - matching the points pattern
        penalty_applies = kid_info.setdefault(const.DATA_KID_PENALTY_APPLIES, {})
        if penalty_id not in penalty_applies:
            penalty_applies[penalty_id] = {
                const.DATA_KID_PENALTY_PERIODS: {},
            }

        const.LOGGER.debug(
            "EconomyManager.apply_penalty: kid=%s, penalty=%s, pts=%.2f, new_balance=%.2f",
            kid_id,
            penalty_id,
            penalty_pts,
            new_balance,
        )

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist_and_update()

        # Emit event for NotificationManager to send notification
        self.emit(
            const.SIGNAL_SUFFIX_PENALTY_APPLIED,
            kid_id=kid_id,
            penalty_id=penalty_id,
            penalty_name=penalty_info[const.DATA_PENALTY_NAME],
            points=penalty_pts,
        )

        return new_balance

    async def reset_penalties(
        self, kid_id: str | None = None, penalty_id: str | None = None
    ) -> None:
        """Reset penalty tracking counters.

        Does NOT restore points - only clears the "times applied" counters.

        Args:
            kid_id: Optional kid ID to reset penalties for
            penalty_id: Optional penalty ID to reset

        Behavior:
        - kid_id + penalty_id: Reset specific penalty counter for specific kid
        - penalty_id only: Reset that penalty counter for all kids
        - kid_id only: Reset all penalty counters for that kid
        - Neither: Reset all penalty counters for all kids

        Raises:
            HomeAssistantError: If specified kid not found or penalty not assigned
        """
        if penalty_id and kid_id:
            # Reset a specific penalty for a specific kid
            kid_info: KidData | None = self._get_kid(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if penalty_id not in kid_info.get(const.DATA_KID_PENALTY_APPLIES, {}):
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Penalty ID '%s' does not apply to Kid ID '%s'",
                    penalty_id,
                    kid_id,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": f"penalty '{penalty_id}'",
                        "kid": kid_id,
                    },
                )

            kid_info[const.DATA_KID_PENALTY_APPLIES].pop(penalty_id, None)

        elif penalty_id:
            # Reset a specific penalty for all kids
            found = False
            for kid_info_loop in self._coordinator.kids_data.values():
                if penalty_id in kid_info_loop.get(const.DATA_KID_PENALTY_APPLIES, {}):
                    found = True
                    kid_info_loop[const.DATA_KID_PENALTY_APPLIES].pop(penalty_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Penalties - Penalty ID '%s' not found in any kid's data",
                    penalty_id,
                )

        elif kid_id:
            # Reset all penalties for a specific kid
            kid_info_elif: KidData | None = self._get_kid(kid_id)
            if not kid_info_elif:
                const.LOGGER.error(
                    "ERROR: Reset Penalties - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info_elif[const.DATA_KID_PENALTY_APPLIES].clear()

        else:
            # Reset all penalties for all kids
            const.LOGGER.info(
                "INFO: Reset Penalties - Resetting all penalties for all kids"
            )
            for kid_info in self._coordinator.kids_data.values():
                kid_info[const.DATA_KID_PENALTY_APPLIES].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Penalties completed - Kid ID '%s', Penalty ID '%s'",
            kid_id,
            penalty_id,
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    # =========================================================================
    # Bonus Operations
    # =========================================================================

    async def apply_bonus(self, parent_name: str, kid_id: str, bonus_id: str) -> float:
        """Apply bonus to kid - adds points via deposit().

        This method:
        1. Validates bonus and kid exist
        2. Deposits points (emits POINTS_CHANGED)
        3. Updates bonus tracking counter
        4. Sends notification to kid
        5. Persists changes

        Args:
            parent_name: Name of parent applying bonus (for audit trail)
            kid_id: The kid's internal ID
            bonus_id: The bonus's internal ID

        Returns:
            New balance after bonus

        Raises:
            HomeAssistantError: If kid or bonus not found
        """
        bonus_info = self._coordinator.bonuses_data.get(bonus_id)
        if not bonus_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BONUS,
                    "name": bonus_id,
                },
            )

        kid_info: KidData | None = self._get_kid(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        bonus_pts = bonus_info.get(const.DATA_BONUS_POINTS, const.DEFAULT_ZERO)
        bonus_name = bonus_info.get(const.DATA_BONUS_NAME, "")

        # Use deposit for bonus (emits POINTS_CHANGED)
        new_balance = await self.deposit(
            kid_id=kid_id,
            amount=bonus_pts,
            source=const.POINTS_SOURCE_BONUSES,
            reference_id=bonus_id,
            item_name=bonus_name,
            apply_multiplier=False,  # Bonuses don't use multiplier
        )

        # Landlord: Ensure bonus_applies entry exists with periods structure
        # StatisticsEngine (via StatisticsManager) creates period buckets (daily/weekly/etc)
        # on-demand via record_transaction() - matching the points pattern
        bonus_applies = kid_info.setdefault(const.DATA_KID_BONUS_APPLIES, {})
        if bonus_id not in bonus_applies:
            bonus_applies[bonus_id] = {
                const.DATA_KID_BONUS_PERIODS: {},
            }

        const.LOGGER.debug(
            "EconomyManager.apply_bonus: kid=%s, bonus=%s, pts=%.2f, new_balance=%.2f",
            kid_id,
            bonus_id,
            bonus_pts,
            new_balance,
        )

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist_and_update()

        # Emit event for NotificationManager to send notification
        self.emit(
            const.SIGNAL_SUFFIX_BONUS_APPLIED,
            kid_id=kid_id,
            bonus_id=bonus_id,
            bonus_name=bonus_info[const.DATA_BONUS_NAME],
            points=bonus_pts,
        )

        return new_balance

    async def reset_bonuses(
        self, kid_id: str | None = None, bonus_id: str | None = None
    ) -> None:
        """Reset bonus tracking counters.

        Does NOT remove points - only clears the "times applied" counters.

        Args:
            kid_id: Optional kid ID to reset bonuses for
            bonus_id: Optional bonus ID to reset

        Behavior:
        - kid_id + bonus_id: Reset specific bonus counter for specific kid
        - bonus_id only: Reset that bonus counter for all kids
        - kid_id only: Reset all bonus counters for that kid
        - Neither: Reset all bonus counters for all kids

        Raises:
            HomeAssistantError: If specified kid not found or bonus not assigned
        """
        if bonus_id and kid_id:
            # Reset a specific bonus for a specific kid
            kid_info: KidData | None = self._get_kid(kid_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if bonus_id not in kid_info.get(const.DATA_KID_BONUS_APPLIES, {}):
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Bonus '%s' does not apply to Kid ID '%s'",
                    bonus_id,
                    kid_id,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": f"bonus '{bonus_id}'",
                        "kid": kid_id,
                    },
                )

            kid_info[const.DATA_KID_BONUS_APPLIES].pop(bonus_id, None)

        elif bonus_id:
            # Reset a specific bonus for all kids
            found = False
            for kid_info_loop in self._coordinator.kids_data.values():
                if bonus_id in kid_info_loop.get(const.DATA_KID_BONUS_APPLIES, {}):
                    found = True
                    kid_info_loop[const.DATA_KID_BONUS_APPLIES].pop(bonus_id, None)

            if not found:
                const.LOGGER.warning(
                    "WARNING: Reset Bonuses - Bonus '%s' not found in any kid's data",
                    bonus_id,
                )

        elif kid_id:
            # Reset all bonuses for a specific kid
            kid_info_elif: KidData | None = self._get_kid(kid_id)
            if not kid_info_elif:
                const.LOGGER.error(
                    "ERROR: Reset Bonuses - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )

            kid_info_elif[const.DATA_KID_BONUS_APPLIES].clear()

        else:
            # Reset all bonuses for all kids
            const.LOGGER.info(
                "INFO: Reset Bonuses - Resetting all bonuses for all kids"
            )
            for kid_info in self._coordinator.kids_data.values():
                kid_info[const.DATA_KID_BONUS_APPLIES].clear()

        const.LOGGER.debug(
            "DEBUG: Reset Bonuses completed - Kid ID '%s', Bonus ID '%s'",
            kid_id,
            bonus_id,
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    # =========================================================================
    # CRUD METHODS - BONUS (Manager-owned create/update/delete)
    # =========================================================================
    # These methods own the write operations for bonus entities.
    # Called by options_flow.py and services.py - they must NOT write directly.

    def create_bonus(
        self, user_input: dict[str, Any], *, immediate_persist: bool = False
    ) -> dict[str, Any]:
        """Create a new bonus in storage.

        Args:
            user_input: Bonus data with DATA_* keys.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Complete BonusData dict ready for use.

        Emits:
            SIGNAL_SUFFIX_BONUS_CREATED with bonus_id and bonus_name.
        """
        # Build complete bonus data structure
        bonus_data = dict(
            db.build_bonus_or_penalty(user_input, const.ENTITY_TYPE_BONUS)
        )
        internal_id = str(bonus_data[const.DATA_BONUS_INTERNAL_ID])
        bonus_name = str(bonus_data.get(const.DATA_BONUS_NAME, ""))

        # Store in coordinator data
        self._coordinator._data[const.DATA_BONUSES][internal_id] = bonus_data
        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_BONUS_CREATED,
            bonus_id=internal_id,
            bonus_name=bonus_name,
        )

        const.LOGGER.info(
            "Created bonus '%s' (ID: %s)",
            bonus_name,
            internal_id,
        )

        return bonus_data

    def update_bonus(
        self, bonus_id: str, updates: dict[str, Any], *, immediate_persist: bool = False
    ) -> dict[str, Any]:
        """Update an existing bonus in storage.

        Args:
            bonus_id: Internal UUID of the bonus to update.
            updates: Partial bonus data with DATA_* keys to merge.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Updated BonusData dict.

        Raises:
            HomeAssistantError: If bonus not found.

        Emits:
            SIGNAL_SUFFIX_BONUS_UPDATED with bonus_id and bonus_name.
        """
        bonuses_data = self._coordinator._data.get(const.DATA_BONUSES, {})
        if bonus_id not in bonuses_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BONUS,
                    "name": bonus_id,
                },
            )

        existing = bonuses_data[bonus_id]
        # Build updated bonus (merge existing with updates)
        updated_bonus = dict(
            db.build_bonus_or_penalty(
                updates, const.ENTITY_TYPE_BONUS, existing=existing
            )
        )

        # Store updated bonus
        self._coordinator._data[const.DATA_BONUSES][bonus_id] = updated_bonus
        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        bonus_name = str(updated_bonus.get(const.DATA_BONUS_NAME, ""))

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_BONUS_UPDATED,
            bonus_id=bonus_id,
            bonus_name=bonus_name,
        )

        const.LOGGER.debug(
            "Updated bonus '%s' (ID: %s)",
            bonus_name,
            bonus_id,
        )

        return updated_bonus

    def delete_bonus(self, bonus_id: str, *, immediate_persist: bool = False) -> None:
        """Delete a bonus from storage.

        Args:
            bonus_id: Internal UUID of the bonus to delete.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Raises:
            HomeAssistantError: If bonus not found.

        Emits:
            SIGNAL_SUFFIX_BONUS_DELETED with bonus_id and bonus_name.
        """
        bonuses_data = self._coordinator._data.get(const.DATA_BONUSES, {})
        if bonus_id not in bonuses_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BONUS,
                    "name": bonus_id,
                },
            )

        bonus_name = bonuses_data[bonus_id].get(const.DATA_BONUS_NAME, bonus_id)

        # Delete from storage
        del self._coordinator._data[const.DATA_BONUSES][bonus_id]

        # Remove HA entities
        remove_entities_by_item_id(
            self.hass,
            self._coordinator.config_entry.entry_id,
            bonus_id,
        )

        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_BONUS_DELETED,
            bonus_id=bonus_id,
            bonus_name=bonus_name,
        )

        const.LOGGER.info(
            "Deleted bonus '%s' (ID: %s)",
            bonus_name,
            bonus_id,
        )

    # =========================================================================
    # CRUD METHODS - PENALTY (Manager-owned create/update/delete)
    # =========================================================================
    # These methods own the write operations for penalty entities.
    # Called by options_flow.py and services.py - they must NOT write directly.

    def create_penalty(
        self, user_input: dict[str, Any], *, immediate_persist: bool = False
    ) -> dict[str, Any]:
        """Create a new penalty in storage.

        Args:
            user_input: Penalty data with DATA_* keys.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Complete PenaltyData dict ready for use.

        Emits:
            SIGNAL_SUFFIX_PENALTY_CREATED with penalty_id and penalty_name.
        """
        # Build complete penalty data structure
        penalty_data = dict(
            db.build_bonus_or_penalty(user_input, const.ENTITY_TYPE_PENALTY)
        )
        internal_id = str(penalty_data[const.DATA_PENALTY_INTERNAL_ID])
        penalty_name = str(penalty_data.get(const.DATA_PENALTY_NAME, ""))

        # Store in coordinator data
        self._coordinator._data[const.DATA_PENALTIES][internal_id] = penalty_data
        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_PENALTY_CREATED,
            penalty_id=internal_id,
            penalty_name=penalty_name,
        )

        const.LOGGER.info(
            "Created penalty '%s' (ID: %s)",
            penalty_name,
            internal_id,
        )

        return penalty_data

    def update_penalty(
        self,
        penalty_id: str,
        updates: dict[str, Any],
        *,
        immediate_persist: bool = False,
    ) -> dict[str, Any]:
        """Update an existing penalty in storage.

        Args:
            penalty_id: Internal UUID of the penalty to update.
            updates: Partial penalty data with DATA_* keys to merge.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Updated PenaltyData dict.

        Raises:
            HomeAssistantError: If penalty not found.

        Emits:
            SIGNAL_SUFFIX_PENALTY_UPDATED with penalty_id and penalty_name.
        """
        penalties_data = self._coordinator._data.get(const.DATA_PENALTIES, {})
        if penalty_id not in penalties_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PENALTY,
                    "name": penalty_id,
                },
            )

        existing = penalties_data[penalty_id]
        # Build updated penalty (merge existing with updates)
        updated_penalty = dict(
            db.build_bonus_or_penalty(
                updates, const.ENTITY_TYPE_PENALTY, existing=existing
            )
        )

        # Store updated penalty
        self._coordinator._data[const.DATA_PENALTIES][penalty_id] = updated_penalty
        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        penalty_name = str(updated_penalty.get(const.DATA_PENALTY_NAME, ""))

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_PENALTY_UPDATED,
            penalty_id=penalty_id,
            penalty_name=penalty_name,
        )

        const.LOGGER.debug(
            "Updated penalty '%s' (ID: %s)",
            penalty_name,
            penalty_id,
        )

        return updated_penalty

    def delete_penalty(
        self, penalty_id: str, *, immediate_persist: bool = False
    ) -> None:
        """Delete a penalty from storage.

        Args:
            penalty_id: Internal UUID of the penalty to delete.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Raises:
            HomeAssistantError: If penalty not found.

        Emits:
            SIGNAL_SUFFIX_PENALTY_DELETED with penalty_id and penalty_name.
        """
        penalties_data = self._coordinator._data.get(const.DATA_PENALTIES, {})
        if penalty_id not in penalties_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_PENALTY,
                    "name": penalty_id,
                },
            )

        penalty_name = penalties_data[penalty_id].get(
            const.DATA_PENALTY_NAME, penalty_id
        )

        # Delete from storage
        del self._coordinator._data[const.DATA_PENALTIES][penalty_id]

        # Remove HA entities
        remove_entities_by_item_id(
            self.hass,
            self._coordinator.config_entry.entry_id,
            penalty_id,
        )

        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_PENALTY_DELETED,
            penalty_id=penalty_id,
            penalty_name=penalty_name,
        )

        const.LOGGER.info(
            "Deleted penalty '%s' (ID: %s)",
            penalty_name,
            penalty_id,
        )

    # =========================================================================
    # DATA RESET - Transactional Data Reset for Economy Domain
    # =========================================================================

    async def data_reset_points(
        self,
        scope: str,
        kid_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for points domain (economy-owned fields).

        Clears points, ledger, and economy-owned tracking while preserving
        kid configuration (name, user_id, notifications, language).

        Args:
            scope: Reset scope (global = all kids, kid = one kid)
            kid_id: Target kid ID for kid scope (optional)
            item_id: Not used for points domain (ignored)

        Emits:
            SIGNAL_SUFFIX_POINTS_DATA_RESET_COMPLETE with scope, kid_id, item_id
        """
        const.LOGGER.info(
            "Data reset: points domain - scope=%s, kid_id=%s",
            scope,
            kid_id,
        )

        kids_data = self._coordinator.kids_data

        # Determine which kids to process
        if kid_id:
            kid_ids = [kid_id] if kid_id in kids_data else []
        else:
            kid_ids = list(kids_data.keys())

        # Reset kid economy runtime fields
        for loop_kid_id in kid_ids:
            kid_info = kids_data.get(loop_kid_id)
            if not kid_info:
                continue

            # Cast for dynamic field access (TypedDict requires literal keys)
            kid_dict = cast("dict[str, Any]", kid_info)

            # Reset economy-owned scalar fields
            for field in db._ECONOMY_KID_RUNTIME_FIELDS:
                if field == const.DATA_KID_POINTS:
                    kid_dict[field] = const.DEFAULT_ZERO
                elif field == const.DATA_KID_POINTS_MULTIPLIER:
                    kid_dict[field] = const.DEFAULT_KID_POINTS_MULTIPLIER
                elif field == const.DATA_KID_LEDGER:
                    kid_dict[field] = []
                elif field in kid_dict:
                    # Clear any other economy fields
                    if isinstance(kid_dict[field], dict):
                        kid_dict[field] = {}
                    elif isinstance(kid_dict[field], list):
                        kid_dict[field] = []
                    else:
                        kid_dict[field] = const.DEFAULT_ZERO

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_DATA_RESET_COMPLETE,
            scope=scope,
            kid_id=kid_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: points domain complete - %d kids affected",
            len(kid_ids),
        )

    async def data_reset_penalties(
        self,
        scope: str,
        kid_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for penalties domain.

        Clears penalty application tracking (penalty_applies counters).
        Does NOT restore points - only clears "times applied" counters.

        Args:
            scope: Reset scope (global, kid, item_type, item)
            kid_id: Target kid ID for kid scope (optional)
            item_id: Target penalty ID for item scope (optional)

        Emits:
            SIGNAL_SUFFIX_PENALTY_DATA_RESET_COMPLETE with scope, kid_id, item_id
        """
        const.LOGGER.info(
            "Data reset: penalties domain - scope=%s, kid_id=%s, item_id=%s",
            scope,
            kid_id,
            item_id,
        )

        kids_data = self._coordinator.kids_data

        # Determine which kids to process
        if kid_id:
            kid_ids = [kid_id] if kid_id in kids_data else []
        else:
            kid_ids = list(kids_data.keys())

        # Reset kid-side penalty tracking
        for loop_kid_id in kid_ids:
            kid_info = kids_data.get(loop_kid_id)
            if not kid_info:
                continue

            penalty_applies = kid_info.get(const.DATA_KID_PENALTY_APPLIES, {})
            if item_id:
                # Item scope - only clear specific penalty
                penalty_applies.pop(item_id, None)
            else:
                # Clear all penalty tracking
                penalty_applies.clear()

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_PENALTY_DATA_RESET_COMPLETE,
            scope=scope,
            kid_id=kid_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: penalties domain complete - %d kids affected",
            len(kid_ids),
        )

    async def data_reset_bonuses(
        self,
        scope: str,
        kid_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for bonuses domain.

        Clears bonus application tracking (bonus_applies counters).
        Does NOT reverse points - only clears "times applied" counters.

        Args:
            scope: Reset scope (global, kid, item_type, item)
            kid_id: Target kid ID for kid scope (optional)
            item_id: Target bonus ID for item scope (optional)

        Emits:
            SIGNAL_SUFFIX_BONUS_DATA_RESET_COMPLETE with scope, kid_id, item_id
        """
        const.LOGGER.info(
            "Data reset: bonuses domain - scope=%s, kid_id=%s, item_id=%s",
            scope,
            kid_id,
            item_id,
        )

        kids_data = self._coordinator.kids_data

        # Determine which kids to process
        if kid_id:
            kid_ids = [kid_id] if kid_id in kids_data else []
        else:
            kid_ids = list(kids_data.keys())

        # Reset kid-side bonus tracking
        for loop_kid_id in kid_ids:
            kid_info = kids_data.get(loop_kid_id)
            if not kid_info:
                continue

            bonus_applies = kid_info.get(const.DATA_KID_BONUS_APPLIES, {})
            if item_id:
                # Item scope - only clear specific bonus
                bonus_applies.pop(item_id, None)
            else:
                # Clear all bonus tracking
                bonus_applies.clear()

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_BONUS_DATA_RESET_COMPLETE,
            scope=scope,
            kid_id=kid_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: bonuses domain complete - %d kids affected",
            len(kid_ids),
        )
