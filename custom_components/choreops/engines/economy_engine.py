"""Economy Engine - Pure logic for point transactions and ledger management.

This engine provides stateless, pure Python functions for:
- Point arithmetic with consistent rounding
- Ledger entry creation and pruning
- Sufficient funds validation (NSF checks)
- Multiplier calculations

ARCHITECTURE: This is a pure logic engine with NO Home Assistant dependencies.
All functions are static methods that operate on passed-in data.
State management belongs in EconomyManager.

See docs/ARCHITECTURE.md for the Engine vs Manager distinction.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from .. import const

if TYPE_CHECKING:
    from ..type_defs import LedgerEntry


def _now_iso() -> str:
    """Return current UTC time as ISO string (engine-internal helper)."""
    return datetime.now(UTC).isoformat()


class InsufficientFundsError(Exception):
    """Raised when a withdrawal would result in negative balance.

    Attributes:
        assignee_id: The assignee attempting the withdrawal
        current_balance: Current point balance
        requested_amount: Amount attempted to withdraw
        shortfall: How much more is needed (requested - current)
    """

    def __init__(
        self,
        assignee_id: str,
        current_balance: float,
        requested_amount: float,
    ) -> None:
        """Initialize InsufficientFundsError.

        Args:
            assignee_id: The assignee attempting the withdrawal
            current_balance: Current point balance
            requested_amount: Amount attempted to withdraw
        """
        self.assignee_id = assignee_id
        self.current_balance = current_balance
        self.requested_amount = requested_amount
        self.shortfall = requested_amount - current_balance
        super().__init__(
            f"Insufficient funds for assignee {assignee_id}: "
            f"balance={current_balance}, requested={requested_amount}, "
            f"shortfall={self.shortfall}"
        )


class EconomyEngine:
    """Pure logic engine for point calculations and ledger operations.

    All methods are static - no instance state. This enables easy unit testing
    without any Home Assistant mocking.

    Transaction Sources (for ledger entries):
        Uses existing POINTS_SOURCE_* constants from const.py:
        - POINTS_SOURCE_CHORES: Points earned from completing a chore
        - POINTS_SOURCE_REWARDS: Points spent on a reward (negative delta)
        - POINTS_SOURCE_PENALTIES: Points deducted as penalty
        - POINTS_SOURCE_BONUSES: Points added as bonus
        - POINTS_SOURCE_MANUAL: Manual point adjustment by approver
        - POINTS_SOURCE_BADGES/ACHIEVEMENTS/CHALLENGES: Gamification rewards

    Reference IDs provide additional context (chore_id, reward_id, etc.).
    """

    # Default maximum ledger entries to prevent storage bloat
    DEFAULT_MAX_LEDGER_ENTRIES: int = 50

    @staticmethod
    def round_points(
        value: float, precision: int = const.DATA_FLOAT_PRECISION
    ) -> float:
        """Round points to consistent precision.

        Prevents Python float arithmetic drift (e.g., 27.499999999999996 → 27.5).

        Args:
            value: The float value to round
            precision: Decimal places (default from const.DATA_FLOAT_PRECISION)

        Returns:
            Rounded float value
        """
        return round(value, precision)

    @staticmethod
    def validate_sufficient_funds(balance: float, cost: float) -> bool:
        """Check if balance is sufficient for a withdrawal.

        Args:
            balance: Current point balance
            cost: Amount to withdraw (positive value)

        Returns:
            True if balance >= cost, False otherwise (NSF)
        """
        return balance >= cost

    @staticmethod
    def calculate_with_multiplier(
        base_points: float,
        multiplier: float,
        precision: int = const.DATA_FLOAT_PRECISION,
    ) -> float:
        """Apply a multiplier to base points with rounding.

        Used for badge-based point multipliers.

        Args:
            base_points: Base point value
            multiplier: Multiplier to apply (e.g., 1.5 for 50% bonus)
            precision: Decimal places for rounding

        Returns:
            Rounded result of base_points * multiplier
        """
        return EconomyEngine.round_points(base_points * multiplier, precision)

    @staticmethod
    def create_ledger_entry(
        current_balance: float,
        delta: float,
        source: str,
        reference_id: str | None = None,
        item_name: str | None = None,
    ) -> LedgerEntry:
        """Create an immutable ledger entry for a transaction.

        Args:
            current_balance: Balance BEFORE the transaction
            delta: Amount to add (positive) or subtract (negative)
            source: Transaction source (e.g., "chore_approval", "reward_redemption")
            reference_id: Optional ID of related entity (chore_id, reward_id, etc.)
            item_name: Optional human-readable name of related item (Phase 4C)

        Returns:
            LedgerEntry TypedDict with transaction details
        """
        new_balance = EconomyEngine.round_points(current_balance + delta)
        entry: LedgerEntry = {
            const.DATA_LEDGER_TIMESTAMP: _now_iso(),
            const.DATA_LEDGER_AMOUNT: EconomyEngine.round_points(delta),
            const.DATA_LEDGER_BALANCE_AFTER: new_balance,
            const.DATA_LEDGER_SOURCE: source,
            const.DATA_LEDGER_REFERENCE_ID: reference_id,
        }

        # Add item_name if provided (Phase 4C enhancement)
        if item_name:
            entry[const.DATA_LEDGER_ITEM_NAME] = item_name  # type: ignore[typeddict-unknown-key]

        return entry

    @staticmethod
    def calculate_new_balance(current_balance: float, delta: float) -> float:
        """Calculate new balance after applying delta.

        Args:
            current_balance: Current point balance
            delta: Amount to add (positive) or subtract (negative)

        Returns:
            New balance after transaction, rounded
        """
        return EconomyEngine.round_points(current_balance + delta)

    @staticmethod
    def prune_ledger(
        ledger: list[LedgerEntry],
        max_entries: int = DEFAULT_MAX_LEDGER_ENTRIES,
        max_age_days: int | None = None,
        now_utc: datetime | None = None,
    ) -> list[LedgerEntry]:
        """Trim ledger to maximum entries, keeping most recent.

        Modifies the list in place and returns it for convenience.
        Newest entries are at the END of the list (append order).

        Args:
            ledger: List of ledger entries to prune
            max_entries: Maximum entries to keep (default 50)
            max_age_days: Optional age-based retention window in days
            now_utc: Optional current time override for deterministic tests

        Returns:
            The pruned ledger list (same object, modified in place)
        """
        if max_age_days is not None and max_age_days > 0:
            current_time = now_utc or datetime.now(UTC)
            cutoff = current_time - timedelta(days=max_age_days)

            retained_entries: list[LedgerEntry] = []
            for entry in ledger:
                raw_timestamp = entry.get(const.DATA_LEDGER_TIMESTAMP)
                if not isinstance(raw_timestamp, str):
                    retained_entries.append(entry)
                    continue

                try:
                    parsed = datetime.fromisoformat(raw_timestamp)
                except ValueError:
                    retained_entries.append(entry)
                    continue

                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)

                if parsed >= cutoff:
                    retained_entries.append(entry)

            if len(retained_entries) != len(ledger):
                ledger[:] = retained_entries

        if len(ledger) > max_entries:
            # Remove oldest entries (beginning of list)
            del ledger[: len(ledger) - max_entries]
        return ledger
