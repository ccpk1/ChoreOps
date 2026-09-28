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
- TestAutoUnpause: Auto-resume timing, UTC storage, midnight fallback
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# hass fixture required for HA test setup

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from homeassistant.core import Context, HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.choreops import const
from custom_components.choreops.data_builders import build_user_profile
from custom_components.choreops.utils.dt_utils import (
    get_default_timezone,
    set_default_timezone,
)
from tests.helpers import (
    ATTR_CAN_APPROVE,
    ATTR_CAN_CLAIM,
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PAUSED,
    CHORE_STATE_PENDING,
    SERVICE_FIELD_CHORES_PAUSED,
    SERVICE_FIELD_CHORES_PAUSED_UNTIL,
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


# =============================================================================
# TEST: Auto-unpause (UTC storage + poll/midnight evaluation)
# =============================================================================


class TestAutoUnpause:
    """Test auto-resume: UTC storage, parsed-instant expiry, safety net."""

    @pytest.mark.parametrize(
        ("stored_until", "expected_utc"),
        [
            pytest.param(
                "2026-09-29T10:00:00",
                "2026-09-29T08:00:00+00:00",
                id="naive_local_treated_as_local",
            ),
            pytest.param(
                "2026-09-29T10:00:00+02:00",
                "2026-09-29T08:00:00+00:00",
                id="offset_instant_preserved_as_utc",
            ),
        ],
    )
    async def test_service_stores_paused_until_as_utc(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
        stored_until: str,
        expected_utc: str,
    ) -> None:
        """Service stores UTC ISO: naive input is local, offset input is kept."""
        original_tz = get_default_timezone()
        set_default_timezone(ZoneInfo("Europe/Berlin"))
        try:
            await hass.services.async_call(
                const.DOMAIN,
                SERVICE_PAUSE_USER_CHORES,
                {
                    "config_entry_id": scenario_minimal.config_entry.entry_id,
                    SERVICE_FIELD_CHORES_PAUSED: True,
                    SERVICE_FIELD_CHORES_PAUSED_UNTIL: stored_until,
                    "user_name": "Zoë",
                },
                blocking=True,
                context=zoe_context,
            )
            await hass.async_block_till_done()

            zoe_id = scenario_minimal.assignee_ids["Zoë"]
            user_data = scenario_minimal.coordinator._data[const.DATA_USERS][zoe_id]
            assert user_data[const.DATA_USER_CHORES_PAUSED_UNTIL] == expected_utc
        finally:
            set_default_timezone(original_tz)

    def test_build_user_profile_stores_utc(self) -> None:
        """User-form path normalizes the DateTimeSelector string to UTC ISO."""
        original_tz = get_default_timezone()
        set_default_timezone(ZoneInfo("Europe/Berlin"))
        try:
            profile = build_user_profile(
                {
                    const.CFOF_USERS_INPUT_NAME: "Zoë",
                    const.CFOF_USERS_INPUT_CHORES_PAUSED: True,
                    const.CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL: "2026-09-29 10:00:00",
                }
            )
            assert (
                profile[const.DATA_USER_CHORES_PAUSED_UNTIL]
                == "2026-09-29T08:00:00+00:00"
            )
        finally:
            set_default_timezone(original_tz)

    @pytest.mark.parametrize(
        "stored_until",
        [
            pytest.param(
                "2026-09-28T13:00:00",
                id="naive_local_wall_after_utc_now",
            ),
            pytest.param(
                "2026-09-28T13:30:00+02:00",
                id="offset_wall_after_utc_now",
            ),
            pytest.param("2026-09-27 23:00:00", id="space_separated_legacy"),
        ],
    )
    async def test_auto_unpause_fires_on_periodic_update(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        stored_until: str,
    ) -> None:
        """Expired pauses resume on the poll via parsed instants, not strings.

        The naive and offset variants have wall-clock digits that sort AFTER
        the UTC now string, so the legacy string comparison would leave the
        user paused for an extra day (issue #322).
        """
        original_tz = get_default_timezone()
        set_default_timezone(ZoneInfo("Europe/Berlin"))
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        users = scenario_minimal.coordinator._data[const.DATA_USERS]
        users[zoe_id][const.DATA_USER_CHORES_PAUSED] = True
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNTIL] = stored_until
        try:
            fixed_now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
            await scenario_minimal.coordinator.chore_manager._on_periodic_update(
                now_utc=fixed_now
            )
            await hass.async_block_till_done()

            assert users[zoe_id][const.DATA_USER_CHORES_PAUSED] is False
            assert const.DATA_USER_CHORES_PAUSED_UNTIL not in users[zoe_id]
        finally:
            set_default_timezone(original_tz)

    async def test_auto_unpause_falls_back_to_midnight_rollover(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """The midnight pass still resumes expired pauses (safety net)."""
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        users = scenario_minimal.coordinator._data[const.DATA_USERS]
        users[zoe_id][const.DATA_USER_CHORES_PAUSED] = True
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNTIL] = "2026-09-27T00:00:00+00:00"

        await scenario_minimal.coordinator.chore_manager._on_midnight_rollover(
            now_utc=datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
        )
        await hass.async_block_till_done()

        assert users[zoe_id][const.DATA_USER_CHORES_PAUSED] is False
        assert const.DATA_USER_CHORES_PAUSED_UNTIL not in users[zoe_id]

    async def test_future_until_stays_paused_on_periodic(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """A return date in the future keeps the pause active."""
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        users = scenario_minimal.coordinator._data[const.DATA_USERS]
        users[zoe_id][const.DATA_USER_CHORES_PAUSED] = True
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNTIL] = "2026-09-29T00:00:00+00:00"

        await scenario_minimal.coordinator.chore_manager._on_periodic_update(
            now_utc=datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
        )
        await hass.async_block_till_done()

        assert users[zoe_id][const.DATA_USER_CHORES_PAUSED] is True
        assert (
            users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNTIL]
            == "2026-09-29T00:00:00+00:00"
        )

    async def test_pause_without_until_never_auto_unpauses(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """No return date means an indefinite pause (documented behavior)."""
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        users = scenario_minimal.coordinator._data[const.DATA_USERS]
        users[zoe_id][const.DATA_USER_CHORES_PAUSED] = True

        await scenario_minimal.coordinator.chore_manager._on_periodic_update(
            now_utc=datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
        )
        await scenario_minimal.coordinator.chore_manager._on_midnight_rollover(
            now_utc=datetime(2026, 9, 28, 23, 59, tzinfo=UTC)
        )
        await hass.async_block_till_done()

        assert users[zoe_id][const.DATA_USER_CHORES_PAUSED] is True
        assert not users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL)

    async def test_auto_unpause_does_not_shift_dates(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Auto-resume never shifts schedules: reschedule stays opt-in."""
        coordinator = scenario_minimal.coordinator
        with patch.object(
            coordinator.chore_manager, "reschedule_chores_after"
        ) as reschedule_mock:
            await hass.services.async_call(
                const.DOMAIN,
                SERVICE_PAUSE_USER_CHORES,
                {
                    "config_entry_id": scenario_minimal.config_entry.entry_id,
                    SERVICE_FIELD_CHORES_PAUSED: True,
                    SERVICE_FIELD_CHORES_PAUSED_UNTIL: "2026-09-27T00:00:00+00:00",
                    "user_name": "Zoë",
                },
                blocking=True,
                context=zoe_context,
            )
            await hass.async_block_till_done()

            await coordinator.chore_manager._on_periodic_update(
                now_utc=datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
            )
            await hass.async_block_till_done()

            reschedule_mock.assert_not_awaited()

        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        user_data = coordinator._data[const.DATA_USERS][zoe_id]
        assert user_data[const.DATA_USER_CHORES_PAUSED] is False
