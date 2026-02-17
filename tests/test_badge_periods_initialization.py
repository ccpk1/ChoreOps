"""Test badge period structure initialization and signal flow.

Tests the Landlord-Tenant pattern for badge earned period tracking:
- GamificationManager (Landlord) creates empty periods: {} before emitting signal
- StatisticsManager (Tenant) populates period data via record_transaction

These tests verify the ACTUAL BUG that was found in production:
- Bronze badge was awarded with periods: {} (empty dict)
- Signal was not emitted OR handler was not triggered OR record_transaction failed
- This file tests each step of the flow to isolate the root cause

Uses scenario_full (Stårblüm family) from test_badge_helpers.py pattern.
"""

from homeassistant.core import HomeAssistant

from custom_components.choreops import const

# Note: We import from const.py for attribute keys (not tests.helpers)
from tests.test_badge_helpers import (
    get_badge_by_name,
    get_kid_by_name,
    setup_badges,  # noqa: F401 - pytest fixture
)

# ============================================================================
# SECTION 1: LANDLORD-TENANT PATTERN TESTS
# ============================================================================


class TestBadgePeriodStructureCreation:
    """Test that badge period structures follow Landlord-Tenant pattern."""

    async def test_ensure_kid_badge_structures_creates_empty_periods(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test Landlord creates empty periods dict before Tenant populates.

        Landlord (GamificationManager) responsibility:
        - Create badge entry with empty periods: {}
        - Call _ensure_kid_badge_structures before persist
        - Emit BADGE_EARNED signal AFTER persist

        This test verifies Step 1 of the contract.
        """
        coordinator = setup_badges.coordinator

        # Get Zoë (has cumulative badges in scenario_full)
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        zoe_data = coordinator._data[const.DATA_KIDS][zoe_id]

        # Get Chore Stär Champion badge ID
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        # Manually create badge entry WITHOUT periods (simulate pre-fix bug)
        badges_earned = zoe_data.setdefault(const.DATA_KID_BADGES_EARNED, {})
        badges_earned[champion_id] = {
            const.DATA_KID_BADGES_EARNED_NAME: "Chore Stär Champion",
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED: "2026-02-11",
            # Intentionally missing periods key to test structure creation
        }

        # Call Landlord's structure creation method
        coordinator.gamification_manager._ensure_kid_badge_structures(
            zoe_id, champion_id
        )

        # Verify Landlord created ONLY empty dict (Tenant populates later)
        champion_entry = badges_earned[champion_id]
        assert const.DATA_KID_BADGES_EARNED_PERIODS in champion_entry, (
            "Landlord should create periods key"
        )

        periods = champion_entry[const.DATA_KID_BADGES_EARNED_PERIODS]
        assert isinstance(periods, dict), "periods should be dict type"
        assert periods == {}, (
            "Landlord should create ONLY empty dict, Tenant populates via signal"
        )
