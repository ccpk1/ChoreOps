"""Test entity cleanup when options change.

Tests that entities are removed immediately when toggling configuration options,
not just on integration reload. Ensures proper EntityRegistry cleanup.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from tests.helpers import CONF_SHOW_LEGACY_ENTITIES
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def init_integration_with_legacy(
    hass: HomeAssistant,
    mock_hass_users: dict,
) -> SetupResult:
    """Initialize integration with legacy entities enabled.

    Uses scenario_minimal.yaml as base, then enables show_legacy_entities
    via options update to trigger entity creation.
    """
    # Setup base scenario first
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )

    # Enable show_legacy_entities flag via options update
    # This triggers entity creation for legacy sensors
    new_options = dict(result.config_entry.options)
    new_options[CONF_SHOW_LEGACY_ENTITIES] = True
    hass.config_entries.async_update_entry(result.config_entry, options=new_options)
    await hass.async_block_till_done()

    return result


async def test_toggle_show_legacy_entities_removes_immediately(
    hass: HomeAssistant,
    init_integration_with_legacy: SetupResult,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that toggling show_legacy_entities removes entities immediately."""
    config_entry = init_integration_with_legacy.config_entry

    # Find legacy entity for Zoë (from scenario_minimal.yaml)
    # Entity ID pattern: sensor.zoe_choreops_chores_completed_total
    # This is the KidChoreCompletionSensor from sensor_legacy.py
    legacy_entity_id = "sensor.zoe_choreops_chores_completed_total"

    # Verify legacy entity exists with show_legacy_entities=True
    entity_before = entity_registry.async_get(legacy_entity_id)
    assert entity_before is not None, (
        f"Legacy entity {legacy_entity_id} should exist with show_legacy_entities=True"
    )

    # Toggle show_legacy_entities to False
    new_options = dict(config_entry.options)
    new_options[CONF_SHOW_LEGACY_ENTITIES] = False
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    await hass.async_block_till_done()

    # Verify entity is immediately removed from registry
    entity_after = entity_registry.async_get(legacy_entity_id)
    assert entity_after is None, (
        f"Legacy entity {legacy_entity_id} should be removed from registry "
        f"when show_legacy_entities=False"
    )
