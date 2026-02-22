"""Tests for event infrastructure (BaseManager, signal scoping).

Phase 0: Layered Architecture Foundation
Tests the event communication infrastructure used by managers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers.entity_helpers import get_event_signal
from custom_components.choreops.managers.base_manager import BaseManager


class MockManager(BaseManager):
    """Concrete manager for testing BaseManager."""

    async def async_setup(self) -> None:
        """Mock setup (no subscriptions)."""


class TestGetEventSignal:
    """Tests for get_event_signal() helper function."""

    def test_get_event_signal_format(self) -> None:
        """Test event signal follows expected format."""
        entry_id = "abc123"
        suffix = const.SIGNAL_SUFFIX_POINTS_CHANGED

        signal = get_event_signal(entry_id, suffix)

        assert signal == f"{const.DOMAIN}_{entry_id}_{suffix}"
        assert signal == f"{const.DOMAIN}_abc123_points_changed"

    def test_get_event_signal_multi_instance_isolation(self) -> None:
        """Test that two instances get different signals."""
        entry_id_1 = "instance_alpha"
        entry_id_2 = "instance_beta"
        suffix = const.SIGNAL_SUFFIX_CHORE_APPROVED

        signal_1 = get_event_signal(entry_id_1, suffix)
        signal_2 = get_event_signal(entry_id_2, suffix)

        # Signals should be different
        assert signal_1 != signal_2
        # Each should contain its entry_id
        assert "instance_alpha" in signal_1
        assert "instance_beta" in signal_2
        # Both should have same suffix
        assert suffix in signal_1
        assert suffix in signal_2

    def test_get_event_signal_various_suffixes(self) -> None:
        """Test multiple signal suffixes work correctly."""
        entry_id = "test_entry"

        signals = [
            (const.SIGNAL_SUFFIX_POINTS_CHANGED, "points_changed"),
            (const.SIGNAL_SUFFIX_CHORE_CLAIMED, "chore_claimed"),
            (const.SIGNAL_SUFFIX_BADGE_EARNED, "badge_earned"),
            (const.SIGNAL_SUFFIX_ASSIGNEE_CREATED, "assignee_created"),
        ]

        for suffix, expected_suffix in signals:
            signal = get_event_signal(entry_id, suffix)
            assert signal == f"{const.DOMAIN}_test_entry_{expected_suffix}"


class TestBaseManager:
    """Tests for BaseManager class."""

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant instance."""
        return MagicMock()

    @pytest.fixture
    def mock_coordinator(self) -> MagicMock:
        """Create a mock coordinator with config entry."""
        coordinator = MagicMock()
        coordinator.config_entry.entry_id = "test_entry_123"
        coordinator.config_entry.async_on_unload = MagicMock()
        return coordinator

    def test_manager_initialization(
        self, mock_hass: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test manager initializes with correct references."""
        manager = MockManager(mock_hass, mock_coordinator)

        assert manager.hass is mock_hass
        assert manager.coordinator is mock_coordinator
        assert manager.entry_id == "test_entry_123"

    def test_emit_calls_dispatcher(
        self, mock_hass: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test emit() dispatches events with correct signal."""
        manager = MockManager(mock_hass, mock_coordinator)

        with patch(
            "custom_components.choreops.managers.base_manager.async_dispatcher_send"
        ) as mock_send:
            manager.emit(
                const.SIGNAL_SUFFIX_POINTS_CHANGED,
                assignee_id="assignee1",
                old_balance=50.0,
                new_balance=60.0,
                delta=10.0,
                source="chore_approval",
            )

            # Verify dispatcher was called
            mock_send.assert_called_once()

            # Verify first arg is hass
            assert mock_send.call_args[0][0] is mock_hass

            # Verify second arg is correct signal
            expected_signal = get_event_signal(
                "test_entry_123", const.SIGNAL_SUFFIX_POINTS_CHANGED
            )
            assert mock_send.call_args[0][1] == expected_signal

            # Verify payload was passed as third positional arg (dict)
            payload = mock_send.call_args[0][2]
            assert payload["assignee_id"] == "assignee1"
            assert payload["delta"] == 10.0

    def test_listen_subscribes_and_registers_cleanup(
        self, mock_hass: MagicMock, mock_coordinator: MagicMock
    ) -> None:
        """Test listen() subscribes to events and registers cleanup."""
        manager = MockManager(mock_hass, mock_coordinator)
        callback = AsyncMock()

        with patch(
            "custom_components.choreops.managers.base_manager.async_dispatcher_connect"
        ) as mock_connect:
            mock_unsub = MagicMock()
            mock_connect.return_value = mock_unsub

            manager.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, callback)

            # Verify dispatcher connect was called
            mock_connect.assert_called_once()

            # Verify correct signal
            expected_signal = get_event_signal(
                "test_entry_123", const.SIGNAL_SUFFIX_CHORE_APPROVED
            )
            assert mock_connect.call_args[0][1] == expected_signal

            # Verify callback was passed
            assert mock_connect.call_args[0][2] is callback

            # Verify cleanup was registered
            mock_coordinator.config_entry.async_on_unload.assert_called_once_with(
                mock_unsub
            )


