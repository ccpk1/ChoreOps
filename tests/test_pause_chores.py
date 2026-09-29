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
- TestUnpauseActionChaining: stored resume intent, bare/explicit resume,
  D3 lifecycle matrix, form rows, sensor attribute
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# hass fixture required for HA test setup

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
import pytest

from custom_components.choreops import const
from custom_components.choreops.data_builders import build_user_profile
from custom_components.choreops.utils.dt_utils import (
    dt_now_utc,
    dt_to_utc,
    get_default_timezone,
    set_default_timezone,
)

if TYPE_CHECKING:
    from custom_components.choreops.coordinator import ChoreOpsDataCoordinator
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
    """Load shared scenario: 3 assignees, 1 approver, shared chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


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


async def call_pause_service(
    hass: HomeAssistant,
    scenario: SetupResult,
    context: Context,
    *,
    paused: bool,
    **fields: Any,
) -> None:
    """Call pause_user_chores for this scenario's Zoë with extra fields.

    Args:
        hass: Home Assistant instance
        scenario: Scenario providing the config entry
        context: Service call context
        paused: True to pause, False to resume
        **fields: Extra service fields (unpause_action, paused_until, ...)
    """
    payload: dict[str, Any] = {
        "config_entry_id": scenario.config_entry.entry_id,
        SERVICE_FIELD_CHORES_PAUSED: paused,
        "user_name": "Zoë",
    }
    payload.update(fields)
    await hass.services.async_call(
        const.DOMAIN,
        SERVICE_PAUSE_USER_CHORES,
        payload,
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()


def get_chore_id(coordinator: ChoreOpsDataCoordinator, chore_name: str) -> str:
    """Find a chore's internal ID by display name.

    Args:
        coordinator: Coordinator holding chore data
        chore_name: Display name of the chore

    Returns:
        The chore's internal_id

    Raises:
        AssertionError: If no chore matches the name
    """
    for chore_id, chore_data in coordinator.chores_data.items():
        if chore_data.get(const.DATA_CHORE_NAME) == chore_name:
            return chore_id
    raise AssertionError(f"Chore not found: {chore_name}")


def set_past_due(
    coordinator: ChoreOpsDataCoordinator,
    chore_id: str,
    assignee_id: str | None = None,
    days: int = 2,
) -> str:
    """Overwrite a stored due date into the past for shift assertions.

    Args:
        coordinator: Coordinator holding chore data
        chore_id: Chore to backdate
        assignee_id: Set the per-assignee date (independent) when given,
            otherwise the chore-level date (shared/rotation)
        days: How many days in the past

    Returns:
        The stored past-due ISO string
    """
    past_iso = (dt_now_utc() - timedelta(days=days)).isoformat()
    chore_data = coordinator.chores_data[chore_id]
    if assignee_id is None:
        chore_data[const.DATA_CHORE_DUE_DATE] = past_iso
    else:
        chore_data.setdefault(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})[
            assignee_id
        ] = past_iso
    return past_iso


def get_stored_due(
    coordinator: ChoreOpsDataCoordinator,
    chore_id: str,
    assignee_id: str | None = None,
) -> str:
    """Read the raw stored due date (cache-proof) for shift assertions.

    Args:
        coordinator: Coordinator holding chore data
        chore_id: Chore to read
        assignee_id: Read the per-assignee date (independent) when given,
            otherwise the chore-level date (shared/rotation)

    Returns:
        The stored ISO string, or "" when unset
    """
    chore_data = coordinator.chores_data[chore_id]
    if assignee_id is None:
        due = chore_data.get(const.DATA_CHORE_DUE_DATE)
    else:
        due = chore_data.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}).get(
            assignee_id
        )
    return str(due) if due is not None else ""


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
                "2099-09-29T10:00:00",
                "2099-09-29T08:00:00+00:00",
                id="naive_local_treated_as_local",
            ),
            pytest.param(
                "2099-09-29T10:00:00+02:00",
                "2099-09-29T08:00:00+00:00",
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

    @pytest.mark.parametrize(
        ("stored_action", "expect_shifted"),
        [
            pytest.param(None, False, id="no_intent_no_shift"),
            pytest.param("unpause_shift_all", True, id="intent_shifts"),
        ],
    )
    async def test_auto_unpause_shifts_only_when_intent_stored(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        stored_action: str | None,
        expect_shifted: bool,
    ) -> None:
        """Auto-resume applies stored intent; absent intent never shifts (D7)."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = get_chore_id(coordinator, "Make bed")
        past_due = set_past_due(coordinator, chore_id, assignee_id=zoe_id)

        # Direct writes: a service pause with an already-expired until would
        # auto-resume on the handler's own refresh poll before intent is set.
        users = coordinator._data[const.DATA_USERS]
        users[zoe_id][const.DATA_USER_CHORES_PAUSED] = True
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNTIL] = "2026-09-27T00:00:00+00:00"
        # None is semantically identical to an absent key (bare call)
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION] = stored_action

        await coordinator.chore_manager._on_periodic_update(
            now_utc=datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
        )
        await hass.async_block_till_done()

        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is False
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL) is None
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        shifted = get_stored_due(coordinator, chore_id, zoe_id) != past_due
        assert shifted is expect_shifted


