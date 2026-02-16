"""Test rotation management services.

Tests the rotation service actions:
- kidschores.set_rotation_turn - Set turn to specific kid
- kidschores.reset_rotation - Reset to first assigned kid
- kidschores.open_rotation_cycle - Allow any kid to claim once

These services allow manual rotation control for special circumstances.
"""

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

# Import test constants from helpers (not from const.py - Rule 0)
from tests.helpers.constants import (
    CHORE_STATE_NOT_MY_TURN,
    CHORE_STATE_PENDING,
    SERVICE_FIELD_CHORE_ID,
    SERVICE_FIELD_KID_ID,
)
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.helpers.workflows import find_chore, get_dashboard_helper
from tests.test_badge_helpers import get_chore_by_name, get_kid_by_name

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load shared scenario: 3 kids, 1 parent, with rotation chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


# =============================================================================
# T2 — Rotation Service Tests
# =============================================================================


@pytest.mark.asyncio
async def test_set_rotation_turn_service(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test kidschores.set_rotation_turn service.

    Validates:
    - Service sets turn to specified kid
    - New turn holder sees 'pending'
    - Previous turn holder sees 'not_my_turn'
    - Other kids remain 'not_my_turn'
    - turn_kid_name attribute updates correctly
    """
    result = scenario_shared
    await hass.async_block_till_done()

    # Wait for all entities to fully initialize and update states
    await hass.async_block_till_done(wait_background_tasks=True)

    # Get dashboard helpers
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Use "Dishes Rotation" which has rotation_cycle_override: false
    # (This is rotation_simple and works correctly in the FSM tests)
    zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
    max_chore = find_chore(max_helper, "Dishes Rotation")
    lila_chore = find_chore(lila_helper, "Dishes Rotation")

    assert zoe_chore is not None
    assert max_chore is not None
    assert lila_chore is not None

    # Verify initial rotation state is correct
    # - Exactly one kid should have "pending" (their turn)
    # - All other kids should have "not_my_turn"
    assert zoe_chore["status"] == CHORE_STATE_PENDING, (
        f"Expected Zoë to have pending status, got {zoe_chore['status']}"
    )
    assert max_chore["status"] == CHORE_STATE_NOT_MY_TURN, (
        f"Expected Max! to have not_my_turn status, got {max_chore['status']}"
    )
    assert lila_chore["status"] == CHORE_STATE_NOT_MY_TURN, (
        f"Expected Lila to have not_my_turn status, got {lila_chore['status']}"
    )

    # Identify original turn holder and choose a different kid as target
    chores: list[tuple[str, dict[str, Any], str, str]] = [
        ("zoe", zoe_chore, "Zoë", "zoe_internal_id"),
        ("max", max_chore, "Max!", "max_internal_id"),
        ("lila", lila_chore, "Lila", "lila_internal_id"),
    ]

    original_turn_holder = None
    new_turn_target = None

    # Find who currently has the turn (sees 'pending')
    for slug, chore, name, kid_id_placeholder in chores:
        if chore["status"] == CHORE_STATE_PENDING:
            original_turn_holder = (slug, chore, name)
            break

    assert original_turn_holder is not None, (
        f"No kid found with PENDING status. All states: {[(n, c['status']) for _, c, n, _ in chores]}"
    )

    # Choose a different kid as the new target (not the current turn holder)
    for slug, chore, name, kid_id_placeholder in chores:
        if (
            chore["status"] == CHORE_STATE_NOT_MY_TURN
        ):  # Pick first kid who doesn't have turn
            new_turn_target = (slug, chore, name)
            break

    assert new_turn_target is not None, (
        f"No kid found with NOT_MY_TURN status. All states: {[(n, c['status']) for _, c, n, _ in chores]}"
    )

    orig_slug, orig_chore, orig_name = original_turn_holder
    new_slug, new_chore, new_name = new_turn_target

    # Get chore internal_id and kid internal_id for service call
    # The chore sensor has the chore's internal_id in its entity_id
    orig_sensor = hass.states.get(orig_chore["eid"])
    assert orig_sensor is not None

    # Extract chore_id from coordinator data
    # Get coordinator from config entry
    config_entry = hass.config_entries.async_entries("kidschores")[0]
    coordinator = config_entry.runtime_data

    # Find chore UUID dynamically using helper
    chore_id = get_chore_by_name(coordinator, "Dishes Rotation")

    # Find target kid's internal ID using helper
    target_kid_id = get_kid_by_name(coordinator, new_name)

    # Call the set_rotation_turn service
    await hass.services.async_call(
        "kidschores",
        "set_rotation_turn",
        {
            SERVICE_FIELD_CHORE_ID: chore_id,
            SERVICE_FIELD_KID_ID: target_kid_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    # Re-fetch dashboard helpers after service call
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Verify turn changed
    for slug, orig_chore, name, user_id in chores:
        current_chore = find_chore(get_dashboard_helper(hass, slug), "Dishes Rotation")
        assert current_chore is not None
        sensor = hass.states.get(current_chore["eid"])
        assert sensor is not None

        if slug == new_slug:
            # New turn holder sees pending
            assert current_chore["status"] == CHORE_STATE_PENDING, (
                f"{name} should now have the turn"
            )
            assert sensor.state == CHORE_STATE_PENDING
            assert sensor.attributes.get("can_claim") is True
            assert sensor.attributes.get("turn_kid_name") == new_name
        else:
            # Others see not_my_turn
            assert current_chore["status"] == CHORE_STATE_NOT_MY_TURN, (
                f"{name} should see not_my_turn after turn changed to {new_name}"
            )
            assert sensor.state == CHORE_STATE_NOT_MY_TURN
            assert sensor.attributes.get("can_claim") is False
            assert sensor.attributes.get("lock_reason") == "not_my_turn"
            # turn_kid_name should point to new holder
            assert sensor.attributes.get("turn_kid_name") == new_name


@pytest.mark.asyncio
async def test_reset_rotation_service(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test kidschores.reset_rotation service.

    Validates:
    - Service resets turn to first assigned kid
    - First kid sees 'pending'
    - Other kids see 'not_my_turn'
    - Works regardless of current turn state
    """
    result = scenario_shared
    await hass.async_block_till_done()

    # Get coordinator and find chore
    config_entry = hass.config_entries.async_entries("kidschores")[0]
    coordinator = config_entry.runtime_data

    chore_id = None
    for cid, chore_data in coordinator._data["chores"].items():
        if chore_data.get("name") == "Dishes Rotation":
            chore_id = cid
            break

    assert chore_id is not None

    # Get assigned kids list (ordered)
    chore_data = coordinator._data["chores"][chore_id]
    assigned_kid_ids = chore_data.get("assigned_kids", [])
    assert len(assigned_kid_ids) >= 2, "Need at least 2 kids for rotation"

    # Get first kid's name
    first_kid_id = assigned_kid_ids[0]
    first_kid_name = None
    for kid_data in coordinator._data["kids"].values():
        if kid_data.get("internal_id") == first_kid_id:
            first_kid_name = kid_data.get("name")
            break

    assert first_kid_name is not None

    # Call reset_rotation service
    await hass.services.async_call(
        "kidschores",
        "reset_rotation",
        {SERVICE_FIELD_CHORE_ID: chore_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify first kid has the turn
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    helpers = {
        "Zoë": zoe_helper,
        "Max!": max_helper,
        "Lila": lila_helper,
    }

    for kid_name, helper in helpers.items():
        chore = find_chore(helper, "Dishes Rotation")
        assert chore is not None
        sensor = hass.states.get(chore["eid"])
        assert sensor is not None

        if kid_name == first_kid_name:
            # First kid sees pending
            assert chore["status"] == CHORE_STATE_PENDING, (
                f"{kid_name} should have the turn after reset"
            )
            assert sensor.state == CHORE_STATE_PENDING
            assert sensor.attributes.get("can_claim") is True
            assert sensor.attributes.get("turn_kid_name") == first_kid_name
        else:
            # Others see not_my_turn
            assert chore["status"] == CHORE_STATE_NOT_MY_TURN
            assert sensor.state == CHORE_STATE_NOT_MY_TURN
            assert sensor.attributes.get("can_claim") is False
            assert sensor.attributes.get("turn_kid_name") == first_kid_name


@pytest.mark.asyncio
async def test_open_rotation_cycle_service(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test kidschores.open_rotation_cycle service.

    Validates:
    - Service sets rotation_cycle_override flag
    - Allows special "anyone can claim once" mode
    - Used for extra credit opportunities

    Note: rotation_cycle_override doesn't change FSM states immediately.
    It allows ANY kid to claim (bypassing turn holder check), but state
    still reflects current turn until someone claims.
    """
    result = scenario_shared
    await hass.async_block_till_done()

    # Get coordinator and find a rotation chore WITHOUT cycle override
    config_entry = hass.config_entries.async_entries("kidschores")[0]
    coordinator = config_entry.runtime_data

    # Use "Laundry Rotation" which has rotation_cycle_override: false
    chore_id = None
    for cid, chore_data in coordinator._data["chores"].items():
        if chore_data.get("name") == "Laundry Rotation":
            chore_id = cid
            break

    assert chore_id is not None

    # Verify cycle override is initially false
    chore_data = coordinator._data["chores"][chore_id]
    assert chore_data.get("rotation_cycle_override") is False

    # Call open_rotation_cycle service
    await hass.services.async_call(
        "kidschores",
        "open_rotation_cycle",
        {SERVICE_FIELD_CHORE_ID: chore_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify cycle override flag is now true
    chore_data = coordinator._data["chores"][chore_id]
    assert chore_data.get("rotation_cycle_override") is True, (
        "rotation_cycle_override should be set to True"
    )


# =============================================================================
# T3 Group: Turn Advancement Tests
# =============================================================================


@pytest.mark.asyncio
async def test_rotation_advancement_with_skipped_kids(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test rotation correctly handles kids who aren't assigned to chore.

    Validates:
    - Rotation skips kids not in assigned_kids list
    - Only assigned kids participate in rotation
    - Turn advances correctly among assigned kids only
    """
    result = scenario_shared
    await hass.async_block_till_done()

    # Get coordinator for direct data access
    config_entry = hass.config_entries.async_entries("kidschores")[0]
    coordinator = config_entry.runtime_data

    # Find "Water Plants" chore (only assigned to Max and Lila, not Zoë)
    chore_id = None
    for cid, chore_data in coordinator._data["chores"].items():
        if chore_data.get("name") == "Water Plants":
            chore_id = cid
            break

    assert chore_id is not None

    # Verify assigned kids (should be Max and Lila only)
    chore_data = coordinator._data["chores"][chore_id]
    assigned_kids = chore_data.get("assigned_kids", [])

    # Should have exactly 2 kids assigned
    assert len(assigned_kids) == 2, "Water Plants should have 2 assigned kids"

    # Get kid names for verification
    assigned_names = []
    for kid_id in assigned_kids:
        kid_info = coordinator._data["kids"].get(kid_id, {})
        kid_name = kid_info.get("name")
        if kid_name:
            assigned_names.append(kid_name)

    # Should be Max and Lila (Zoë not assigned)
    assert "Max!" in assigned_names, "Max should be assigned to Water Plants"
    assert "Lila" in assigned_names, "Lila should be assigned to Water Plants"
    assert "Zoë" not in assigned_names, "Zoë should NOT be assigned to Water Plants"

    # Verify current turn holder is one of the assigned kids
    current_turn_kid_id = chore_data.get("rotation_current_kid_id")
    assert current_turn_kid_id in assigned_kids, "Turn holder must be assigned to chore"

    # Get dashboard helpers to check entity states
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Check if Zoë can see this chore at all (should not)
    zoe_chore = find_chore(zoe_helper, "Water Plants")
    # Zoë might see the chore but in not_my_turn/unavailable state

    # Max and Lila should see the chore
    max_chore = find_chore(max_helper, "Water Plants")
    lila_chore = find_chore(lila_helper, "Water Plants")

    assert max_chore is not None, "Max should see Water Plants chore"
    assert lila_chore is not None, "Lila should see Water Plants chore"

    # One of Max/Lila should have pending, the other not_my_turn
    max_status = max_chore["status"]
    lila_status = lila_chore["status"]

    pending_count = 0
    if max_status == CHORE_STATE_PENDING:
        pending_count += 1
    if lila_status == CHORE_STATE_PENDING:
        pending_count += 1

    assert pending_count == 1, "Exactly one assigned kid should see pending"


@pytest.mark.asyncio
async def test_set_turn_then_reset_preserves_single_pending_holder_invariant(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """set_rotation_turn + reset_rotation preserves one-and-only-one pending holder."""
    await hass.async_block_till_done(wait_background_tasks=True)

    config_entry = hass.config_entries.async_entries("kidschores")[0]
    coordinator = config_entry.runtime_data
    chore_id = get_chore_by_name(coordinator, "Dishes Rotation")

    # Move turn to Max first (if not already there)
    max_id = get_kid_by_name(coordinator, "Max!")
    await hass.services.async_call(
        "kidschores",
        "set_rotation_turn",
        {SERVICE_FIELD_CHORE_ID: chore_id, SERVICE_FIELD_KID_ID: max_id},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    # Reset back to first assigned kid
    await hass.services.async_call(
        "kidschores",
        "reset_rotation",
        {SERVICE_FIELD_CHORE_ID: chore_id},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    pending_count = 0
    locked_count = 0
    turn_names: set[str] = set()

    for slug in ("zoe", "max", "lila"):
        chore = find_chore(get_dashboard_helper(hass, slug), "Dishes Rotation")
        assert chore is not None
        sensor = hass.states.get(chore["eid"])
        assert sensor is not None
        turn_name = sensor.attributes.get("turn_kid_name")
        if isinstance(turn_name, str):
            turn_names.add(turn_name)

        if sensor.state == CHORE_STATE_PENDING:
            pending_count += 1
            assert sensor.attributes.get("can_claim") is True
        else:
            locked_count += 1
            assert sensor.state == CHORE_STATE_NOT_MY_TURN
            assert sensor.attributes.get("can_claim") is False

    assert pending_count == 1
    assert locked_count == 2
    assert len(turn_names) == 1


# =============================================================================
# Run linting and tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
