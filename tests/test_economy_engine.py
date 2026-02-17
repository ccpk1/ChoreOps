"""Unit tests for EconomyEngine - pure Python logic tests.

These tests verify the stateless economy calculations without any Home Assistant
mocking. The EconomyEngine is a pure Python module with no HA dependencies.

Test Categories:
- Point rounding and precision
- Sufficient funds validation (NSF checks)
- Multiplier calculations
- Ledger entry creation
- Ledger pruning
- InsufficientFundsError exception
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.economy_engine import (
    EconomyEngine,
    InsufficientFundsError,
)

if TYPE_CHECKING:
    from custom_components.choreops.type_defs import LedgerEntry

# =============================================================================
# Test: InsufficientFundsError
# =============================================================================


class TestInsufficientFundsError:
    """Tests for the InsufficientFundsError exception."""

    def test_error_attributes(self) -> None:
        """Test that error captures all relevant attributes."""
        error = InsufficientFundsError(
            kid_id="kid-123",
            current_balance=25.0,
            requested_amount=50.0,
        )

        assert error.kid_id == "kid-123"
        assert error.current_balance == 25.0
        assert error.requested_amount == 50.0
        assert error.shortfall == 25.0  # 50 - 25

    def test_error_message(self) -> None:
        """Test that error message is descriptive."""
        error = InsufficientFundsError(
            kid_id="kid-456",
            current_balance=10.0,
            requested_amount=100.0,
        )

        message = str(error)
        assert "kid-456" in message
        assert "10.0" in message or "10" in message
        assert "100.0" in message or "100" in message
        assert "90.0" in message or "90" in message  # shortfall

    def test_error_is_exception(self) -> None:
        """Test that InsufficientFundsError is a proper exception."""
        error = InsufficientFundsError("kid", 0.0, 10.0)
        assert isinstance(error, Exception)

        # Should be raisable
        with pytest.raises(InsufficientFundsError) as exc_info:
            raise error
        assert exc_info.value.shortfall == 10.0


# =============================================================================
# Test: round_points
# =============================================================================


class TestRoundPoints:
    """Tests for point rounding precision."""

    def test_rounds_to_default_precision(self) -> None:
        """Test default precision from const.DATA_FLOAT_PRECISION."""
        # Python float arithmetic can produce drift
        result = EconomyEngine.round_points(27.499999999999996)
        assert result == 27.5

    def test_rounds_up_correctly(self) -> None:
        """Test rounding behavior."""
        # Use values that don't have float representation issues
        result = EconomyEngine.round_points(10.556)
        assert result == 10.56

        result2 = EconomyEngine.round_points(10.559)
        assert result2 == 10.56

    def test_rounds_down_correctly(self) -> None:
        """Test rounding down at boundary."""
        result = EconomyEngine.round_points(10.554)
        assert result == 10.55

    def test_custom_precision(self) -> None:
        """Test custom precision parameter."""
        result = EconomyEngine.round_points(10.5555, precision=3)
        assert result == 10.556

    def test_zero_precision(self) -> None:
        """Test whole number rounding."""
        result = EconomyEngine.round_points(10.6, precision=0)
        assert result == 11.0

    def test_negative_values(self) -> None:
        """Test rounding negative values."""
        result = EconomyEngine.round_points(-27.499999999999996)
        assert result == -27.5


# =============================================================================
# Test: validate_sufficient_funds
# =============================================================================


class TestValidateSufficientFunds:
    """Tests for NSF (Non-Sufficient Funds) validation."""

    def test_sufficient_funds_exact(self) -> None:
        """Test exact balance matches cost."""
        assert EconomyEngine.validate_sufficient_funds(100.0, 100.0) is True

    def test_sufficient_funds_excess(self) -> None:
        """Test balance exceeds cost."""
        assert EconomyEngine.validate_sufficient_funds(150.0, 100.0) is True

    def test_insufficient_funds(self) -> None:
        """Test balance is less than cost (NSF)."""
        assert EconomyEngine.validate_sufficient_funds(50.0, 100.0) is False

    def test_zero_balance_zero_cost(self) -> None:
        """Test zero balance with zero cost (edge case)."""
        assert EconomyEngine.validate_sufficient_funds(0.0, 0.0) is True

    def test_zero_balance_positive_cost(self) -> None:
        """Test zero balance with positive cost."""
        assert EconomyEngine.validate_sufficient_funds(0.0, 10.0) is False

    def test_fractional_amounts(self) -> None:
        """Test with fractional point values."""
        assert EconomyEngine.validate_sufficient_funds(10.50, 10.50) is True
        assert EconomyEngine.validate_sufficient_funds(10.49, 10.50) is False


# =============================================================================
# Test: calculate_with_multiplier
# =============================================================================


class TestCalculateWithMultiplier:
    """Tests for multiplier calculations."""

    def test_no_multiplier(self) -> None:
        """Test multiplier of 1.0 (no change)."""
        result = EconomyEngine.calculate_with_multiplier(100.0, 1.0)
        assert result == 100.0

    def test_bonus_multiplier(self) -> None:
        """Test 50% bonus multiplier."""
        result = EconomyEngine.calculate_with_multiplier(100.0, 1.5)
        assert result == 150.0

    def test_reduction_multiplier(self) -> None:
        """Test reduction multiplier (penalty)."""
        result = EconomyEngine.calculate_with_multiplier(100.0, 0.5)
        assert result == 50.0

    def test_double_multiplier(self) -> None:
        """Test 2x multiplier."""
        result = EconomyEngine.calculate_with_multiplier(25.0, 2.0)
        assert result == 50.0

    def test_result_is_rounded(self) -> None:
        """Test that result is rounded to precision."""
        # 33.33 * 1.5 = 49.995 → 50.0 (but float precision means 49.99499...)
        result = EconomyEngine.calculate_with_multiplier(33.33, 1.5)
        assert result == 49.99  # Actual float result after rounding

        # Use values that produce clean results
        result2 = EconomyEngine.calculate_with_multiplier(20.0, 2.5)
        assert result2 == 50.0

    def test_zero_base(self) -> None:
        """Test zero base points."""
        result = EconomyEngine.calculate_with_multiplier(0.0, 1.5)
        assert result == 0.0

    def test_custom_precision(self) -> None:
        """Test custom precision in multiplier calculation."""
        result = EconomyEngine.calculate_with_multiplier(10.0, 1.333, precision=1)
        assert result == 13.3


# =============================================================================
# Test: create_ledger_entry
# =============================================================================


class TestCreateLedgerEntry:
    """Tests for ledger entry creation."""

    def test_deposit_entry(self) -> None:
        """Test creating a deposit (positive) entry."""
        entry = EconomyEngine.create_ledger_entry(
            current_balance=100.0,
            delta=50.0,
            source=const.POINTS_SOURCE_CHORES,
            reference_id="chore-123",
        )

        assert entry[const.DATA_LEDGER_AMOUNT] == 50.0
        assert entry[const.DATA_LEDGER_BALANCE_AFTER] == 150.0
        assert entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_CHORES
        assert entry[const.DATA_LEDGER_REFERENCE_ID] == "chore-123"
        assert const.DATA_LEDGER_TIMESTAMP in entry

    def test_withdrawal_entry(self) -> None:
        """Test creating a withdrawal (negative) entry."""
        entry = EconomyEngine.create_ledger_entry(
            current_balance=100.0,
            delta=-30.0,
            source=const.POINTS_SOURCE_REWARDS,
            reference_id="reward-456",
        )

        assert entry[const.DATA_LEDGER_AMOUNT] == -30.0
        assert entry[const.DATA_LEDGER_BALANCE_AFTER] == 70.0
        assert entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_REWARDS
        assert entry[const.DATA_LEDGER_REFERENCE_ID] == "reward-456"

    def test_entry_without_reference(self) -> None:
        """Test creating an entry without reference_id."""
        entry = EconomyEngine.create_ledger_entry(
            current_balance=50.0,
            delta=-10.0,
            source=const.POINTS_SOURCE_PENALTIES,
        )

        assert entry[const.DATA_LEDGER_REFERENCE_ID] is None
        assert entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_PENALTIES

    def test_entry_amounts_are_rounded(self) -> None:
        """Test that entry values are properly rounded."""
        entry = EconomyEngine.create_ledger_entry(
            current_balance=100.0,
            delta=33.333333333,
            source=const.POINTS_SOURCE_BONUSES,
        )

        assert entry[const.DATA_LEDGER_AMOUNT] == 33.33
        assert entry[const.DATA_LEDGER_BALANCE_AFTER] == 133.33

    def test_timestamp_is_iso_format(self) -> None:
        """Test that timestamp is ISO format string."""
        entry = EconomyEngine.create_ledger_entry(
            current_balance=0.0,
            delta=10.0,
            source=const.POINTS_SOURCE_MANUAL,
        )

        timestamp = entry[const.DATA_LEDGER_TIMESTAMP]
        assert isinstance(timestamp, str)
        # Should contain date and time markers
        assert "T" in timestamp or "-" in timestamp

    def test_all_source_types(self) -> None:
        """Test creating entries with all valid source types."""
        sources = [
            const.POINTS_SOURCE_CHORES,
            const.POINTS_SOURCE_CHORES,
            const.POINTS_SOURCE_REWARDS,
            const.POINTS_SOURCE_PENALTIES,
            const.POINTS_SOURCE_BONUSES,
            const.POINTS_SOURCE_MANUAL,
        ]

        for source in sources:
            entry = EconomyEngine.create_ledger_entry(
                current_balance=100.0,
                delta=10.0,
                source=source,
            )
            assert entry[const.DATA_LEDGER_SOURCE] == source


# =============================================================================
# Test: calculate_new_balance
# =============================================================================


class TestCalculateNewBalance:
    """Tests for balance calculation."""

    def test_positive_delta(self) -> None:
        """Test adding points."""
        result = EconomyEngine.calculate_new_balance(100.0, 50.0)
        assert result == 150.0

    def test_negative_delta(self) -> None:
        """Test subtracting points."""
        result = EconomyEngine.calculate_new_balance(100.0, -30.0)
        assert result == 70.0

    def test_zero_delta(self) -> None:
        """Test zero change."""
        result = EconomyEngine.calculate_new_balance(100.0, 0.0)
        assert result == 100.0

    def test_result_is_rounded(self) -> None:
        """Test that result is rounded."""
        result = EconomyEngine.calculate_new_balance(0.1, 0.2)
        # 0.1 + 0.2 can produce 0.30000000000000004 in Python
        assert result == 0.3

    def test_negative_balance_possible(self) -> None:
        """Test that negative balance is mathematically possible (validation separate)."""
        result = EconomyEngine.calculate_new_balance(10.0, -50.0)
        assert result == -40.0


# =============================================================================
# Test: prune_ledger
# =============================================================================


class TestPruneLedger:
    """Tests for ledger pruning."""

    def _make_entry(self, amount: float) -> LedgerEntry:
        """Helper to create minimal ledger entry for testing."""
        return {
            const.DATA_LEDGER_TIMESTAMP: "2026-01-24T12:00:00+00:00",
            const.DATA_LEDGER_AMOUNT: amount,
            const.DATA_LEDGER_BALANCE_AFTER: 100.0,
            const.DATA_LEDGER_SOURCE: const.POINTS_SOURCE_MANUAL,
            const.DATA_LEDGER_REFERENCE_ID: None,
        }

    def test_no_pruning_under_limit(self) -> None:
        """Test that ledger under limit is unchanged."""
        ledger = [self._make_entry(i) for i in range(10)]
        result = EconomyEngine.prune_ledger(ledger, max_entries=50)

        assert len(result) == 10
        assert result is ledger  # Same object

    def test_no_pruning_at_limit(self) -> None:
        """Test that ledger at exact limit is unchanged."""
        ledger = [self._make_entry(i) for i in range(50)]
        result = EconomyEngine.prune_ledger(ledger, max_entries=50)

        assert len(result) == 50

    def test_pruning_over_limit(self) -> None:
        """Test that ledger over limit is trimmed."""
        ledger = [self._make_entry(i) for i in range(60)]
        result = EconomyEngine.prune_ledger(ledger, max_entries=50)

        assert len(result) == 50

    def test_pruning_keeps_newest(self) -> None:
        """Test that oldest entries are removed, newest kept."""
        ledger = [self._make_entry(i) for i in range(60)]
        result = EconomyEngine.prune_ledger(ledger, max_entries=50)

        # Should keep entries 10-59 (newest 50)
        assert result[0][const.DATA_LEDGER_AMOUNT] == 10
        assert result[-1][const.DATA_LEDGER_AMOUNT] == 59

    def test_modifies_in_place(self) -> None:
        """Test that pruning modifies the original list."""
        ledger = [self._make_entry(i) for i in range(60)]
        original_id = id(ledger)
        result = EconomyEngine.prune_ledger(ledger, max_entries=50)

        assert id(result) == original_id
        assert len(ledger) == 50

    def test_empty_ledger(self) -> None:
        """Test pruning an empty ledger."""
        ledger: list = []
        result = EconomyEngine.prune_ledger(ledger, max_entries=50)

        assert len(result) == 0
        assert result is ledger

    def test_custom_max_entries(self) -> None:
        """Test custom max_entries parameter."""
        ledger = [self._make_entry(i) for i in range(100)]
        result = EconomyEngine.prune_ledger(ledger, max_entries=10)

        assert len(result) == 10
        # Should keep entries 90-99 (newest 10)
        assert result[0][const.DATA_LEDGER_AMOUNT] == 90
        assert result[-1][const.DATA_LEDGER_AMOUNT] == 99

    def test_default_max_entries(self) -> None:
        """Test default max_entries value."""
        assert EconomyEngine.DEFAULT_MAX_LEDGER_ENTRIES == 50
