"""Test entity loading extension for all entity types via config flow.

This test validates Phase 12 Step 7 implementation: extending setup_from_yaml()
to support badges, rewards, penalties, bonuses, achievements, and challenges.
"""

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers.setup import setup_from_yaml


@pytest.mark.usefixtures("mock_hass_users")
async def test_scenario_full_loads_all_entity_types(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that scenario_full.yaml loads all entity types successfully.

    Validates:
    - All 6 new entity types load via config flow
    - ID mappings populated in SetupResult
    - Coordinator data contains all entities
    - Entity names match YAML configuration
    """
    # Load comprehensive scenario with all entity types
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )

    # Verify assignees (baseline - already worked)
    assert len(result.assignee_ids) == 3
    assert "Zoë" in result.assignee_ids
    assert "Max!" in result.assignee_ids
    assert "Lila" in result.assignee_ids

    # Verify configured approvers are present. approver_ids may also include
    # approver-compatible linked-profile records from unified users data.
    assert len(result.approver_ids) >= 2
    assert "Môm Astrid Stârblüm" in result.approver_ids
    assert "Dad Leo" in result.approver_ids

    # Verify chores (baseline - already worked)
    # Note: scenario_full.yaml currently has 18 chores (was 19 before recent updates)
    assert len(result.chore_ids) == 18
    assert "Feed the cåts" in result.chore_ids
    assert "Wåsh Family Car" in result.chore_ids

    # =========================================================================
    # NEW ENTITY TYPES (Phase 12 Step 7 Implementation)
    # =========================================================================

    # Verify badges loaded (2 from scenario_full.yaml)
    assert len(result.badge_ids) == 2
    assert "Chore Stär Champion" in result.badge_ids
    assert "Team Player Badge" in result.badge_ids

    # Verify rewards loaded (3 from scenario_full.yaml)
    assert len(result.reward_ids) == 3
    assert "Extra Screen Time" in result.reward_ids
    assert "Pick Next Movie" in result.reward_ids
    assert "Special Outing" in result.reward_ids

    # Verify penalties loaded (2 from scenario_full.yaml)
    assert len(result.penalty_ids) == 2
    assert "Missed Chore" in result.penalty_ids
    assert "Sibling Fight" in result.penalty_ids

    # Verify bonuses loaded (2 from scenario_full.yaml)
    assert len(result.bonus_ids) == 2
    assert "Extra Effort" in result.bonus_ids
    assert "Helping Sibling" in result.bonus_ids

    # Verify achievements loaded (2 from scenario_full.yaml)
    assert len(result.achievement_ids) == 2
    assert "Early Bird" in result.achievement_ids
    assert "Chore Champion" in result.achievement_ids

    # Verify challenges loaded (2 from scenario_full.yaml)
    assert len(result.challenge_ids) == 2
    assert "Weekend Warrior" in result.challenge_ids
    assert "Summer Sprint" in result.challenge_ids

    # =========================================================================
    # COORDINATOR DATA VALIDATION
    # =========================================================================

    coordinator = result.coordinator

    # Verify coordinator has all entity data
    assert len(coordinator.badges_data) == 2
    assert len(coordinator.rewards_data) == 3
    assert len(coordinator.penalties_data) == 2
    assert len(coordinator.bonuses_data) == 2
    assert len(coordinator.achievements_data) == 2
    assert len(coordinator.challenges_data) == 2

    # Spot-check: Verify specific badge data loaded correctly
    chore_star_badge_id = result.badge_ids["Chore Stär Champion"]
    badge_data = coordinator.badges_data[chore_star_badge_id]
    assert badge_data["name"] == "Chore Stär Champion"
    assert badge_data["badge_type"] == "cumulative"
    # award_points is nested under "awards" dict in storage format
    assert badge_data["awards"]["award_points"] == 50.0

    # Spot-check: Verify specific reward data loaded correctly
    screen_time_reward_id = result.reward_ids["Extra Screen Time"]
    reward_data = coordinator.rewards_data[screen_time_reward_id]
    assert reward_data["name"] == "Extra Screen Time"
    assert reward_data["cost"] == 50
    assert reward_data["description"] == "30 minutes extra screen time"

    # Spot-check: Verify specific penalty data loaded correctly
    missed_chore_penalty_id = result.penalty_ids["Missed Chore"]
    penalty_data = coordinator.penalties_data[missed_chore_penalty_id]
    assert penalty_data["name"] == "Missed Chore"
    assert penalty_data["points"] == -10  # Stored as negative

    # Spot-check: Verify specific bonus data loaded correctly
    extra_effort_bonus_id = result.bonus_ids["Extra Effort"]
    bonus_data = coordinator.bonuses_data[extra_effort_bonus_id]
    assert bonus_data["name"] == "Extra Effort"
    assert bonus_data["points"] == 20

    # Spot-check: Verify specific achievement data loaded correctly
    early_bird_achievement_id = result.achievement_ids["Early Bird"]
    achievement_data = coordinator.achievements_data[early_bird_achievement_id]
    assert achievement_data["name"] == "Early Bird"
    assert achievement_data["type"] == "chore_total"  # Achievement type, not name
    assert achievement_data["reward_points"] == 25.0

    # Spot-check: Verify specific challenge data loaded correctly
    weekend_warrior_challenge_id = result.challenge_ids["Weekend Warrior"]
    challenge_data = coordinator.challenges_data[weekend_warrior_challenge_id]
    assert challenge_data["name"] == "Weekend Warrior"
    assert challenge_data["type"] == "daily_minimum"  # Challenge type, not name
    assert challenge_data["reward_points"] == 50.0


@pytest.mark.usefixtures("mock_hass_users")
async def test_entity_loading_with_empty_lists(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that entity loading works when some entity types are empty.

    Validates:
    - Empty entity lists don't break config flow
    - ID mappings are empty dicts (not None)
    - Coordinator data structures exist but are empty
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",  # Has no badges/rewards/etc
    )

    # Minimal scenario should have 1 assignee, configured approver present, 5 chores
    # (approver_ids may include approver-compatible linked-profile records)
    assert len(result.assignee_ids) == 1
    assert len(result.approver_ids) >= 1
    assert "Môm Astrid Stârblüm" in result.approver_ids
    assert len(result.chore_ids) == 5

    # All new entity ID mappings should be empty dicts (not None)
    assert result.badge_ids == {}
    assert result.reward_ids == {}
    assert result.penalty_ids == {}
    assert result.bonus_ids == {}
    assert result.achievement_ids == {}
    assert result.challenge_ids == {}

    # Coordinator data structures should exist but be empty
    coordinator = result.coordinator
    assert coordinator.badges_data == {}
    assert coordinator.rewards_data == {}
    assert coordinator.penalties_data == {}
    assert coordinator.bonuses_data == {}
    assert coordinator.achievements_data == {}
    assert coordinator.challenges_data == {}
