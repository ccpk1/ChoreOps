"""Test rotation chore FSM state transitions.

Tests the core rotation logic for turn-based chores:
- Turn holder identification
- NOT_MY_TURN blocking
- State transitions (pending → claimed → approved)
- Rotation advancement at boundaries
"""

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from custom_components.kidschores.utils.dt_utils import dt_now_utc

# Import test constants from helpers (not from const.py - Rule 0)
from tests.helpers.constants import (
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_NOT_MY_TURN,
    CHORE_STATE_PENDING,
)
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.helpers.workflows import find_chore, get_dashboard_helper

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
# T1 — Rotation Turn Holder Tests
# =============================================================================


@pytest.mark.asyncio
async def test_rotation_turn_holder_can_claim(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that only the current turn holder can claim a rotation chore.

    Validates:
    - Turn holder sees status = 'pending'
    - Turn holder has can_claim = True
    - Non-turn holders see status = 'not_my_turn'
    - Non-turn holders have can_claim = False with lock_reason = 'not_my_turn'
    """
    result = scenario_shared
    await hass.async_block_till_done()

    # Get dashboard helpers for all kids
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Find the rotation chore "Dishes Rotation"
    zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
    max_chore = find_chore(max_helper, "Dishes Rotation")
    lila_chore = find_chore(lila_helper, "Dishes Rotation")

    assert zoe_chore is not None
    assert max_chore is not None
    assert lila_chore is not None

    # Identify turn holder by checking status
    chores = [
        (zoe_chore, "Zoë", "zoe"),
        (max_chore, "Max!", "max"),
        (lila_chore, "Lila", "lila"),
    ]

    turn_holder = None
    non_turn_holders = []

    for chore, name, slug in chores:
        if chore["status"] == CHORE_STATE_PENDING:
            turn_holder = (chore, name, slug)
        else:
            assert chore["status"] == CHORE_STATE_NOT_MY_TURN, (
                f"{name} should see not_my_turn"
            )
            non_turn_holders.append((chore, name, slug))

    assert turn_holder is not None, "Should have exactly one turn holder"
    assert len(non_turn_holders) == 2, "Should have two non-turn holders"

    # Verify turn holder can claim
    turn_chore, turn_name, turn_slug = turn_holder
    turn_sensor = hass.states.get(turn_chore["eid"])
    assert turn_sensor is not None
    assert turn_sensor.state == CHORE_STATE_PENDING
    assert turn_sensor.attributes.get("can_claim") is True, (
        f"{turn_name} should be able to claim"
    )
    assert turn_sensor.attributes.get("lock_reason") is None
    assert turn_sensor.attributes.get("turn_kid_name") == turn_name

    # Verify non-turn holders are blocked
    for chore, name, slug in non_turn_holders:
        sensor = hass.states.get(chore["eid"])
        assert sensor is not None
        assert sensor.state == CHORE_STATE_NOT_MY_TURN
        assert sensor.attributes.get("can_claim") is False, (
            f"{name} should not be able to claim"
        )
        assert sensor.attributes.get("lock_reason") == "not_my_turn"
        assert sensor.attributes.get("turn_kid_name") == turn_name


@pytest.mark.asyncio
async def test_rotation_approved_does_not_advance_immediately(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that rotation does NOT advance immediately after approval.

    When a turn holder completes their turn:
    - Turn holder sees status = 'approved'
    - Other kids continue to see 'not_my_turn' (rotation locked until boundary)
    - turn_kid_name remains unchanged
    - Rotation advances at the next boundary reset (e.g., midnight)

    This is the core behavior difference from shared chores.
    """
    from homeassistant.core import Context

    from tests.helpers.workflows import approve_chore, claim_chore

    result = scenario_shared
    await hass.async_block_till_done()

    # Get dashboard helpers
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Find chores
    zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
    max_chore = find_chore(max_helper, "Dishes Rotation")
    lila_chore = find_chore(lila_helper, "Dishes Rotation")

    assert zoe_chore is not None
    assert max_chore is not None
    assert lila_chore is not None

    # Identify turn holder
    chores: list[tuple[str, dict[str, Any], str, str]] = [
        ("zoe", zoe_chore, "Zoë", mock_hass_users["kid1"].id),
        ("max", max_chore, "Max!", mock_hass_users["kid2"].id),
        ("lila", lila_chore, "Lila", mock_hass_users["kid3"].id),
    ]

    turn_holder: tuple[str, dict[str, Any], str, str] | None = None
    for item in chores:
        slug, chore, name, user_id = item
        if chore["status"] == CHORE_STATE_PENDING:
            turn_holder = item
            break

    assert turn_holder is not None
    turn_slug, turn_chore_dict, turn_name, turn_user_id = turn_holder

    # Step 1: Turn holder claims the chore
    kid_context = Context(user_id=turn_user_id)
    await claim_chore(hass, turn_slug, "Dishes Rotation", context=kid_context)
    await hass.async_block_till_done()

    # Step 2: Parent approves the chore
    parent_context = Context(user_id=mock_hass_users["parent1"].id)
    await approve_chore(hass, turn_slug, "Dishes Rotation", context=parent_context)
    await hass.async_block_till_done()

    # Step 3: Verify state after approval - rotation has NOT advanced
    # Re-fetch dashboard helpers after state changes
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
    max_chore = find_chore(max_helper, "Dishes Rotation")
    lila_chore = find_chore(lila_helper, "Dishes Rotation")

    # Only the turn holder should see 'approved'
    # Others remain 'not_my_turn' because rotation hasn't advanced yet
    for slug, chore, name, user_id in chores:
        current_chore = find_chore(get_dashboard_helper(hass, slug), "Dishes Rotation")
        assert current_chore is not None
        sensor = hass.states.get(current_chore["eid"])
        assert sensor is not None

        if slug == turn_slug:
            # Turn holder sees approved
            assert current_chore["status"] == CHORE_STATE_APPROVED, (
                f"{name} completed their turn"
            )
            assert sensor.state == CHORE_STATE_APPROVED
            assert sensor.attributes.get("can_claim") is False
            assert sensor.attributes.get("lock_reason") is None
        else:
            # Others still blocked by not_my_turn
            assert current_chore["status"] == CHORE_STATE_NOT_MY_TURN, (
                f"{name} still blocked"
            )
            assert sensor.state == CHORE_STATE_NOT_MY_TURN
            assert sensor.attributes.get("can_claim") is False
            assert sensor.attributes.get("lock_reason") == "not_my_turn"

        # turn_kid_name remains unchanged for all
        assert sensor.attributes.get("turn_kid_name") == turn_name


@pytest.mark.asyncio
async def test_rotation_claimed_state(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test rotation chore in claimed state.

    Validates:
    - Turn holder sees status = 'claimed' after claiming
    - Turn holder has can_claim = False (already claimed)
    - Non-turn holders still see 'not_my_turn'
    - claimed_by attribute is set correctly
    """
    from homeassistant.core import Context

    from tests.helpers.workflows import claim_chore

    result = scenario_shared
    await hass.async_block_till_done()

    # Get dashboard helpers
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Find chores
    zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
    max_chore = find_chore(max_helper, "Dishes Rotation")
    lila_chore = find_chore(lila_helper, "Dishes Rotation")

    assert zoe_chore is not None
    assert max_chore is not None
    assert lila_chore is not None

    # Identify turn holder
    chores: list[tuple[str, dict[str, Any], str, str]] = [
        ("zoe", zoe_chore, "Zoë", mock_hass_users["kid1"].id),
        ("max", max_chore, "Max!", mock_hass_users["kid2"].id),
        ("lila", lila_chore, "Lila", mock_hass_users["kid3"].id),
    ]

    turn_holder: tuple[str, dict[str, Any], str, str] | None = None
    for item in chores:
        slug, chore, name, user_id = item
        if chore["status"] == CHORE_STATE_PENDING:
            turn_holder = item
            break

    assert turn_holder is not None
    turn_slug, turn_chore_dict, turn_name, turn_user_id = turn_holder

    # Turn holder claims the chore
    kid_context = Context(user_id=turn_user_id)
    await claim_chore(hass, turn_slug, "Dishes Rotation", context=kid_context)
    await hass.async_block_till_done()

    # Re-fetch dashboard helpers after state change
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
    max_chore = find_chore(max_helper, "Dishes Rotation")
    lila_chore = find_chore(lila_helper, "Dishes Rotation")

    # Verify turn holder sees 'claimed'
    for slug, chore, name, user_id in chores:
        current_chore = find_chore(get_dashboard_helper(hass, slug), "Dishes Rotation")
        assert current_chore is not None
        sensor = hass.states.get(current_chore["eid"])
        assert sensor is not None

        if slug == turn_slug:
            # Turn holder sees claimed
            assert current_chore["status"] == CHORE_STATE_CLAIMED, (
                f"{name} should see claimed"
            )
            assert sensor.state == CHORE_STATE_CLAIMED
            assert sensor.attributes.get("can_claim") is False  # Already claimed
            assert sensor.attributes.get("lock_reason") is None
            # claimed_by should be set (kid's display name)
            claimed_by = sensor.attributes.get("claimed_by")
            assert claimed_by == turn_name, f"Expected claimed_by={turn_name}"
        else:
            # Others still blocked by not_my_turn
            assert current_chore["status"] == CHORE_STATE_NOT_MY_TURN, (
                f"{name} still blocked"
            )
            assert sensor.state == CHORE_STATE_NOT_MY_TURN
            assert sensor.attributes.get("can_claim") is False
            assert sensor.attributes.get("lock_reason") == "not_my_turn"

        # turn_kid_name remains unchanged
        assert sensor.attributes.get("turn_kid_name") == turn_name


@pytest.mark.asyncio
async def test_rotation_non_turn_holder_cannot_claim(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that non-turn holders cannot claim rotation chore.

    Validates NOT_MY_TURN enforcement:
    - Non-turn holder attempts to claim
    - Chore remains in 'pending' state (claim rejected)
    - Turn holder still has exclusive access
    """
    from homeassistant.core import Context

    from tests.helpers.workflows import claim_chore

    result = scenario_shared
    await hass.async_block_till_done()

    # Get dashboard helpers
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Find chores
    zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
    max_chore = find_chore(max_helper, "Dishes Rotation")
    lila_chore = find_chore(lila_helper, "Dishes Rotation")

    assert zoe_chore is not None
    assert max_chore is not None
    assert lila_chore is not None

    # Identify turn holder and non-turn holders
    chores = [
        ("zoe", zoe_chore, "Zoë", mock_hass_users["kid1"].id),
        ("max", max_chore, "Max!", mock_hass_users["kid2"].id),
        ("lila", lila_chore, "Lila", mock_hass_users["kid3"].id),
    ]

    turn_holder = None
    non_turn_holder = None

    for slug, chore, name, user_id in chores:
        if chore["status"] == CHORE_STATE_PENDING:
            turn_holder = (slug, chore, name, user_id)
        elif non_turn_holder is None:
            non_turn_holder = (slug, chore, name, user_id)

    assert turn_holder is not None
    assert non_turn_holder is not None

    turn_slug, _, turn_name, _ = turn_holder
    non_slug, _, non_name, non_user_id = non_turn_holder

    # Non-turn holder attempts to claim
    non_context = Context(user_id=non_user_id)
    result_workflow = await claim_chore(
        hass, non_slug, "Dishes Rotation", context=non_context
    )
    await hass.async_block_till_done()

    # Verify claim was rejected - chore should still be pending
    zoe_helper = get_dashboard_helper(hass, "zoe")
    max_helper = get_dashboard_helper(hass, "max")
    lila_helper = get_dashboard_helper(hass, "lila")

    # Turn holder should still see pending
    turn_chore = find_chore(get_dashboard_helper(hass, turn_slug), "Dishes Rotation")
    assert turn_chore is not None
    turn_sensor = hass.states.get(turn_chore["eid"])
    assert turn_sensor is not None

    assert turn_chore["status"] == CHORE_STATE_PENDING, (
        f"Turn holder {turn_name} should still see pending"
    )
    assert turn_sensor.state == CHORE_STATE_PENDING
    assert turn_sensor.attributes.get("can_claim") is True
    assert turn_sensor.attributes.get("turn_kid_name") == turn_name

    # Non-turn holder should still be blocked
    non_chore = find_chore(get_dashboard_helper(hass, non_slug), "Dishes Rotation")
    assert non_chore is not None
    non_sensor = hass.states.get(non_chore["eid"])
    assert non_sensor is not None

    assert non_chore["status"] == CHORE_STATE_NOT_MY_TURN, (
        f"{non_name} should still be blocked"
    )
    assert non_sensor.state == CHORE_STATE_NOT_MY_TURN
    assert non_sensor.attributes.get("can_claim") is False
    assert non_sensor.attributes.get("lock_reason") == "not_my_turn"


@pytest.mark.asyncio
async def test_rotation_midnight_advances_once_and_keeps_single_claimable_holder(
    hass: HomeAssistant,
    scenario_shared: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Rotation advances once at midnight reset and remains stable on next tick.

    This validates end-to-end user-visible behavior through chore status sensors:
    - Turn holder can complete and be approved.
    - Midnight reset advances turn exactly once.
    - A second midnight tick without new completion does not double-advance.
    - Exactly one kid remains claimable (pending), others remain not_my_turn.
    """
    from homeassistant.core import Context

    from tests.helpers.workflows import approve_chore, claim_chore

    await hass.async_block_till_done()

    kid_profiles = [
        ("zoe", "Zoë", mock_hass_users["kid1"].id),
        ("max", "Max!", mock_hass_users["kid2"].id),
        ("lila", "Lila", mock_hass_users["kid3"].id),
    ]

    initial_turn_slug: str | None = None
    for kid_slug, _, _ in kid_profiles:
        rotation_chore = find_chore(
            get_dashboard_helper(hass, kid_slug), "Dishes Rotation"
        )
        assert rotation_chore is not None
        if rotation_chore["status"] == CHORE_STATE_PENDING:
            initial_turn_slug = kid_slug
            break

    assert initial_turn_slug is not None, "Expected one initial turn holder"

    initial_turn_user_id = next(
        user_id for slug, _, user_id in kid_profiles if slug == initial_turn_slug
    )

    kid_context = Context(user_id=initial_turn_user_id)
    parent_context = Context(user_id=mock_hass_users["parent1"].id)

    claim_result = await claim_chore(
        hass,
        initial_turn_slug,
        "Dishes Rotation",
        context=kid_context,
    )
    assert claim_result.success, f"Claim failed: {claim_result.error}"

    approve_result = await approve_chore(
        hass,
        initial_turn_slug,
        "Dishes Rotation",
        context=parent_context,
    )
    assert approve_result.success, f"Approve failed: {approve_result.error}"
    await hass.async_block_till_done()

    await scenario_shared.coordinator.chore_manager._on_midnight_rollover(
        now_utc=dt_now_utc()
    )
    await hass.async_block_till_done()

    first_midnight_pending: list[str] = []
    first_midnight_not_my_turn: list[str] = []
    first_turn_name: str | None = None

    for kid_slug, kid_name, _ in kid_profiles:
        rotation_chore = find_chore(
            get_dashboard_helper(hass, kid_slug), "Dishes Rotation"
        )
        assert rotation_chore is not None
        sensor_state = hass.states.get(rotation_chore["eid"])
        assert sensor_state is not None

        if sensor_state.state == CHORE_STATE_PENDING:
            first_midnight_pending.append(kid_slug)
            first_turn_name = kid_name
            assert sensor_state.attributes.get("can_claim") is True
        else:
            first_midnight_not_my_turn.append(kid_slug)
            assert sensor_state.state == CHORE_STATE_NOT_MY_TURN
            assert sensor_state.attributes.get("can_claim") is False
            assert sensor_state.attributes.get("lock_reason") == "not_my_turn"

    assert len(first_midnight_pending) == 1, "Exactly one kid should be claimable"
    assert len(first_midnight_not_my_turn) == 2
    assert first_midnight_pending[0] != initial_turn_slug, (
        "Turn holder should advance after midnight approval reset"
    )

    # Second midnight tick should not advance again without a new completed cycle
    await scenario_shared.coordinator.chore_manager._on_midnight_rollover(
        now_utc=dt_now_utc()
    )
    await hass.async_block_till_done()

    second_midnight_pending: list[str] = []
    for kid_slug, _, _ in kid_profiles:
        rotation_chore = find_chore(
            get_dashboard_helper(hass, kid_slug), "Dishes Rotation"
        )
        assert rotation_chore is not None
        sensor_state = hass.states.get(rotation_chore["eid"])
        assert sensor_state is not None
        if sensor_state.state == CHORE_STATE_PENDING:
            second_midnight_pending.append(kid_slug)
        assert sensor_state.attributes.get("turn_kid_name") == first_turn_name

    assert second_midnight_pending == first_midnight_pending, (
        "Turn holder should remain stable on subsequent midnight without new approval"
    )


# =============================================================================
# Run linting and tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
