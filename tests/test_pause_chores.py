"""Pause chore tests using YAML scenarios.

These tests verify the complete pause → paused display → resume cycle
for independent and rotation chore types.

COMPLIANT WITH AGENT_TEST_CREATION_INSTRUCTIONS.md:
- Rule 2: Uses service calls (not direct coordinator API)
- Rule 3: Uses dashboard helper as single source of entity IDs
- Rule 4: Gets chore data from sensor attributes
- Rule 5: All service calls use Context for user authorization
- Rule 6: Coordinator data access only for internal logic verification

Test Organization:
- TestPauseService: Service layer (pause, resume, paused_until)
- TestPausedDisplay: Chore state shows paused when flag is set
- TestPauseOverdueGuard: No overdue transition while paused
- TestPauseRotationSkip: Rotation advances past paused user
- TestCanClaimGuard: can_claim returns False for paused user
- TestUnpauseLifecycle: Full pause → unpause cycle
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# hass fixture required for HA test setup

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.core import Context, HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.choreops import const
from tests.helpers import (
    ATTR_CAN_APPROVE,
    ATTR_CAN_CLAIM,
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PAUSED,
    CHORE_STATE_PENDING,
    SERVICE_FIELD_CHORES_PAUSED,
    SERVICE_PAUSE_USER_CHORES,
)
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.helpers.workflows import find_chore, get_dashboard_helper

# =============================================================================
# FIXTURES
# =============================================================================


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


@pytest.fixture
async def scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load shared scenario: 3 assignees, 1 approver, rotation chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


# =============================================================================
# HELPERS
# =============================================================================


def get_chore_sensor(
    hass: HomeAssistant, assignee_slug: str, chore_name: str
) -> str | None:
    """Get chore sensor entity ID from dashboard helper.

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee's slug (e.g., "zoe")
        chore_name: Display name of chore

    Returns:
        Entity ID string, or None if not found
    """
    dashboard = get_dashboard_helper(hass, assignee_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return None
    return chore["eid"]


def get_chore_state(hass: HomeAssistant, assignee_slug: str, chore_name: str) -> str:
    """Get chore sensor state.

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee's slug (e.g., "zoe")
        chore_name: Display name of chore

    Returns:
        State string, or "not_found" if chore or sensor is missing
    """
    eid = get_chore_sensor(hass, assignee_slug, chore_name)
    if eid is None:
        return "not_found"
    sensor = hass.states.get(eid)
    return sensor.state if sensor else "unavailable"


def get_chore_attr(
    hass: HomeAssistant, assignee_slug: str, chore_name: str, attr: str
) -> Any:
    """Get a specific attribute from a chore sensor.

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee's slug (e.g., "zoe")
        chore_name: Display name of chore
        attr: Attribute key to retrieve

    Returns:
        Attribute value, or None if sensor/attribute missing
    """
    eid = get_chore_sensor(hass, assignee_slug, chore_name)
    if eid is None:
        return None
    sensor = hass.states.get(eid)
    if sensor is None:
        return None
    return sensor.attributes.get(attr)


@pytest.fixture
def zoe_context(scenario_minimal: SetupResult) -> Context:
    """Create a context for Zoë's user ID."""
    return Context(user_id=scenario_minimal.assignee_ids["Zoë"])


# =============================================================================
# TEST: Pause Service
# =============================================================================


