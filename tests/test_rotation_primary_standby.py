"""Test rotation_primary_standby chore FSM state transitions.

Tests the primary-standby rotation logic:
- Primary is always the default turn-holder
- Standbys see "standby" state with blocking per standby_claim_mode
- Turn always resets to primary at approval/midnight boundaries
- Pause-aware snap-back on unpause
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from homeassistant.core import Context

from custom_components.choreops.utils.dt_utils import dt_now_utc

# Import test constants from helpers (not from const.py - Rule 0)
from tests.helpers.constants import (
    CHORE_CLAIM_MODE_BLOCKED_STANDBY,
    CHORE_CLAIM_MODE_CLAIMABLE,
    CHORE_CLAIM_MODE_STANDBY_AVAILABLE,
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_DUE,
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PENDING,
    CHORE_STATE_STANDBY,
    CHORE_STATE_WAITING,
)
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.helpers.workflows import (
    approve_chore,
    claim_chore,
    find_chore,
    get_dashboard_helper,
)

# =============================================================================
# HELPERS
# =============================================================================


def get_chore_state_from_sensor(
    hass: HomeAssistant, assignee_slug: str, chore_name: str
) -> str:
    """Get chore state from sensor entity (what the user sees in UI)."""
    dashboard = get_dashboard_helper(hass, assignee_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return "not_found"
    chore_state = hass.states.get(chore["eid"])
    return chore_state.state if chore_state else "unavailable"


def get_chore_attributes_from_sensor(
    hass: HomeAssistant, assignee_slug: str, chore_name: str
) -> dict[str, Any]:
    """Get all chore sensor attributes for a assignee/chore pair."""
    dashboard = get_dashboard_helper(hass, assignee_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return {}
    chore_state = hass.states.get(chore["eid"])
    return dict(chore_state.attributes) if chore_state else {}


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_primary_standby(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load primary-standby scenario: 2 assignees, 1 approver."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_primary_standby.yaml",
    )


# =============================================================================
# T1 — Primary always claimable
# =============================================================================


@pytest.mark.asyncio
async def test_primary_always_claimable(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
) -> None:
    """Primary (assignee[0]) should always see pending/due/waiting, never standby."""
    await hass.async_block_till_done()

    for chore_name in [
        "Daily Chore (anytime)",
        "Weekly Chore (on_overdue)",
        "Daily Chore (manual_only)",
    ]:
        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        assert zoe_state != CHORE_STATE_STANDBY, (
            f"Primary should never see standby for {chore_name}, got {zoe_state}"
        )
        assert zoe_state in (
            CHORE_STATE_PENDING,
            CHORE_STATE_DUE,
            CHORE_STATE_WAITING,
        ), f"Primary should see actionable state for {chore_name}, got {zoe_state}"


# =============================================================================
# T2 — Standby sees standby state
# =============================================================================


@pytest.mark.asyncio
async def test_standby_sees_standby_state(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
) -> None:
    """All standbys (regardless of claim_mode) should see standby state."""
    await hass.async_block_till_done()

    for chore_name in [
        "Daily Chore (anytime)",
        "Weekly Chore (on_overdue)",
        "Daily Chore (manual_only)",
    ]:
        max_state = get_chore_state_from_sensor(hass, "max", chore_name)
        assert max_state == CHORE_STATE_STANDBY, (
            f"Standby should see standby state for {chore_name}, got {max_state}"
        )


# =============================================================================
# T3 — Standby with anytime can claim (claim mode check)
# =============================================================================


@pytest.mark.asyncio
async def test_standby_anytime_claim_mode(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Standby with anytime should have standby_available claim mode and can claim."""
    from homeassistant.core import Context

    await hass.async_block_till_done()

    chore_name = "Daily Chore (anytime)"
    coordinator = scenario_primary_standby.coordinator

    # Check claim mode on sensor
    max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
    assert max_attrs.get("claim_mode") == CHORE_CLAIM_MODE_STANDBY_AVAILABLE, (
        f"Standby anytime should have standby_available claim mode, "
        f"got {max_attrs.get('claim_mode')}"
    )

    # Verify standby can claim
    assignee_context = Context(user_id=mock_hass_users["assignee2"].id)
    claim_result = await claim_chore(hass, "max", chore_name, context=assignee_context)
    await hass.async_block_till_done()
    assert claim_result.success, (
        f"Standby should be able to claim: {claim_result.error}"
    )
    assert get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_CLAIMED

    # Approve — after approval, turn is snapped back to primary in storage
    approver_context = Context(user_id=mock_hass_users["approver1"].id)
    await approve_chore(hass, "max", chore_name, context=approver_context)
    await hass.async_block_till_done()

    # Verify turn holder in coordinator data (sensor shows completed_by_other
    # until the reset boundary fires — turn IS snapped back for next cycle)
    chore_id = scenario_primary_standby.chore_ids[chore_name]
    zoe_id = scenario_primary_standby.assignee_ids.get("Zoë")
    chore_info = coordinator.chores_data.get(chore_id, {})
    turn = chore_info.get("rotation_current_assignee_id")
    assert turn == zoe_id, f"Turn should be snapped back to primary, got {turn}"


