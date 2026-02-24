"""Integration tests for EconomyManager.

Tests the EconomyManager's interaction with coordinator and event system.
These tests use the full integration test setup with mocked Home Assistant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.choreops import const
from custom_components.choreops.managers.economy_manager import InsufficientFundsError
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_dispatcher_send():
    """Mock the dispatcher send function to capture emitted events."""
    with patch(
        "custom_components.choreops.managers.base_manager.async_dispatcher_send"
    ) as mock:
        yield mock


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 assignee, 1 approver, 5 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class TestEconomyManagerDeposit:
    """Tests for EconomyManager.deposit() method."""

    @pytest.mark.asyncio
    async def test_deposit_increases_balance(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that deposit increases assignee's balance."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        # Get a assignee
        assignee_id = list(coordinator.assignees_data.keys())[0]
        initial_balance = manager.get_balance(assignee_id)

        # Deposit points (async method)
        new_balance = await manager.deposit(
            assignee_id=assignee_id,
            amount=10.0,
            source=const.POINTS_SOURCE_CHORES,
        )

        assert new_balance == initial_balance + 10.0
        assert manager.get_balance(assignee_id) == new_balance

    @pytest.mark.asyncio
    async def test_deposit_creates_ledger_entry(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that deposit creates a ledger entry."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]

        # Clear any existing ledger
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_LEDGER] = []  # type: ignore[typeddict-unknown-key]

        # Deposit (async method)
        await manager.deposit(
            assignee_id=assignee_id,
            amount=15.0,
            source=const.POINTS_SOURCE_BONUSES,
            reference_id="test-bonus-123",
        )

        # Check ledger
        history = manager.get_history(assignee_id, limit=10)
        assert len(history) == 1
        entry = history[0]
        assert entry[const.DATA_LEDGER_AMOUNT] == 15.0
        assert entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_BONUSES
        assert entry[const.DATA_LEDGER_REFERENCE_ID] == "test-bonus-123"

    @pytest.mark.asyncio
    async def test_deposit_emits_points_changed_event(
        self,
        scenario_minimal: SetupResult,
        mock_dispatcher_send: MagicMock,
    ) -> None:
        """Test that deposit emits SIGNAL_SUFFIX_POINTS_CHANGED event."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        initial_balance = manager.get_balance(assignee_id)

        await manager.deposit(
            assignee_id=assignee_id,
            amount=25.0,
            source=const.POINTS_SOURCE_CHORES,
        )

        # Verify event was emitted
        mock_dispatcher_send.assert_called()
        call_args = mock_dispatcher_send.call_args
        # Check signal name contains our suffix
        signal = call_args[0][1]  # Second positional arg is the signal
        assert const.SIGNAL_SUFFIX_POINTS_CHANGED in signal

        # Payload is passed as third positional arg (dict)
        payload = call_args[0][2]
        assert payload["assignee_id"] == assignee_id
        assert payload["old_balance"] == initial_balance
        assert payload["new_balance"] == initial_balance + 25.0
        assert payload["delta"] == 25.0
        assert payload["source"] == const.POINTS_SOURCE_CHORES

    @pytest.mark.asyncio
    async def test_deposit_with_multiplier(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test deposit with multiplier applied."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS_MULTIPLIER] = 1.5  # 1.5x multiplier

        initial_balance = manager.get_balance(assignee_id)

        # Deposit with multiplier (async method)
        new_balance = await manager.deposit(
            assignee_id=assignee_id,
            amount=10.0,
            source=const.POINTS_SOURCE_CHORES,
            apply_multiplier=True,
        )

        # 10 * 1.5 = 15
        assert new_balance == initial_balance + 15.0

    @pytest.mark.asyncio
    async def test_deposit_rejects_negative_amount(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that deposit rejects negative amounts."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]

        with pytest.raises(ValueError, match="must be positive"):
            await manager.deposit(
                assignee_id=assignee_id,
                amount=-10.0,
                source=const.POINTS_SOURCE_BONUSES,
            )


class TestEconomyManagerWithdraw:
    """Tests for EconomyManager.withdraw() method."""

    @pytest.mark.asyncio
    async def test_withdraw_decreases_balance(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that withdraw decreases assignee's balance."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 100.0  # Ensure sufficient balance

        new_balance = await manager.withdraw(
            assignee_id=assignee_id,
            amount=30.0,
            source=const.POINTS_SOURCE_REWARDS,
        )

        assert new_balance == 70.0
        assert manager.get_balance(assignee_id) == 70.0

    @pytest.mark.asyncio
    async def test_withdraw_creates_negative_ledger_entry(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that withdraw creates a negative ledger entry."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 50.0
        assignee[const.DATA_USER_LEDGER] = []  # type: ignore[typeddict-unknown-key]

        await manager.withdraw(
            assignee_id=assignee_id,
            amount=20.0,
            source=const.POINTS_SOURCE_REWARDS,
            reference_id="reward-abc",
        )

        history = manager.get_history(assignee_id, limit=10)
        assert len(history) == 1
        entry = history[0]
        assert entry[const.DATA_LEDGER_AMOUNT] == -20.0  # Negative
        assert entry[const.DATA_LEDGER_BALANCE_AFTER] == 30.0
        assert entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_REWARDS
        assert entry[const.DATA_LEDGER_REFERENCE_ID] == "reward-abc"

    @pytest.mark.asyncio
    async def test_withdraw_insufficient_funds_raises(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that withdraw with insufficient funds raises InsufficientFundsError.

        Note: withdraw() defaults to allow_negative=True (approver authority pattern).
        Only reward redemptions explicitly set allow_negative=False for NSF.
        """
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 10.0  # Only 10 points

        with pytest.raises(InsufficientFundsError) as exc_info:
            await manager.withdraw(
                assignee_id=assignee_id,
                amount=50.0,  # Trying to withdraw 50
                source=const.POINTS_SOURCE_REWARDS,
                allow_negative=False,  # Explicitly test NSF behavior
            )

        error = exc_info.value
        assert error.assignee_id == assignee_id
        assert error.current_balance == 10.0
        assert error.requested_amount == 50.0

    @pytest.mark.asyncio
    async def test_withdraw_emits_points_changed_event(
        self,
        scenario_minimal: SetupResult,
        mock_dispatcher_send: MagicMock,
    ) -> None:
        """Test that withdraw emits SIGNAL_SUFFIX_POINTS_CHANGED event."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 100.0

        await manager.withdraw(
            assignee_id=assignee_id,
            amount=40.0,
            source=const.POINTS_SOURCE_PENALTIES,
        )

        mock_dispatcher_send.assert_called()
        call_args = mock_dispatcher_send.call_args
        # Payload is third positional arg (dict)
        payload = call_args[0][2]
        assert payload["delta"] == -40.0  # Negative delta

    @pytest.mark.asyncio
    async def test_withdraw_rejects_negative_amount(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that withdraw rejects negative amounts."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]

        with pytest.raises(ValueError, match="must be positive"):
            await manager.withdraw(
                assignee_id=assignee_id,
                amount=-10.0,
                source=const.POINTS_SOURCE_PENALTIES,
            )


class TestEconomyManagerHistory:
    """Tests for EconomyManager history methods."""

    @pytest.mark.asyncio
    async def test_get_history_returns_recent_entries(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test get_history returns entries in order."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 0.0
        assignee[const.DATA_USER_LEDGER] = []  # type: ignore[typeddict-unknown-key]

        # Multiple deposits (async method)
        await manager.deposit(assignee_id, 10.0, source=const.POINTS_SOURCE_CHORES)
        await manager.deposit(assignee_id, 20.0, source=const.POINTS_SOURCE_BONUSES)
        await manager.deposit(assignee_id, 30.0, source=const.POINTS_SOURCE_MANUAL)

        history = manager.get_history(assignee_id, limit=10)
        assert len(history) == 3
        # Entries should be oldest to newest (append order)
        assert history[0][const.DATA_LEDGER_AMOUNT] == 10.0
        assert history[1][const.DATA_LEDGER_AMOUNT] == 20.0
        assert history[2][const.DATA_LEDGER_AMOUNT] == 30.0

    @pytest.mark.asyncio
    async def test_get_history_respects_limit(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test get_history respects limit parameter."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 0.0
        assignee[const.DATA_USER_LEDGER] = []  # type: ignore[typeddict-unknown-key]

        # Add 5 entries (async method)
        for i in range(5):
            await manager.deposit(
                assignee_id, float(i + 1), source=const.POINTS_SOURCE_MANUAL
            )

        # Request only 2
        history = manager.get_history(assignee_id, limit=2)
        assert len(history) == 2
        # Should be the LAST 2 entries (most recent)
        assert history[0][const.DATA_LEDGER_AMOUNT] == 4.0
        assert history[1][const.DATA_LEDGER_AMOUNT] == 5.0

    def test_get_history_nonexistent_assignee(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test get_history returns empty list for nonexistent assignee."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        history = manager.get_history("nonexistent-assignee-id", limit=10)
        assert history == []


class TestEconomyManagerBalance:
    """Tests for EconomyManager.get_balance() method."""

    def test_get_balance_returns_current(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test get_balance returns current balance."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 42.5

        assert manager.get_balance(assignee_id) == 42.5

    def test_get_balance_nonexistent_assignee(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test get_balance returns 0 for nonexistent assignee."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        balance = manager.get_balance("nonexistent-assignee-id")
        assert balance == 0.0

    def test_get_balance_handles_invalid_value(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test get_balance handles invalid stored value."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = "not a number"  # type: ignore[typeddict-item]

        # Should return 0.0 instead of crashing
        assert manager.get_balance(assignee_id) == 0.0


class TestEconomyManagerLedgerIntegration:
    """Tests for ledger integration via EconomyManager deposit/withdraw."""

    @pytest.mark.asyncio
    async def test_deposit_creates_ledger_entry(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that EconomyManager.deposit creates ledger entries."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 0.0
        assignee[const.DATA_USER_LEDGER] = []  # type: ignore[typeddict-unknown-key]

        # Use economy_manager.deposit
        await manager.deposit(
            assignee_id, amount=50.0, source=const.POINTS_SOURCE_CHORES
        )

        # Check ledger was created
        ledger = assignee.get(const.DATA_USER_LEDGER, [])
        assert len(ledger) == 1
        entry = ledger[0]
        # Source is passed through directly (no mapping)
        assert entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_CHORES

    @pytest.mark.asyncio
    async def test_ledger_source_passthrough(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that POINTS_SOURCE_* passes through to ledger directly."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]

        # Test various sources - all should pass through unchanged
        test_sources = [
            const.POINTS_SOURCE_CHORES,
            const.POINTS_SOURCE_BONUSES,
            const.POINTS_SOURCE_MANUAL,
            const.POINTS_SOURCE_BADGES,
            const.POINTS_SOURCE_ACHIEVEMENTS,
        ]

        for source in test_sources:
            assignee[const.DATA_USER_LEDGER] = []  # type: ignore[typeddict-unknown-key]
            assignee[const.DATA_USER_POINTS] = 100.0

            await manager.deposit(assignee_id, amount=5.0, source=source)

            ledger = assignee.get(const.DATA_USER_LEDGER, [])
            assert len(ledger) == 1, f"Failed for source {source}"
            assert ledger[0][const.DATA_LEDGER_SOURCE] == source

    @pytest.mark.asyncio
    async def test_deposit_prunes_ledger(
        self,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that ledger is pruned to MAX_ENTRIES."""
        coordinator = scenario_minimal.coordinator
        manager = coordinator.economy_manager

        assignee_id = list(coordinator.assignees_data.keys())[0]
        assignee = coordinator.assignees_data[assignee_id]
        assignee[const.DATA_USER_POINTS] = 0.0
        assignee[const.DATA_USER_LEDGER] = []  # type: ignore[typeddict-unknown-key]

        # Add more than max entries
        for i in range(const.DEFAULT_LEDGER_MAX_ENTRIES + 10):
            await manager.deposit(
                assignee_id, amount=1.0, source=const.POINTS_SOURCE_OTHER
            )

        ledger = assignee.get(const.DATA_USER_LEDGER, [])
        assert len(ledger) == const.DEFAULT_LEDGER_MAX_ENTRIES
