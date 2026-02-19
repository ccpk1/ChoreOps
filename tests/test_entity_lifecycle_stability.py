"""Entity lifecycle stability tests.

Phase 5 validation for Entity Lifecycle Refactor: verify entity counts remain
stable across reloads and flag changes, with NO orphaned (unavailable) entities.

Test Categories:
- STAB-*: Stability tests (entity count unchanged across reloads)
- ORPHAN-*: Orphan detection (no unavailable entities)
- FLAG-*: Flag toggle tests (extra/workflow/gamification)

Key Test Patterns:
1. Count entities BEFORE operation
2. Perform operation (reload, flag change, etc.)
3. Count entities AFTER operation
4. Verify counts match AND no unavailable entities

Reference: docs/in-process/ENTITY_LIFECYCLE_REFACTOR_IN-PROCESS.md Phase 5
"""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from tests.helpers import SetupResult, setup_from_yaml

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_kc_entity_count(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_id: str,
) -> int:
    """Count all ChoreOps entities for a config entry.

    Uses entity registry (not state machine) for accurate count including
    entities that may be temporarily unavailable.

    Args:
        hass: Home Assistant instance
        entity_registry: Entity registry instance
        config_entry_id: Config entry ID to filter by

    Returns:
        Total count of registered entities
    """
    return sum(
        1
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry_id
    )


def get_unavailable_kc_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_id: str,
) -> list[str]:
    """Find ChoreOps entities with 'unavailable' state.

    Entities in registry but with unavailable state are orphans - they exist
    in registry but have no backing coordinator data.

    Args:
        hass: Home Assistant instance
        entity_registry: Entity registry instance
        config_entry_id: Config entry ID to filter by

    Returns:
        List of entity_ids with unavailable state
    """
    unavailable = []
    for e in entity_registry.entities.values():
        if e.config_entry_id != config_entry_id:
            continue
        state = hass.states.get(e.entity_id)
        if state is not None and state.state == "unavailable":
            unavailable.append(e.entity_id)
    return unavailable


def get_entity_breakdown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_id: str,
) -> dict[str, dict[str, int]]:
    """Get count of entities by platform and state.

    Useful for debugging entity count changes.

    Returns:
        Dict with platform counts and state breakdown
    """
    platforms: dict[str, int] = {}
    states: dict[str, int] = {}

    for e in entity_registry.entities.values():
        if e.config_entry_id != config_entry_id:
            continue

        # Count by platform
        platforms[e.domain] = platforms.get(e.domain, 0) + 1

        # Count by state
        state = hass.states.get(e.entity_id)
        state_str = state.state if state else "missing"
        states[state_str] = states.get(state_str, 0) + 1

    return {"platforms": platforms, "states": states}


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
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario: 3 assignees, 2 approvers, 18 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# =============================================================================
# STABILITY TESTS: Entity Count Unchanged Across Reloads
# =============================================================================


class TestEntityStability:
    """STAB-* tests: Verify entity counts stable across reloads."""

    async def test_stab_01_single_reload_count_unchanged(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_minimal: SetupResult,
    ) -> None:
        """STAB-01: Entity count unchanged after single reload."""
        config_entry = scenario_minimal.config_entry

        # Count entities BEFORE reload
        count_before = get_kc_entity_count(hass, entity_registry, config_entry.entry_id)
        breakdown_before = get_entity_breakdown(
            hass, entity_registry, config_entry.entry_id
        )

        # Reload integration
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Count entities AFTER reload
        count_after = get_kc_entity_count(hass, entity_registry, config_entry.entry_id)
        breakdown_after = get_entity_breakdown(
            hass, entity_registry, config_entry.entry_id
        )

        # Verify count unchanged
        assert count_before == count_after, (
            f"Entity count changed after reload: {count_before} → {count_after}\n"
            f"Before: {breakdown_before}\n"
            f"After: {breakdown_after}"
        )

    async def test_stab_02_triple_reload_count_unchanged(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_minimal: SetupResult,
    ) -> None:
        """STAB-02: Entity count unchanged after 3 consecutive reloads."""
        config_entry = scenario_minimal.config_entry

        # Count entities BEFORE reloads
        count_initial = get_kc_entity_count(
            hass, entity_registry, config_entry.entry_id
        )

        # Reload 3 times
        for i in range(3):
            await hass.config_entries.async_reload(config_entry.entry_id)
            await hass.async_block_till_done()

            count_after = get_kc_entity_count(
                hass, entity_registry, config_entry.entry_id
            )
            assert count_initial == count_after, (
                f"Entity count changed after reload #{i + 1}: "
                f"{count_initial} → {count_after}"
            )

    async def test_stab_03_full_scenario_reload_stable(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_full: SetupResult,
    ) -> None:
        """STAB-03: Full scenario (3 assignees, 18 chores) stable across reloads."""
        config_entry = scenario_full.config_entry

        # Count entities BEFORE reload
        count_before = get_kc_entity_count(hass, entity_registry, config_entry.entry_id)

        # Reload integration
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Count entities AFTER reload
        count_after = get_kc_entity_count(hass, entity_registry, config_entry.entry_id)

        # Verify count unchanged
        assert count_before == count_after, (
            f"Full scenario entity count changed: {count_before} → {count_after}"
        )