# =============================================================================
# T4 — Standby with manual_only claim mode
# =============================================================================


@pytest.mark.asyncio
async def test_standby_manual_only_claim_mode(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
) -> None:
    """Standby with manual_only should have blocked_standby claim mode."""
    await hass.async_block_till_done()

    chore_name = "Daily Chore (manual_only)"

    max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
    assert max_attrs.get("claim_mode") == CHORE_CLAIM_MODE_BLOCKED_STANDBY, (
        f"Standby manual_only should have blocked_standby, "
        f"got {max_attrs.get('claim_mode')}"
    )

    # Claim mode is blocked — claim button may still render in dashboard
    # templates, but the FSM rejects the claim at the service level


# =============================================================================
# T5 — Manual turn override via set_rotation_turn
# =============================================================================


@pytest.mark.asyncio
async def test_set_rotation_turn_makes_standby_active(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
) -> None:
    """set_rotation_turn should make the standby the active turn-holder."""
    await hass.async_block_till_done()

    chore_name = "Daily Chore (anytime)"
    coordinator = scenario_primary_standby.coordinator
    chore_id = scenario_primary_standby.chore_ids[chore_name]
    zoe_id = scenario_primary_standby.assignee_ids.get("Zoë")
    max_id = scenario_primary_standby.assignee_ids.get("Max!")

    # Set turn to Max (standby)
    await coordinator.chore_manager.set_rotation_turn(chore_id, max_id)
    await hass.async_block_till_done()

    # Max should now see pending (active turn-holder)
    assert get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_PENDING
    # Zoë should now see standby
    assert get_chore_state_from_sensor(hass, "zoe", chore_name) == CHORE_STATE_STANDBY

    # Reset back to Zoë (primary)
    await coordinator.chore_manager.set_rotation_turn(chore_id, zoe_id)
    await hass.async_block_till_done()

    assert get_chore_state_from_sensor(hass, "zoe", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )
    assert get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_STANDBY


# =============================================================================
# T6 — Standby on_overdue can claim after due date
# =============================================================================


