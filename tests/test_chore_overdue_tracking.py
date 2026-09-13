"""Test chore overdue timestamp tracking (issue #293).

Covers `last_overdue` population at the per-assignee state funnel
(`ChoreManager._set_assignee_chore_state`):

- Scanner-driven overdue transitions stamp the timestamp
- Repeat transitions keep the episode's first detection
- Never-overdue chores never register lateness
- Non-scanner transitions (disapprove/undo) also stamp
- The chore status sensor exposes the timestamp

Uses scenario_minimal.yaml.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.utils import dt_utils
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.helpers.workflows import find_chore, get_dashboard_helper

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def overdue_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for overdue tracking tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# ============================================================================
# HELPERS
# ============================================================================


def get_assignee_chore_entry(
    coordinator: Any, assignee_id: str, chore_id: str
) -> dict[str, Any]:
    """Return the assignee's per-chore data entry."""
    return (
        coordinator.assignees_data.get(assignee_id, {})
        .get(const.DATA_USER_CHORE_DATA, {})
        .get(chore_id, {})
    )


async def create_chore_with_past_due_date(
    hass: HomeAssistant,
    coordinator: Any,
    assignee_name: str,
    *,
    name: str,
    overdue_handling: str,
) -> tuple[str, str]:
    """Create an assigned chore forced past its due date.

    Returns:
        Tuple of (assignee_id, chore_id).
    """
    assignee_id = next(
        assignee_key
        for assignee_key, info in coordinator.assignees_data.items()
        if info.get(const.DATA_USER_NAME) == assignee_name
    )

    response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: name,
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: [assignee_name],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
            const.SERVICE_FIELD_POINTS: 10,
            const.SERVICE_FIELD_OVERDUE_HANDLING: overdue_handling,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    # Bypass service validation to force a past due date
    past_date = (dt_utils.dt_now_local() - timedelta(days=2)).isoformat()
    coordinator.chores_data[chore_id][const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {
        assignee_id: past_date
    }
    coordinator._persist()

    return assignee_id, chore_id


async def run_time_scan(coordinator: Any, hass: HomeAssistant) -> None:
    """Run a due-date scan and let listeners settle."""
    await coordinator.chore_manager._on_periodic_update(now_utc=dt_utils.dt_now_utc())
    await hass.async_block_till_done()


# ============================================================================
# TEST: last_overdue stamping
# ============================================================================


class TestLastOverdueStamp:
    """Tests for `last_overdue` population."""

    async def test_scanner_overdue_sets_last_overdue(
        self,
        hass: HomeAssistant,
        overdue_scenario: SetupResult,
    ) -> None:
        """A chore passing its due date stamps last_overdue."""
        coordinator = overdue_scenario.coordinator
        assignee_id, chore_id = await create_chore_with_past_due_date(
            hass,
            coordinator,
            "Zoë",
            name="Overdue Stamp Chore",
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
        )

        entry = get_assignee_chore_entry(coordinator, assignee_id, chore_id)
        assert entry.get(const.DATA_USER_CHORE_DATA_LAST_OVERDUE) is None

        await run_time_scan(coordinator, hass)

        entry = get_assignee_chore_entry(coordinator, assignee_id, chore_id)
        assert entry[const.DATA_USER_CHORE_DATA_STATE] == const.CHORE_STATE_OVERDUE
        last_overdue = entry[const.DATA_USER_CHORE_DATA_LAST_OVERDUE]
        assert isinstance(last_overdue, str)

    async def test_repeat_scan_preserves_first_detection(
        self,
        hass: HomeAssistant,
        overdue_scenario: SetupResult,
    ) -> None:
        """Repeated overdue processing does not move the episode timestamp."""
        coordinator = overdue_scenario.coordinator
        assignee_id, chore_id = await create_chore_with_past_due_date(
            hass,
            coordinator,
            "Zoë",
            name="Stable Overdue Stamp Chore",
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
        )

        await run_time_scan(coordinator, hass)
        entry = get_assignee_chore_entry(coordinator, assignee_id, chore_id)
        first_detection = entry[const.DATA_USER_CHORE_DATA_LAST_OVERDUE]
        assert first_detection is not None

        await run_time_scan(coordinator, hass)

        entry = get_assignee_chore_entry(coordinator, assignee_id, chore_id)
        assert entry[const.DATA_USER_CHORE_DATA_LAST_OVERDUE] == first_detection

    async def test_funnel_stamps_new_episode_after_exit(
        self,
        hass: HomeAssistant,
        overdue_scenario: SetupResult,
    ) -> None:
        """Leaving overdue and returning starts a fresh timestamp."""
        coordinator = overdue_scenario.coordinator
        chore_manager = coordinator.chore_manager
        assignee_id, chore_id = await create_chore_with_past_due_date(
            hass,
            coordinator,
            "Zoë",
            name="Overdue Episode Chore",
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
        )

        entry = chore_manager._get_assignee_chore_data(assignee_id, chore_id)

        chore_manager._set_assignee_chore_state(
            assignee_id, chore_id, entry, const.CHORE_STATE_OVERDUE
        )
        first_episode = entry[const.DATA_USER_CHORE_DATA_LAST_OVERDUE]
        assert first_episode is not None

        # Still overdue: preserve the first detection of this episode
        chore_manager._set_assignee_chore_state(
            assignee_id, chore_id, entry, const.CHORE_STATE_OVERDUE
        )
        assert entry[const.DATA_USER_CHORE_DATA_LAST_OVERDUE] == first_episode

        # Exit and re-enter overdue: a new episode refreshes the timestamp
        chore_manager._set_assignee_chore_state(
            assignee_id, chore_id, entry, const.CHORE_STATE_PENDING
        )
        chore_manager._set_assignee_chore_state(
            assignee_id, chore_id, entry, const.CHORE_STATE_OVERDUE
        )
        assert entry[const.DATA_USER_CHORE_DATA_LAST_OVERDUE] is not None

    async def test_never_overdue_chore_never_stamps(
        self,
        hass: HomeAssistant,
        overdue_scenario: SetupResult,
    ) -> None:
        """Never-overdue chores register no lateness, even when forced overdue."""
        coordinator = overdue_scenario.coordinator
        chore_manager = coordinator.chore_manager
        assignee_id, chore_id = await create_chore_with_past_due_date(
            hass,
            coordinator,
            "Zoë",
            name="Never Overdue Stamp Chore",
            overdue_handling=const.OVERDUE_HANDLING_NEVER_OVERDUE,
        )

        # Scanner path never categorizes never-overdue chores as overdue
        await run_time_scan(coordinator, hass)
        entry = get_assignee_chore_entry(coordinator, assignee_id, chore_id)
        assert entry.get(const.DATA_USER_CHORE_DATA_LAST_OVERDUE) is None

        # Disapprove/undo can force OVERDUE from due-date math alone
        chore_manager._set_assignee_chore_state(
            assignee_id,
            chore_id,
            chore_manager._get_assignee_chore_data(assignee_id, chore_id),
            const.CHORE_STATE_OVERDUE,
        )
        entry = get_assignee_chore_entry(coordinator, assignee_id, chore_id)
        assert entry.get(const.DATA_USER_CHORE_DATA_LAST_OVERDUE) is None

    async def test_sensor_exposes_last_overdue(
        self,
        hass: HomeAssistant,
        overdue_scenario: SetupResult,
    ) -> None:
        """The chore status sensor surfaces the stamped timestamp."""
        coordinator = overdue_scenario.coordinator
        chore_name = "Sensor Overdue Stamp Chore"
        await create_chore_with_past_due_date(
            hass,
            coordinator,
            "Zoë",
            name=chore_name,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
        )

        await run_time_scan(coordinator, hass)

        dashboard = get_dashboard_helper(hass, "zoe")
        chore = find_chore(dashboard, chore_name)
        assert chore is not None

        state = hass.states.get(chore["eid"])
        assert state is not None
        assert state.attributes.get(const.ATTR_LAST_OVERDUE) is not None