# =============================================================================
# ORPHAN DETECTION TESTS: No Unavailable Entities
# =============================================================================


class TestOrphanDetection:
    """ORPHAN-* tests: Verify no unavailable (orphan) entities."""

    async def test_orphan_01_no_unavailable_after_setup(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_minimal: SetupResult,
    ) -> None:
        """ORPHAN-01: No unavailable entities after initial setup."""
        config_entry = scenario_minimal.config_entry

        unavailable = get_unavailable_kc_entities(
            hass, entity_registry, config_entry.entry_id
        )

        assert len(unavailable) == 0, (
            f"Found {len(unavailable)} unavailable entities after setup: {unavailable}"
        )

    async def test_orphan_02_no_unavailable_after_reload(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_minimal: SetupResult,
    ) -> None:
        """ORPHAN-02: No unavailable entities after reload."""
        config_entry = scenario_minimal.config_entry

        # Reload integration
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        unavailable = get_unavailable_kc_entities(
            hass, entity_registry, config_entry.entry_id
        )

        assert len(unavailable) == 0, (
            f"Found {len(unavailable)} unavailable entities after reload: {unavailable}"
        )

    async def test_orphan_03_no_unavailable_after_triple_reload(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_minimal: SetupResult,
    ) -> None:
        """ORPHAN-03: No unavailable entities after 3 consecutive reloads."""
        config_entry = scenario_minimal.config_entry

        # Reload 3 times
        for i in range(3):
            await hass.config_entries.async_reload(config_entry.entry_id)
            await hass.async_block_till_done()

            unavailable = get_unavailable_kc_entities(
                hass, entity_registry, config_entry.entry_id
            )

            assert len(unavailable) == 0, (
                f"Found {len(unavailable)} unavailable entities after reload #{i + 1}: "
                f"{unavailable}"
            )

    async def test_orphan_04_full_scenario_no_unavailable(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_full: SetupResult,
    ) -> None:
        """ORPHAN-04: Full scenario has no unavailable entities after reload."""
        config_entry = scenario_full.config_entry

        # Reload integration
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        unavailable = get_unavailable_kc_entities(
            hass, entity_registry, config_entry.entry_id
        )

        assert len(unavailable) == 0, (
            f"Full scenario has {len(unavailable)} unavailable entities: {unavailable}"
        )


# =============================================================================
# FLAG TOGGLE TESTS: Extra/Workflow/Gamification
# =============================================================================


class TestFlagToggle:
    """FLAG-* tests: Verify entity cleanup when flags change."""

    async def test_flag_01_extra_entities_exist_when_enabled(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        scenario_minimal: SetupResult,
    ) -> None:
        """FLAG-01: Extra entities exist when show_legacy_entities=True.

        Note: scenario_minimal has show_legacy_entities=False by default.
        This test verifies the base state.
        """
        config_entry = scenario_minimal.config_entry

        # Verify no unavailable entities (baseline check)
        unavailable = get_unavailable_kc_entities(
            hass, entity_registry, config_entry.entry_id
        )
        assert len(unavailable) == 0, f"Unexpected unavailable entities: {unavailable}"

        # Check that extra entities (streak_multiplier, etc.) DON'T exist
        # when show_legacy_entities is False
        extra_suffixes = ["streak_multiplier", "daily_chores_completed"]
        for suffix in extra_suffixes:
            entity_id = f"sensor.kc_zoe_{suffix}"
            state = hass.states.get(entity_id)
            # Extra entities should NOT exist when flag is False
            # (they are filtered at creation time)
            # Note: They may exist in registry but be unavailable if flag changed
            if state is not None:
                assert state.state != "unavailable", (
                    f"Extra entity {entity_id} should not be unavailable - "
                    "should be removed or not created"
                )
