"""Targeted tests for chore runtime entity synchronization.

These tests exercise the Phase 2 runtime sync contract directly without relying
on the older service reload fallback path.
"""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.choreops import const
from custom_components.choreops.coordinator import ChoreOpsDataCoordinator
from tests.helpers import SetupResult, setup_from_yaml

DOMAIN = const.DOMAIN
SERVICE_CREATE_CHORE = const.SERVICE_CREATE_CHORE


def _get_user_id_by_name(coordinator: ChoreOpsDataCoordinator, user_name: str) -> str:
    """Return the user ID for a named assignee."""
    for user_id, user_data in coordinator.assignees_data.items():
        if user_data.get(const.DATA_USER_NAME) == user_name:
            return user_id
    raise AssertionError(f"Assignee not found: {user_name}")


def _get_single_assignee_chore_id(
    coordinator: ChoreOpsDataCoordinator,
    *,
    completion_criteria: str | None = None,
) -> str:
    """Return a chore ID with exactly one assigned assignee.

    Optionally constrain the chore by completion criteria.
    """
    for chore_id, chore_data in coordinator.chores_data.items():
        assigned_ids = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        if len(assigned_ids) != 1:
            continue
        if (
            completion_criteria is not None
            and chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            != completion_criteria
        ):
            continue
        return chore_id
    raise AssertionError("No single-assignee chore available in scenario")


def _sensor_unique_id(entry_id: str, assignee_id: str, chore_id: str) -> str:
    """Return the unique ID for an assignee chore status sensor."""
    return (
        f"{entry_id}_{assignee_id}_{chore_id}"
        f"{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
    )


def _shared_sensor_unique_id(entry_id: str, chore_id: str) -> str:
    """Return the unique ID for a shared chore state sensor."""
    return (
        f"{entry_id}_{chore_id}"
        f"{const.SENSOR_KC_UID_SUFFIX_SHARED_CHORE_GLOBAL_STATE_SENSOR}"
    )