class TestMultiInstanceIsolation:
    """Tests for multi-instance isolation via scoped signals."""

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock HomeAssistant instance."""
        return MagicMock()

    def test_different_instances_different_signals(self, mock_hass: MagicMock) -> None:
        """Test two instances use completely separate signal namespaces."""
        # Create two mock coordinators (two config entries)
        mock_coord_1 = MagicMock()
        mock_coord_1.config_entry.entry_id = "family_smith"
        mock_coord_1.config_entry.async_on_unload = MagicMock()

        mock_coord_2 = MagicMock()
        mock_coord_2.config_entry.entry_id = "family_jones"
        mock_coord_2.config_entry.async_on_unload = MagicMock()

        manager_1 = MockManager(mock_hass, mock_coord_1)
        manager_2 = MockManager(mock_hass, mock_coord_2)

        # Verify entry_ids are tracked correctly
        assert manager_1.entry_id == "family_smith"
        assert manager_2.entry_id == "family_jones"

        # Verify signals would be different
        signal_1 = get_event_signal(
            manager_1.entry_id, const.SIGNAL_SUFFIX_POINTS_CHANGED
        )
        signal_2 = get_event_signal(
            manager_2.entry_id, const.SIGNAL_SUFFIX_POINTS_CHANGED
        )

        assert signal_1 != signal_2
        assert "family_smith" in signal_1
        assert "family_jones" in signal_2

    def test_emit_uses_instance_scoped_signal(self, mock_hass: MagicMock) -> None:
        """Test emit() uses the manager's entry_id for signal scoping."""
        mock_coord = MagicMock()
        mock_coord.config_entry.entry_id = "unique_instance_xyz"
        mock_coord.config_entry.async_on_unload = MagicMock()

        manager = MockManager(mock_hass, mock_coord)

        with patch(
            "custom_components.choreops.managers.base_manager.async_dispatcher_send"
        ) as mock_send:
            manager.emit(const.SIGNAL_SUFFIX_BADGE_EARNED, badge_id="badge1")

            # Verify the signal contains this instance's entry_id
            actual_signal = mock_send.call_args[0][1]
            assert "unique_instance_xyz" in actual_signal
            assert const.SIGNAL_SUFFIX_BADGE_EARNED in actual_signal


class TestStartupCascade:
    """Tests for the startup cascade signal sequence.

    Verifies the "Infrastructure Coordinator" pattern:
    - Coordinator emits DATA_READY after integrity check
    - Managers chain: DATA_READY → CHORES_READY → STATS_READY → GAMIFICATION_READY
    """

    def test_lifecycle_signals_defined(self) -> None:
        """Verify all lifecycle signals are defined in const.py."""
        # Core cascade signals
        assert hasattr(const, "SIGNAL_SUFFIX_DATA_READY")
        assert hasattr(const, "SIGNAL_SUFFIX_CHORES_READY")
        assert hasattr(const, "SIGNAL_SUFFIX_STATS_READY")
        assert hasattr(const, "SIGNAL_SUFFIX_GAMIFICATION_READY")

        # Timer signals (SystemManager owns all timers)
        assert hasattr(const, "SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER")
        assert hasattr(const, "SIGNAL_SUFFIX_PERIODIC_UPDATE")

    def test_cascade_signal_values(self) -> None:
        """Verify signal values follow naming convention."""
        assert const.SIGNAL_SUFFIX_DATA_READY == "data_ready"
        assert const.SIGNAL_SUFFIX_CHORES_READY == "chores_ready"
        assert const.SIGNAL_SUFFIX_STATS_READY == "stats_ready"
        assert const.SIGNAL_SUFFIX_GAMIFICATION_READY == "gamification_ready"
        assert const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER == "midnight_rollover"
        assert const.SIGNAL_SUFFIX_PERIODIC_UPDATE == "periodic_update"

    def test_cascade_managers_have_ready_handlers(self) -> None:
        """Verify managers implement _on_*_ready handlers for cascade."""
        from custom_components.choreops.managers.chore_manager import ChoreManager
        from custom_components.choreops.managers.gamification_manager import (
            GamificationManager,
        )
        from custom_components.choreops.managers.statistics_manager import (
            StatisticsManager,
        )

        # ChoreManager listens to DATA_READY, emits CHORES_READY
        assert hasattr(ChoreManager, "_on_data_ready")

        # StatisticsManager listens to CHORES_READY, emits STATS_READY
        assert hasattr(StatisticsManager, "_on_chores_ready")

        # GamificationManager listens to STATS_READY, emits GAMIFICATION_READY
        assert hasattr(GamificationManager, "_on_stats_ready")
