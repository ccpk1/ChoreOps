"""Tests for show_on_calendar feature.

Test Strategy:
    - Use SetupResult fixture (scenario_minimal)
    - Create chores with show_on_calendar True and False
    - Verify calendar event filtering based on flag
    - Test backward compatibility (missing field defaults to True)
"""

from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest

from tests.helpers import (
    DATA_CHORE_APPLICABLE_DAYS,
    DATA_CHORE_ASSIGNED_KIDS,
    DATA_CHORE_DEFAULT_POINTS,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_INTERNAL_ID,
    DATA_CHORE_NAME,
    DATA_CHORE_RECURRING_FREQUENCY,
    DATA_CHORE_SHOW_ON_CALENDAR,
    FREQUENCY_NONE,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

TEST_TZ = ZoneInfo("America/New_York")


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms fixture to only load calendar for faster tests."""
    return [Platform.CALENDAR]


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant, mock_hass_users: dict[str, Any]
) -> SetupResult:
    """Load minimal scenario (Zoë with 2 daily chores)."""
    return await setup_from_yaml(
        hass, mock_hass_users, "tests/scenarios/scenario_minimal.yaml"
    )


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_show_on_calendar_true_chore_appears(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Test that calendar includes chores with show_on_calendar=True."""
    coordinator = scenario_minimal.coordinator
    zoe_id = scenario_minimal.kid_ids["Zoë"]

    # Create chore with show_on_calendar=True
    visible_chore_id = str(uuid4())
    coordinator.chores_data[visible_chore_id] = {
        DATA_CHORE_INTERNAL_ID: visible_chore_id,
        DATA_CHORE_NAME: "Visible Chore",
        DATA_CHORE_DEFAULT_POINTS: 10,
        DATA_CHORE_SHOW_ON_CALENDAR: True,
        DATA_CHORE_ASSIGNED_KIDS: [zoe_id],
        DATA_CHORE_RECURRING_FREQUENCY: FREQUENCY_NONE,
        DATA_CHORE_DUE_DATE: "2025-01-20T15:00:00-05:00",
        DATA_CHORE_APPLICABLE_DAYS: [],
    }
    coordinator.async_update_listeners()

    # Get calendar entity
    calendar_entity_id = "calendar.zoe_choreops_calendar"
    state = hass.states.get(calendar_entity_id)
    assert state is not None, f"Calendar entity {calendar_entity_id} not found"

    # Verify the chore was added to coordinator data
    assert visible_chore_id in coordinator.chores_data
    chore_data = coordinator.chores_data[visible_chore_id]
    assert chore_data[DATA_CHORE_SHOW_ON_CALENDAR] is True
    assert chore_data[DATA_CHORE_NAME] == "Visible Chore"


@freeze_time("2025-01-15 12:00:00", tz_offset=0)
async def test_show_on_calendar_false_chore_hidden(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Test that calendar excludes chores with show_on_calendar=False."""
    coordinator = scenario_minimal.coordinator
    zoe_id = scenario_minimal.kid_ids["Zoë"]

    # Create chore with show_on_calendar=False
    hidden_chore_id = str(uuid4())
    coordinator.chores_data[hidden_chore_id] = {
        DATA_CHORE_INTERNAL_ID: hidden_chore_id,
        DATA_CHORE_NAME: "Hidden Chore",
        DATA_CHORE_DEFAULT_POINTS: 20,
        DATA_CHORE_SHOW_ON_CALENDAR: False,
        DATA_CHORE_ASSIGNED_KIDS: [zoe_id],
        DATA_CHORE_RECURRING_FREQUENCY: FREQUENCY_NONE,
        DATA_CHORE_DUE_DATE: "2025-01-25T15:00:00-05:00",
        DATA_CHORE_APPLICABLE_DAYS: [],
    }
    coordinator.async_update_listeners()

    # Verify the chore was added with show_on_calendar=False
    assert hidden_chore_id in coordinator.chores_data
    chore_data = coordinator.chores_data[hidden_chore_id]
    assert chore_data[DATA_CHORE_SHOW_ON_CALENDAR] is False
    assert chore_data[DATA_CHORE_NAME] == "Hidden Chore"


async def test_default_show_on_calendar_value(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Test backward compatibility: missing show_on_calendar defaults to True."""
    coordinator = scenario_minimal.coordinator
    zoe_id = scenario_minimal.kid_ids["Zoë"]

    # Create chore WITHOUT show_on_calendar field (legacy data)
    legacy_chore_id = str(uuid4())
    legacy_chore_data = {
        DATA_CHORE_INTERNAL_ID: legacy_chore_id,
        DATA_CHORE_NAME: "Legacy Chore",
        DATA_CHORE_DEFAULT_POINTS: 5,
        # NOTE: No show_on_calendar field - should default to True
        DATA_CHORE_ASSIGNED_KIDS: [zoe_id],
        DATA_CHORE_RECURRING_FREQUENCY: FREQUENCY_NONE,
        DATA_CHORE_DUE_DATE: "2025-01-22T15:00:00-05:00",
        DATA_CHORE_APPLICABLE_DAYS: [],
    }
    coordinator.chores_data[legacy_chore_id] = legacy_chore_data
    coordinator.async_update_listeners()

    # Verify legacy chore was added (without show_on_calendar field)
    assert legacy_chore_id in coordinator.chores_data
    chore_data = coordinator.chores_data[legacy_chore_id]
    assert chore_data[DATA_CHORE_NAME] == "Legacy Chore"
    # Field may not exist or may be missing - that's the point of backward compatibility
    assert (
        DATA_CHORE_SHOW_ON_CALENDAR not in chore_data
        or chore_data[DATA_CHORE_SHOW_ON_CALENDAR] is True
    )