def _button_unique_id(
    entry_id: str,
    assignee_id: str,
    chore_id: str,
    suffix: str,
) -> str:
    """Return the unique ID for a chore workflow button."""
    return f"{entry_id}_{assignee_id}_{chore_id}{suffix}"


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, object],
) -> SetupResult:
    """Load the full test scenario."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


async def test_runtime_sync_create_adds_missing_chore_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    scenario_full: SetupResult,
) -> None:
    """Runtime sync should create status sensors and workflow buttons for a new chore."""
    coordinator = scenario_full.coordinator
    config_entry = scenario_full.config_entry

    with patch.object(
        coordinator,
        "async_sync_chore_entities",
        new=AsyncMock(),
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_CHORE,
            {
                "name": "Runtime Sync Created Chore",
                "assigned_user_names": ["Zoë"],
                "frequency": "daily",
                "due_date": datetime(2099, 1, 1, 9, 0, tzinfo=UTC),
            },
            blocking=True,
            return_response=True,
        )

    assert response is not None
    chore_id = response[const.SERVICE_FIELD_CHORE_CRUD_ID]
    assignee_id = _get_user_id_by_name(coordinator, "Zoë")

    sync_context = coordinator.chore_manager.build_entity_sync_context(
        chore_id,
        mutation="created",
        current_chore=coordinator.chores_data[chore_id],
    )
    result = await coordinator.async_sync_chore_entities(sync_context)
    await hass.async_block_till_done()

    assert result.buttons_created >= 1

    sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        _sensor_unique_id(config_entry.entry_id, assignee_id, chore_id),
    )
    assert sensor_entity_id is not None

    approve_button_entity_id = entity_registry.async_get_entity_id(
        "button",
        DOMAIN,
        _button_unique_id(
            config_entry.entry_id,
            assignee_id,
            chore_id,
            const.BUTTON_KC_UID_SUFFIX_APPROVE,
        ),
    )
    assert approve_button_entity_id is not None


async def test_runtime_sync_assignment_change_adds_and_removes_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    scenario_full: SetupResult,
) -> None:
    """Runtime sync should add new assignee entities and remove orphaned ones."""
    coordinator = scenario_full.coordinator
    config_entry = scenario_full.config_entry
    chore_id = _get_single_assignee_chore_id(
        coordinator,
        completion_criteria=const.COMPLETION_CRITERIA_INDEPENDENT,
    )

    previous_chore = deepcopy(coordinator.chores_data[chore_id])
    old_assignee_id = previous_chore[const.DATA_CHORE_ASSIGNED_USER_IDS][0]
    new_assignee_id = next(
        user_id for user_id in coordinator.assignees_data if user_id != old_assignee_id
    )

    coordinator.chore_manager.update_chore(
        chore_id,
        {const.DATA_CHORE_ASSIGNED_USER_IDS: [new_assignee_id]},
        immediate_persist=True,
    )
    current_chore = deepcopy(coordinator.chores_data[chore_id])

    sync_context = coordinator.chore_manager.build_entity_sync_context(
        chore_id,
        mutation="updated",
        previous_chore=previous_chore,
        current_chore=current_chore,
    )
    result = await coordinator.async_sync_chore_entities(sync_context)
    await hass.async_block_till_done()

    assert result.buttons_created >= 1
    assert result.orphaned_assignee_entities_removed >= 1

    old_sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        _sensor_unique_id(config_entry.entry_id, old_assignee_id, chore_id),
    )
    new_sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        _sensor_unique_id(config_entry.entry_id, new_assignee_id, chore_id),
    )

    assert old_sensor_entity_id is None
    assert new_sensor_entity_id is not None


async def test_runtime_sync_rename_replaces_cached_chore_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    scenario_full: SetupResult,
) -> None:
    """Runtime sync should replace rename-sensitive chore entities."""
    coordinator = scenario_full.coordinator
    config_entry = scenario_full.config_entry
    chore_id = _get_single_assignee_chore_id(
        coordinator,
        completion_criteria=const.COMPLETION_CRITERIA_INDEPENDENT,
    )
    previous_chore = deepcopy(coordinator.chores_data[chore_id])
    assignee_id = previous_chore[const.DATA_CHORE_ASSIGNED_USER_IDS][0]
    new_name = "Runtime Sync Renamed Chore"

    coordinator.chore_manager.update_chore(
        chore_id,
        {const.DATA_CHORE_NAME: new_name},
        immediate_persist=True,
    )
    current_chore = deepcopy(coordinator.chores_data[chore_id])

    sync_context = coordinator.chore_manager.build_entity_sync_context(
        chore_id,
        mutation="updated",
        previous_chore=previous_chore,
        current_chore=current_chore,
    )
    result = await coordinator.async_sync_chore_entities(sync_context)
    await hass.async_block_till_done()

    assert result.sensors_created >= 1

    sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        _sensor_unique_id(config_entry.entry_id, assignee_id, chore_id),
    )
    assert sensor_entity_id is not None

    sensor_state = hass.states.get(sensor_entity_id)
    assert sensor_state is not None
    assert sensor_state.attributes[const.ATTR_CHORE_NAME] == new_name


async def test_runtime_sync_shared_transition_adds_and_removes_shared_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    scenario_full: SetupResult,
) -> None:
    """Runtime sync should add and remove the shared chore sensor on criteria changes."""
    coordinator = scenario_full.coordinator
    config_entry = scenario_full.config_entry
    chore_id = _get_single_assignee_chore_id(coordinator)

    previous_chore = deepcopy(coordinator.chores_data[chore_id])
    coordinator.chore_manager.update_chore(
        chore_id,
        {const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED},
        immediate_persist=True,
    )
    current_chore = deepcopy(coordinator.chores_data[chore_id])

    sync_context = coordinator.chore_manager.build_entity_sync_context(
        chore_id,
        mutation="updated",
        previous_chore=previous_chore,
        current_chore=current_chore,
    )
    result = await coordinator.async_sync_chore_entities(sync_context)
    await hass.async_block_till_done()

    shared_sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        _shared_sensor_unique_id(config_entry.entry_id, chore_id),
    )
    assert shared_sensor_entity_id is not None

    previous_chore = deepcopy(coordinator.chores_data[chore_id])
    coordinator.chore_manager.update_chore(
        chore_id,
        {const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT},
        immediate_persist=True,
    )
    current_chore = deepcopy(coordinator.chores_data[chore_id])

    sync_context = coordinator.chore_manager.build_entity_sync_context(
        chore_id,
        mutation="updated",
        previous_chore=previous_chore,
        current_chore=current_chore,
    )
    result = await coordinator.async_sync_chore_entities(sync_context)
    await hass.async_block_till_done()

    shared_sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        _shared_sensor_unique_id(config_entry.entry_id, chore_id),
    )
    assert shared_sensor_entity_id is None