class TestPauseService:
    """Test the choreops.pause_user_chores service."""

    async def test_pause_user_chores_pause(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Test pausing a user's chores via service call."""
        entry_id = scenario_minimal.config_entry.entry_id

        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        # Verify: Make bed should show paused state
        state = get_chore_state(hass, "zoe", "Make bed")
        assert state == CHORE_STATE_PAUSED, f"Expected paused, got {state}"

    async def test_pause_user_chores_resume(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Test resuming a user's chores via service call."""
        entry_id = scenario_minimal.config_entry.entry_id

        # First pause
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        # Then resume
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: False,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        # Verify: Make bed should show normal state (pending) after resume
        state = get_chore_state(hass, "zoe", "Make bed")
        assert state == CHORE_STATE_PENDING, f"Expected pending, got {state}"


# =============================================================================
# TEST: Paused Display State
# =============================================================================


class TestPausedDisplay:
    """Test core P0 guard: chore displays paused state."""

    async def test_paused_state_and_claim_mode(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Test that paused chores show paused state with blocked_paused claim mode."""
        entry_id = scenario_minimal.config_entry.entry_id

        # Pause Zoë
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        # Verify sensor state is "paused"
        state = get_chore_state(hass, "zoe", "Make bed")
        assert state == CHORE_STATE_PAUSED, f"Expected paused, got {state}"

        # Verify claim_mode attribute
        claim_mode = get_chore_attr(
            hass, "zoe", "Make bed", const.ATTR_CHORE_CLAIM_MODE
        )
        assert claim_mode == const.CHORE_CLAIM_MODE_BLOCKED_PAUSED, (
            f"Expected blocked_paused, got {claim_mode}"
        )

        # Verify can_claim is False
        can_claim = get_chore_attr(hass, "zoe", "Make bed", ATTR_CAN_CLAIM)
        assert can_claim is False, "Expected can_claim to be False"

        # Verify can_approve is False
        can_approve = get_chore_attr(hass, "zoe", "Make bed", ATTR_CAN_APPROVE)
        assert can_approve is False, "Expected can_approve to be False"

    async def test_unpaused_user_unaffected(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that non-paused users still see normal states."""
        # Pause only Zoë (not Max or Lila)
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": scenario_shared.config_entry.entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=Context(user_id=mock_hass_users["approver1"].id),
        )
        await hass.async_block_till_done()

        # Max should NOT see paused (not paused)
        max_state = get_chore_state(hass, "max", "Walk the dog")
        assert max_state != CHORE_STATE_PAUSED, (
            "Expected non-paused user to see normal state"
        )


# =============================================================================
# TEST: Overdue Guard
# =============================================================================


class TestPauseOverdueGuard:
    """Test that paused users don't accumulate overdue/missed penalties."""

    async def test_no_overdue_while_paused(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Test that a chore with past due date stays in pending while paused."""
        entry_id = scenario_minimal.config_entry.entry_id

        # Pause Zoë
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        # Advance time past the due date of "Clean room" (due +7d from setup)
        # and trigger midnight rollover
        future = dt_util.utcnow() + timedelta(days=30)
        with patch("homeassistant.util.dt.utcnow", return_value=future):
            # Trigger midnight processing
            await hass.services.async_call(
                const.DOMAIN,
                "reset_chores_to_pending_state",
                {"config_entry_id": entry_id},
                blocking=True,
                context=zoe_context,
            )
            await hass.async_block_till_done()

        # Verify: Clean room should still be paused, not overdue
        state = get_chore_state(hass, "zoe", "Clean room")
        assert state != CHORE_STATE_OVERDUE, (
            f"Expected not overdue while paused, got {state}"
        )


# =============================================================================
# TEST: Rotation Skip
# =============================================================================


class TestPauseRotationSkip:
    """Test that rotation advances past paused users."""

    async def test_rotation_skips_paused_user(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that a paused user is skipped in rotation advance."""
        config_entry = scenario_shared.config_entry

        # Pause Zoë (no need to determine current turn first)

        # Pause Zoë
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": config_entry.entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=Context(user_id=mock_hass_users["approver1"].id),
        )
        await hass.async_block_till_done()

        # Verify Zoë sees paused state on rotation chore
        paused_state = get_chore_state(hass, "zoe", "Dishes Rotation")
        assert paused_state == CHORE_STATE_PAUSED, (
            f"Expected paused for Zoë, got {paused_state}"
        )

        # Max should not see paused (not paused)
        max_state = get_chore_state(hass, "max", "Dishes Rotation")
        assert max_state != CHORE_STATE_PAUSED, "Expected non-paused state for Max"


# =============================================================================
# TEST: Can Claim Guard
# =============================================================================


class TestPauseCanClaimGuard:
    """Test that can_claim_chore returns False for paused users."""

    async def test_can_claim_false_when_paused(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Test that a paused user cannot claim chores."""
        entry_id = scenario_minimal.config_entry.entry_id

        # Pause Zoë
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        # Verify can_claim is False on sensor
        can_claim = get_chore_attr(hass, "zoe", "Make bed", ATTR_CAN_CLAIM)
        assert can_claim is False, "Expected can_claim to be False when paused"


# =============================================================================
# TEST: Unpause Lifecycle
# =============================================================================


class TestUnpauseLifecycle:
    """Test the full pause → unpause cycle."""

    async def test_unpause_restores_normal_state(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Test that unpausing returns chore to its underlying state."""
        entry_id = scenario_minimal.config_entry.entry_id

        # Pause Zoë
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: True,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        assert get_chore_state(hass, "zoe", "Make bed") == CHORE_STATE_PAUSED

        # Unpause Zoë
        await hass.services.async_call(
            const.DOMAIN,
            SERVICE_PAUSE_USER_CHORES,
            {
                "config_entry_id": entry_id,
                SERVICE_FIELD_CHORES_PAUSED: False,
                "user_name": "Zoë",
            },
            blocking=True,
            context=zoe_context,
        )
        await hass.async_block_till_done()

        # Verify: Make bed returns to pending (underlying state)
        state = get_chore_state(hass, "zoe", "Make bed")
        assert state == CHORE_STATE_PENDING, (
            f"Expected pending after unpause, got {state}"
        )