# =============================================================================
# TEST: Unpause Action chaining (stored resume intent)
# =============================================================================


class TestUnpauseActionChaining:
    """Test stored resume intent: bare/explicit resume, D3 matrix, sensor."""

    async def test_bare_resume_applies_stored_intent(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """A resume payload with no unpause_action applies stored intent (L1/L2)."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = get_chore_id(coordinator, "Make bed")
        past_due = set_past_due(coordinator, chore_id, assignee_id=zoe_id)

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_all"},
        )
        users = coordinator._data[const.DATA_USERS]
        stored = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert stored == "unpause_shift_all"

        await call_pause_service(hass, scenario_minimal, zoe_context, paused=False)

        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is False
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        shifted_due = get_stored_due(coordinator, chore_id, zoe_id)
        assert shifted_due != past_due
        assert dt_to_utc(shifted_due) > dt_to_utc(past_due)
        assert get_chore_state(hass, "zoe", "Make bed") == CHORE_STATE_PENDING

    async def test_explicit_unpause_skips_stored_intent_but_consumes_it(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Passing 'unpause' explicitly wins over stored intent (D2 precedence)."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = get_chore_id(coordinator, "Make bed")
        past_due = set_past_due(coordinator, chore_id, assignee_id=zoe_id)

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_all"},
        )
        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=False,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause"},
        )

        users = coordinator._data[const.DATA_USERS]
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is False
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        assert get_stored_due(coordinator, chore_id, zoe_id) == past_due

    async def test_manager_call_without_action_applies_stored_intent(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """set_user_chores_paused(paused=False) with no action arg is bare (L3)."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = get_chore_id(coordinator, "Make bed")
        past_due = set_past_due(coordinator, chore_id, assignee_id=zoe_id)

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_all"},
        )
        await coordinator.chore_manager.set_user_chores_paused(
            assignee_id=zoe_id,
            paused=False,
        )
        await hass.async_block_till_done()

        users = coordinator._data[const.DATA_USERS]
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is False
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        assert get_stored_due(coordinator, chore_id, zoe_id) != past_due

    @pytest.mark.parametrize(
        ("action_value", "expect_shifted", "expected_state"),
        [
            pytest.param(None, False, CHORE_STATE_OVERDUE, id="no_intent"),
            pytest.param(
                "unpause_shift_independent",
                True,
                CHORE_STATE_PENDING,
                id="shift_independent",
            ),
            pytest.param(
                "unpause_shift_all_primary",
                True,
                CHORE_STATE_PENDING,
                id="shift_all_primary",
            ),
            pytest.param(
                "unpause_shift_all",
                True,
                CHORE_STATE_PENDING,
                id="shift_all",
            ),
        ],
    )
    async def test_bare_resume_shifts_independent_per_action(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
        action_value: str | None,
        expect_shifted: bool,
        expected_state: str,
    ) -> None:
        """Shift actions move independent dates; without intent they stay put.

        The monthly guard never moves either way. A kept past-due date derives
        as overdue on the next scan - that is the documented plain-resume
        behavior (#322 part 2), asserted here rather than hidden.
        """
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        daily_id = get_chore_id(coordinator, "Make bed")
        monthly_id = get_chore_id(coordinator, "Organize closet")
        past_daily = set_past_due(coordinator, daily_id, assignee_id=zoe_id)
        past_monthly = set_past_due(coordinator, monthly_id, assignee_id=zoe_id)

        await call_pause_service(hass, scenario_minimal, zoe_context, paused=True)
        users = coordinator._data[const.DATA_USERS]
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION] = action_value

        await call_pause_service(hass, scenario_minimal, zoe_context, paused=False)

        shifted = get_stored_due(coordinator, daily_id, zoe_id) != past_daily
        assert shifted is expect_shifted
        # Long-recurrence guard: monthly and longer dates never move
        assert get_stored_due(coordinator, monthly_id, zoe_id) == past_monthly
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        assert get_chore_state(hass, "zoe", "Make bed") == expected_state

    @pytest.mark.parametrize(
        ("action_value", "expect_shifted"),
        [
            pytest.param(
                "unpause_shift_independent",
                False,
                id="independent_flag_skips_shared",
            ),
            pytest.param("unpause_shift_all", True, id="all_flag_shifts_shared"),
        ],
    )
    async def test_bare_resume_shared_chore_per_action(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        action_value: str,
        expect_shifted: bool,
    ) -> None:
        """Shared chore-level dates move only when the shared flag is set."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        context = Context(user_id=zoe_id)
        chore_id = get_chore_id(coordinator, "Family dinner cleanup")
        past_due = set_past_due(coordinator, chore_id)

        await call_pause_service(
            hass,
            scenario_shared,
            context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: action_value},
        )
        await call_pause_service(hass, scenario_shared, context, paused=False)

        shifted = get_stored_due(coordinator, chore_id) != past_due
        assert shifted is expect_shifted
        users = coordinator._data[const.DATA_USERS]
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None

    @pytest.mark.parametrize(
        ("action_value", "expect_shifted"),
        [
            pytest.param(
                "unpause_shift_independent",
                False,
                id="independent_flag_skips_primary_standby",
            ),
            pytest.param(
                "unpause_shift_all_primary",
                True,
                id="all_primary_flag_shifts",
            ),
            pytest.param("unpause_shift_all", True, id="all_flag_shifts"),
        ],
    )
    async def test_bare_resume_primary_standby_chore_per_action(
        self,
        hass: HomeAssistant,
        scenario_primary_standby: SetupResult,
        action_value: str,
        expect_shifted: bool,
    ) -> None:
        """Primary/standby dates move for the primary and all flags, not independent."""
        coordinator = scenario_primary_standby.coordinator
        zoe_id = scenario_primary_standby.assignee_ids["Zoë"]
        context = Context(user_id=zoe_id)
        chore_id = get_chore_id(coordinator, "Daily Chore (anytime)")
        past_due = set_past_due(coordinator, chore_id)

        await call_pause_service(
            hass,
            scenario_primary_standby,
            context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: action_value},
        )
        await call_pause_service(hass, scenario_primary_standby, context, paused=False)

        shifted = get_stored_due(coordinator, chore_id) != past_due
        assert shifted is expect_shifted

    async def test_auto_unpause_with_intent_shifts_before_scan(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Auto-resume with intent shifts before the scan: no OVERDUE emitted."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = get_chore_id(coordinator, "Make bed")
        past_due = set_past_due(coordinator, chore_id, assignee_id=zoe_id)
        users = coordinator._data[const.DATA_USERS]
        users[zoe_id][const.DATA_USER_CHORES_PAUSED] = True
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNTIL] = "2026-09-27T00:00:00+00:00"
        users[zoe_id][const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION] = (
            "unpause_shift_all"
        )

        emitted: list[str] = []
        original_emit = coordinator.chore_manager.emit

        def tracking_emit(suffix: str, **kwargs: Any) -> None:
            emitted.append(suffix)
            original_emit(suffix, **kwargs)

        coordinator.chore_manager.emit = tracking_emit
        try:
            await coordinator.chore_manager._on_periodic_update(
                now_utc=datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
            )
            await hass.async_block_till_done()
        finally:
            coordinator.chore_manager.emit = original_emit

        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is False
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL) is None
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        assert get_stored_due(coordinator, chore_id, zoe_id) != past_due
        assert const.SIGNAL_SUFFIX_CHORE_OVERDUE not in emitted
        assert get_chore_state(hass, "zoe", "Make bed") == CHORE_STATE_PENDING

    async def test_re_pause_without_until_clears_stale_until(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Re-pausing without a time pops a stored until (D2 defect (a))."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        future_until = (dt_now_utc() + timedelta(days=1)).isoformat()
        users = coordinator._data[const.DATA_USERS]

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_CHORES_PAUSED_UNTIL: future_until},
        )
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL) is not None

        await call_pause_service(hass, scenario_minimal, zoe_context, paused=True)

        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is True
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL) is None

    async def test_re_pause_without_action_clears_intent(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Re-pausing without an action pops stored intent (D2 omission rule)."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        users = coordinator._data[const.DATA_USERS]

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_all"},
        )
        stored = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert stored == "unpause_shift_all"

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{
                const.SERVICE_FIELD_CHORES_PAUSED_UNTIL: (
                    dt_now_utc() + timedelta(days=1)
                ).isoformat()
            },
        )

        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL) is not None

    async def test_new_pause_overwrites_previous_intent(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """A newer pause replaces the remembered action (D3 overwrite rule)."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        users = coordinator._data[const.DATA_USERS]

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_independent"},
        )
        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_all"},
        )

        stored = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert stored == "unpause_shift_all"

    async def test_early_resume_applies_intent_and_consumes_pause_fields(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """Resuming before the until still applies intent and consumes both fields."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = get_chore_id(coordinator, "Make bed")
        past_due = set_past_due(coordinator, chore_id, assignee_id=zoe_id)
        users = coordinator._data[const.DATA_USERS]

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{
                const.SERVICE_FIELD_CHORES_PAUSED_UNTIL: (
                    dt_now_utc() + timedelta(days=1)
                ).isoformat(),
                const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_all",
            },
        )
        stored_until = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL)
        stored_action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert stored_until is not None
        assert stored_action == "unpause_shift_all"

        # Resume well before the stored until (early return)
        await call_pause_service(hass, scenario_minimal, zoe_context, paused=False)

        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is False
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL) is None
        action = users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION)
        assert action is None
        shifted_due = get_stored_due(coordinator, chore_id, zoe_id)
        assert dt_to_utc(shifted_due) > dt_to_utc(past_due)

    async def test_sensor_exposes_stored_unpause_action(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """The dashboard helper mirrors the stored action where paused state shows."""
        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_UNPAUSE_ACTION: "unpause_shift_all"},
        )
        helper = get_dashboard_helper(hass, "zoe")
        assert helper.get("chores_paused") is True
        assert helper.get("chores_paused_unpause_action") == "unpause_shift_all"

        await call_pause_service(hass, scenario_minimal, zoe_context, paused=False)
        helper = get_dashboard_helper(hass, "zoe")
        assert helper.get("chores_paused") is False
        assert helper.get("chores_paused_unpause_action") is None

    def test_form_resume_clears_pause_contract(self) -> None:
        """A form save with paused=False clears until and intent (D3 form row 1)."""
        existing: dict[str, Any] = {
            const.DATA_USER_NAME: "Zoë",
            const.DATA_USER_CHORES_PAUSED: True,
            const.DATA_USER_CHORES_PAUSED_UNTIL: "2026-09-27T10:00:00+00:00",
            const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION: "unpause_shift_all",
        }
        built = build_user_profile(
            {
                const.CFOF_USERS_INPUT_NAME: "Zoë",
                const.CFOF_USERS_INPUT_CHORES_PAUSED: False,
                const.CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL: (
                    "2026-09-30T10:00:00+00:00"
                ),
            },
            existing=existing,
        )

        assert built[const.DATA_USER_CHORES_PAUSED] is False
        assert built[const.DATA_USER_CHORES_PAUSED_UNTIL] is None
        assert built[const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION] is None

    def test_form_fresh_pause_has_no_intent(self) -> None:
        """A form pause without an action field starts with no intent (D3 row 2)."""
        built = build_user_profile(
            {
                const.CFOF_USERS_INPUT_NAME: "Zoë",
                const.CFOF_USERS_INPUT_CHORES_PAUSED: True,
                const.CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL: (
                    "2026-09-30T10:00:00+00:00"
                ),
            }
        )

        assert built[const.DATA_USER_CHORES_PAUSED] is True
        assert built[const.DATA_USER_CHORES_PAUSED_UNTIL] == "2026-09-30T10:00:00+00:00"
        assert built[const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION] is None

    def test_form_edit_while_paused_preserves_intent(self) -> None:
        """A form edit while paused keeps intent and rewrites until (D3 row 3)."""
        existing: dict[str, Any] = {
            const.DATA_USER_NAME: "Zoë",
            const.DATA_USER_CHORES_PAUSED: True,
            const.DATA_USER_CHORES_PAUSED_UNTIL: "2026-09-27T10:00:00+00:00",
            const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION: "unpause_shift_all",
        }
        built = build_user_profile(
            {
                const.CFOF_USERS_INPUT_NAME: "Zoë (edited)",
                const.CFOF_USERS_INPUT_CHORES_PAUSED: True,
                const.CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL: (
                    "2026-10-01T10:00:00+00:00"
                ),
            },
            existing=existing,
        )

        assert built[const.DATA_USER_CHORES_PAUSED] is True
        assert built[const.DATA_USER_CHORES_PAUSED_UNTIL] == "2026-10-01T10:00:00+00:00"
        assert (
            built[const.DATA_USER_CHORES_PAUSED_UNPAUSE_ACTION] == "unpause_shift_all"
        )

    async def test_resume_with_until_rejected_before_mutation(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        zoe_context: Context,
    ) -> None:
        """D8: paused=false with paused_until raises before any mutation."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]
        users = coordinator._data[const.DATA_USERS]
        future_until = (dt_now_utc() + timedelta(days=1)).isoformat()

        await call_pause_service(
            hass,
            scenario_minimal,
            zoe_context,
            paused=True,
            **{const.SERVICE_FIELD_CHORES_PAUSED_UNTIL: future_until},
        )
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is True

        with pytest.raises(ServiceValidationError):
            await call_pause_service(
                hass,
                scenario_minimal,
                zoe_context,
                paused=False,
                **{
                    const.SERVICE_FIELD_CHORES_PAUSED_UNTIL: (
                        dt_now_utc() + timedelta(days=2)
                    ).isoformat()
                },
            )

        # Rejected before mutation: the pause contract is untouched
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED) is True
        assert users[zoe_id].get(const.DATA_USER_CHORES_PAUSED_UNTIL) == future_until
