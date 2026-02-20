"""Shared helpers and fixtures for badge tests.

This module provides common utilities used across all badge type test files:
- test_badge_cumulative.py - Cumulative badges (lifetime points tracking)
- test_badge_daily.py - Daily badges (placeholder)
- test_badge_periodic.py - Periodic badges (placeholder)
- test_badge_special_occasion.py - Special occasion badges (placeholder)
- test_badge_achievement_linked.py - Achievement-linked badges (placeholder)
- test_badge_challenge_linked.py - Challenge-linked badges (placeholder)

Badge Types Overview:
--------------------
CUMULATIVE BADGES:
- Track TOTAL LIFETIME POINTS EARNED (not current balance)
- Points earned = sum of all points ever received (chores, bonuses, etc.)
- NOT reduced by reward purchases or penalties
- Target: threshold_value (e.g., 500 = earn 500+ total points to unlock)
- Rewards: Can award bonus points AND/OR an ongoing points multiplier
- The ONLY badge type that can award a multiplier

DAILY BADGES:
- Track daily activity (chores completed per day)
- Reset at midnight
- Target: daily chore completion count
- Rewards: Points only

PERIODIC BADGES:
- Track activity within a time window (start_date to end_date)
- Can track specific chores or all chores
- Target: chore completion count within period
- Rewards: Points only (no multiplier)

SPECIAL OCCASION BADGES:
- One-time badges for special events
- Manually awarded or triggered by specific conditions
- Target: None (event-based)
- Rewards: Points only

ACHIEVEMENT-LINKED BADGES:
- Automatically awarded when achievement is unlocked
- Linked to specific achievement by ID
- Target: Achievement completion
- Rewards: Points only

CHALLENGE-LINKED BADGES:
- Automatically awarded when challenge is completed
- Linked to specific challenge by ID
- Target: Challenge completion
- Rewards: Points only
"""

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers.setup import SetupResult, setup_from_yaml

# ============================================================================
# SHARED FIXTURES
# ============================================================================


@pytest.fixture
async def setup_badges(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up badge testing scenario using scenario_full (Stårblüm family).

    Provides:
    - 2 cumulative badges:
      - "Chore Stär Champion" (Zoë): threshold=100 total points earned
      - "Team Player Badge" (Max!, Lila): threshold=500 total points earned
    - 3 kids: Zoë, Max!, Lila
    - 18 chores with various points
    - 2 bonuses: "Extra Effort" (20pts), "Helping Sibling" (15pts)
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_kid_by_name(coordinator: Any, kid_name: str) -> str:
    """Get kid internal_id by name.

    Args:
        coordinator: KidsChoresCoordinator instance
        kid_name: Display name of the kid (e.g., "Zoë", "Max!")

    Returns:
        Kid's internal_id (UUID string)

    Raises:
        ValueError: If kid not found
    """
    for kid_id, kid_data in coordinator.kids_data.items():
        if kid_data.get("name") == kid_name:
            return kid_id
    raise ValueError(f"Kid not found: {kid_name}")


def get_chore_by_name(coordinator: Any, chore_name: str) -> str:
    """Get chore internal_id by name.

    Args:
        coordinator: KidsChoresCoordinator instance
        chore_name: Display name of the chore

    Returns:
        Chore's internal_id (UUID string)

    Raises:
        ValueError: If chore not found
    """
    for chore_id, chore_data in coordinator.chores_data.items():
        if chore_data.get("name") == chore_name:
            return chore_id
    raise ValueError(f"Chore not found: {chore_name}")


def get_badge_by_name(coordinator: Any, badge_name: str) -> str:
    """Get badge internal_id by name.

    Args:
        coordinator: KidsChoresCoordinator instance
        badge_name: Display name of the badge

    Returns:
        Badge's internal_id (UUID string)

    Raises:
        ValueError: If badge not found
    """
    for badge_id, badge_data in coordinator.badges_data.items():
        if badge_data.get("name") == badge_name:
            return badge_id
    raise ValueError(f"Badge not found: {badge_name}")


def get_bonus_by_name(coordinator: Any, bonus_name: str) -> str:
    """Get bonus internal_id by name.

    Args:
        coordinator: KidsChoresCoordinator instance
        bonus_name: Display name of the bonus

    Returns:
        Bonus's internal_id (UUID string)

    Raises:
        ValueError: If bonus not found
    """
    for bonus_id, bonus_data in coordinator.bonuses_data.items():
        if bonus_data.get("name") == bonus_name:
            return bonus_id
    raise ValueError(f"Bonus not found: {bonus_name}")


def get_dashboard_helper_eid(hass: HomeAssistant, kid_name: str) -> str:
    """Get dashboard helper entity ID for a kid by name.

    Args:
        hass: Home Assistant instance
        kid_name: Display name of the kid

    Returns:
        Entity ID of the kid's dashboard helper sensor

    Raises:
        ValueError: If dashboard helper not found
    """
    # Slugify the kid name (lowercase, replace special chars)
    slug = (
        kid_name.lower()
        .replace("!", "")
        .replace("ë", "e")
        .replace("å", "a")
        .replace("ü", "u")
    )
    for eid in (
        f"sensor.{slug}_choreops_ui_dashboard_helper",
        f"sensor.{slug}_kidschores_ui_dashboard_helper",
    ):
        state = hass.states.get(eid)
        if state:
            return eid
    raise ValueError(f"Dashboard helper not found for kid: {kid_name}")


def find_chore_in_dashboard(
    hass: HomeAssistant, dashboard_helper_eid: str, chore_name: str
) -> dict[str, Any]:
    """Find chore info in dashboard helper attributes.

    Args:
        hass: Home Assistant instance
        dashboard_helper_eid: Entity ID of dashboard helper sensor
        chore_name: Display name of the chore to find

    Returns:
        Dictionary with chore info including 'eid', 'name', etc.

    Raises:
        ValueError: If dashboard helper or chore not found
    """
    helper_state = hass.states.get(dashboard_helper_eid)
    if not helper_state:
        raise ValueError(f"Dashboard helper not found: {dashboard_helper_eid}")
    chores_list = helper_state.attributes.get("chores", [])
    for chore in chores_list:
        if chore.get("name") == chore_name:
            return chore
    raise ValueError(f"Chore not found in dashboard: {chore_name}")