@pytest.mark.asyncio
async def test_standby_on_overdue_can_claim_after_due(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Standby with on_overdue should be able to claim after due date passes."""

    await hass.async_block_till_done()

    chore_name = "Weekly Chore (on_overdue)"
    coordinator = scenario_primary_standby.coordinator
    chore_id = scenario_primary_standby.chore_ids[chore_name]

    # Before due: should see blocked_standby
    max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
    assert max_attrs.get("claim_mode") == CHORE_CLAIM_MODE_BLOCKED_STANDBY, (
        f"Should be blocked before due, got {max_attrs.get('claim_mode')}"
    )

    # Force due date into the past and trigger periodic update
    chore_info = coordinator.chores_data.get(chore_id, {})
    chore_info["due_date"] = (dt_now_utc() - timedelta(minutes=5)).isoformat()
    await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
    await hass.async_block_till_done()

    # After due: claim mode should no longer be blocked_standby
    max_attrs_after = get_chore_attributes_from_sensor(hass, "max", chore_name)
    assert max_attrs_after.get("claim_mode") != CHORE_CLAIM_MODE_BLOCKED_STANDBY, (
        "Standby claim mode should change after due date passes"
    )


# =============================================================================
# T7 — Turn resets to primary after approval
# =============================================================================


@pytest.mark.asyncio
async def test_turn_resets_to_primary_after_approval(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """After standby completes and chore is approved, turn should reset to primary."""
    from homeassistant.core import Context

    await hass.async_block_till_done()

    chore_name = "Daily Chore (anytime)"
    coordinator = scenario_primary_standby.coordinator

    # Max (standby) claims and gets approved
    assignee_context = Context(user_id=mock_hass_users["assignee2"].id)
    await claim_chore(hass, "max", chore_name, context=assignee_context)
    await hass.async_block_till_done()

    approver_context = Context(user_id=mock_hass_users["approver1"].id)
    await approve_chore(hass, "max", chore_name, context=approver_context)
    await hass.async_block_till_done()

    # Zoë should be turn-holder in storage (sensor shows completed_by_other
    # until the reset boundary fires — turn is snapped back for next cycle)
    chore_id = scenario_primary_standby.chore_ids[chore_name]
    zoe_id = scenario_primary_standby.assignee_ids.get("Zoë")
    chore_info = coordinator.chores_data.get(chore_id, {})
    turn = chore_info.get("rotation_current_assignee_id")
    assert turn == zoe_id, f"Turn should be snapped back to primary, got {turn}"


# =============================================================================
# T8 — Issue #248: standby completion clears other users' exception states
# =============================================================================


@pytest.mark.asyncio
async def test_standby_completion_clears_others_overdue_and_global(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """A standby completing after overdue clears the primary's persisted overdue.

    Reproduces Issue #248 (Feed Cat AM): primary and standby both persisted
    `overdue`; the standby completes the chore. The primary's persisted `overdue`
    must be cleared (lifecycle hygiene) so the global aggregate resolves to
    `approved`, not a stale `overdue`.
    """
    from homeassistant.core import Context

    await hass.async_block_till_done()

    chore_name = "Daily Chore (anytime)"
    coordinator = scenario_primary_standby.coordinator
    chore_id = scenario_primary_standby.chore_ids[chore_name]
    zoe_id = scenario_primary_standby.assignee_ids.get("Zoë")
    max_id = scenario_primary_standby.assignee_ids.get("Max!")

    # Set both persisted per-assignee states to OVERDUE (simulating an overdue chore).
    for assignee_id in (zoe_id, max_id):
        assignee_chore_data = coordinator.chore_manager._get_assignee_chore_data(
            assignee_id, chore_id
        )
        assignee_chore_data["state"] = CHORE_STATE_OVERDUE

    # Set the chore's due date to the past so the FSM resolves these as overdue.
    chore_info = coordinator.chores_data.get(chore_id, {})
    chore_info["due_date"] = (dt_now_utc() - timedelta(hours=1)).isoformat()

    # Recompute global from the stale overdue states -> should be overdue.
    coordinator.chore_manager._update_global_state(chore_id)
    assert coordinator.chores_data[chore_id]["state"] == CHORE_STATE_OVERDUE

    # Max (standby) claims and is approved.
    assignee_context = Context(user_id=mock_hass_users["assignee2"].id)
    await claim_chore(hass, "max", chore_name, context=assignee_context)
    await hass.async_block_till_done()
    approver_context = Context(user_id=mock_hass_users["approver1"].id)
    await approve_chore(hass, "max", chore_name, context=approver_context)
    await hass.async_block_till_done()

    # Primary (Zoë) persisted state must be cleared out of overdue.
    zoe_chore_data = coordinator.chore_manager._get_assignee_chore_data(
        zoe_id, chore_id
    )
    assert zoe_chore_data["state"] == CHORE_STATE_PENDING, (
        "Primary's persisted overdue must be cleared when a standby completes"
    )

    # Global aggregate must resolve to approved (occurrence completed).
    assert coordinator.chores_data[chore_id]["state"] == CHORE_STATE_APPROVED


# =============================================================================
# T8 — Single assignee (no standbys) works gracefully
# =============================================================================


@pytest.mark.asyncio
async def test_single_assignee_no_standby_state(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
) -> None:
    """Chore with only primary (no standbys) should never show standby."""
    await hass.async_block_till_done()

    chore_name = "Solo Chore (single)"

    zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
    assert zoe_state != CHORE_STATE_STANDBY, (
        f"Sole assignee should never see standby, got {zoe_state}"
    )
    assert zoe_state in (CHORE_STATE_PENDING, CHORE_STATE_DUE), (
        f"Sole assignee should see actionable state, got {zoe_state}"
    )
    zoe_attrs = get_chore_attributes_from_sensor(hass, "zoe", chore_name)
    assert zoe_attrs.get("claim_mode") == CHORE_CLAIM_MODE_CLAIMABLE


# =============================================================================
# T9 — Standby excluded from due-today summary
# =============================================================================


@pytest.mark.asyncio
async def test_standby_excluded_from_due_today(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
) -> None:
    """Standby state should NOT count toward the backup's due-today summary."""
    await hass.async_block_till_done()

    coordinator = scenario_primary_standby.coordinator
    chore_name = "Daily Chore (anytime)"
    chore_id = scenario_primary_standby.chore_ids[chore_name]
    max_id = scenario_primary_standby.assignee_ids.get("Max!")
    zoe_id = scenario_primary_standby.assignee_ids.get("Zoë")

    assert get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_STANDBY

    # Standby's due-today should exclude this chore
    counts = coordinator.chore_manager.chore_counts_toward_due_today_summary(
        max_id, chore_id
    )
    assert counts is False, "Standby chore should not count toward due-today summary"

    # Primary's due-today should include it
    zoe_counts = coordinator.chore_manager.chore_counts_toward_due_today_summary(
        zoe_id, chore_id
    )
    assert zoe_counts is True, "Primary's chore should count toward due-today summary"


# =============================================================================
# T10 — Primary paused activates standby
# =============================================================================


@pytest.mark.asyncio
async def test_primary_paused_standby_activates(
    hass: HomeAssistant,
    scenario_primary_standby: SetupResult,
) -> None:
    """When primary is paused, standby should become active turn-holder."""
    await hass.async_block_till_done()

    chore_name = "Daily Chore (anytime)"
    coordinator = scenario_primary_standby.coordinator
    zoe_id = scenario_primary_standby.assignee_ids.get("Zoë")

    # Baseline: Zoë is primary, Max is standby
    assert get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_STANDBY

    # Pause Zoë (primary)
    await coordinator.chore_manager.set_user_chores_paused(zoe_id, paused=True)
    await hass.async_block_till_done()

    # Max should now see pending (active turn-holder)
    assert get_chore_state_from_sensor(hass, "max", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )

    # Unpause Zoë
    await coordinator.chore_manager.set_user_chores_paused(zoe_id, paused=False)
    await hass.async_block_till_done()

    # Zoë should be back as turn-holder
    assert get_chore_state_from_sensor(hass, "zoe", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )
    assert get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_STANDBY


# =============================================================================
# T11 — Multi-standby rotation when primary is paused
# =============================================================================


@pytest.fixture
async def scenario_primary_standby_multi(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load multi-standby scenario: 1 primary + 3 standbys."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_primary_standby_multi.yaml",
    )


@pytest.mark.asyncio
async def test_multi_standby_rotates_when_primary_paused(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
    scenario_primary_standby_multi: SetupResult,
) -> None:
    """With primary paused, turn rotates among standbys on each completion."""
    await hass.async_block_till_done()

    chore_name = "Rotating Standby Chore"
    coordinator = scenario_primary_standby_multi.coordinator
    zoe_id = scenario_primary_standby_multi.assignee_ids.get("Zoë")
    approver_context = Context(user_id=mock_hass_users["approver1"].id)
    assignee2_context = Context(user_id=mock_hass_users["assignee2"].id)
    assignee3_context = Context(user_id=mock_hass_users["assignee3"].id)
    assignee4_context = Context(user_id=mock_hass_users["assignee4"].id)

    # Baseline: Zoë is primary, standbys see standby
    assert get_chore_state_from_sensor(hass, "zoe", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )
    for slug in ("max", "lila", "leo"):
        assert (
            get_chore_state_from_sensor(hass, slug, chore_name) == CHORE_STATE_STANDBY
        )

    # Pause Zoë (primary)
    await coordinator.chore_manager.set_user_chores_paused(zoe_id, paused=True)
    await hass.async_block_till_done()

    # Max should become active (first non-paused standby)
    assert get_chore_state_from_sensor(hass, "max", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )

    # Max claims and completes the chore
    await claim_chore(hass, "max", chore_name, context=assignee2_context)
    await approve_chore(hass, "max", chore_name, context=approver_context)
    await hass.async_block_till_done()

    # Turn should advance to Lila (not back to Max, not back to Zoë)
    assert get_chore_state_from_sensor(hass, "lila", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )
    assert get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_STANDBY

    # Lila claims and completes
    await claim_chore(hass, "lila", chore_name, context=assignee3_context)
    await approve_chore(hass, "lila", chore_name, context=approver_context)
    await hass.async_block_till_done()

    # Turn should advance to Leo
    assert get_chore_state_from_sensor(hass, "leo", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )
    assert get_chore_state_from_sensor(hass, "lila", chore_name) == CHORE_STATE_STANDBY

    # Leo claims and completes
    await claim_chore(hass, "leo", chore_name, context=assignee4_context)
    await approve_chore(hass, "leo", chore_name, context=approver_context)
    await hass.async_block_till_done()

    # Turn should wrap back to Max (round-robin among standbys)
    assert get_chore_state_from_sensor(hass, "max", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )
    assert get_chore_state_from_sensor(hass, "leo", chore_name) == CHORE_STATE_STANDBY

    # Unpause Zoë — snap back to primary
    await coordinator.chore_manager.set_user_chores_paused(zoe_id, paused=False)
    await hass.async_block_till_done()

    assert get_chore_state_from_sensor(hass, "zoe", chore_name) in (
        CHORE_STATE_PENDING,
        CHORE_STATE_DUE,
    )
    for slug in ("max", "lila", "leo"):
        assert (
            get_chore_state_from_sensor(hass, slug, chore_name) == CHORE_STATE_STANDBY
        )
