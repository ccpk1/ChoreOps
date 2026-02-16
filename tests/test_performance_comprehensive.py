"""Performance testing for KidsChores.

Measures actual expensive operations:
- Badge checking operations
- Overdue chore checking
- Storage persistence operations
- Entity creation and registration

**Run with default scenario (scenario_stress.yaml)**:
    pytest tests/test_performance_comprehensive.py -s --tb=short

**Run with custom scenario**:
    PERF_SCENARIO=scenario_full.yaml pytest tests/test_performance_comprehensive.py -s
"""

from datetime import datetime
import json
import logging
import os
import time
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.kidschores.utils.dt_utils import dt_now_utc
from tests.helpers import setup_from_yaml

pytestmark = pytest.mark.performance

# Default scenario - override via PERF_SCENARIO env var
DEFAULT_SCENARIO = "tests/scenarios/scenario_stress.yaml"


def save_performance_results(scenario_name: str, results: dict[str, Any]) -> None:
    """Save performance results to tests/performance_results.json for trend analysis."""
    results_file = "tests/performance_results.json"

    # Load existing results
    all_results: dict[str, list[dict[str, Any]]] = {}
    if os.path.exists(results_file):
        try:
            with open(results_file) as f:
                all_results = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Add timestamp and scenario info
    results["timestamp"] = datetime.now().isoformat()
    results["scenario"] = scenario_name

    # Store under scenario name
    if scenario_name not in all_results:
        all_results[scenario_name] = []

    all_results[scenario_name].append(results)

    # Keep only last 50 runs per scenario to prevent file bloat
    all_results[scenario_name] = all_results[scenario_name][-50:]

    # Save results
    try:
        with open(results_file, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"📝 Results saved to {results_file}")
    except Exception as e:
        print(f"⚠️  Could not save results: {e}")


async def run_performance_test(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
    scenario_file: str,
) -> dict[str, Any]:
    """Run performance measurements on any scenario.

    Args:
        hass: Home Assistant instance
        mock_hass_users: Mock user fixtures
        scenario_file: Path to scenario YAML file

    Returns:
        Performance data dictionary
    """
    setup_result = await setup_from_yaml(hass, mock_hass_users, scenario_file)
    config_entry = setup_result.config_entry
    coordinator = config_entry.runtime_data

    # Test badge checking for all kids (via GamificationManager)
    badge_start = time.perf_counter()
    for kid_id in coordinator.kids_data:
        coordinator.gamification_manager._mark_dirty(kid_id)
    coordinator.gamification_manager._evaluate_pending_kids()
    badge_duration_ms = (time.perf_counter() - badge_start) * 1000

    # Test overdue checking
    with (
        patch.object(
            coordinator.notification_manager, "notify_kid_translated", new=AsyncMock()
        ),
        patch.object(
            coordinator.notification_manager,
            "notify_parents_translated",
            new=AsyncMock(),
        ),
    ):
        overdue_start = time.perf_counter()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        overdue_duration_ms = (time.perf_counter() - overdue_start) * 1000

    # Test persistence
    persist_start = time.perf_counter()
    coordinator._persist()
    persist_queue_us = (time.perf_counter() - persist_start) * 1000000

    # Entity count
    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)

    return {
        "badge_duration_ms": round(badge_duration_ms, 2),
        "overdue_duration_ms": round(overdue_duration_ms, 2),
        "persist_queue_us": round(persist_queue_us, 1),
        "entity_count": len(entities),
        "kids_count": len(coordinator.kids_data),
        "chores_count": len(coordinator.chores_data),
        "badges_count": len(coordinator.badges_data),
        "parents_count": len(coordinator.parents_data),
        "rewards_count": len(coordinator.rewards_data),
    }


@pytest.mark.timeout(300)  # 5 minute timeout for any scenario
async def test_scenario_performance(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Performance test - runs default scenario or PERF_SCENARIO env override.

    Usage:
        # Default (scenario_stress.yaml)
        pytest tests/test_performance_comprehensive.py -s

        # Custom scenario
        PERF_SCENARIO=scenario_full.yaml pytest tests/test_performance_comprehensive.py -s
    """
    # Get scenario from env var or use default
    scenario_env = os.environ.get("PERF_SCENARIO", "")
    if scenario_env:
        scenario_file = f"tests/scenarios/{scenario_env}"
    else:
        scenario_file = DEFAULT_SCENARIO

    scenario_name = os.path.basename(scenario_file).replace(".yaml", "")

    # Suppress Home Assistant debug logging for cleaner output
    ha_logger = logging.getLogger("homeassistant")
    original_level = ha_logger.level
    ha_logger.setLevel(logging.WARNING)

    try:
        print(f"\n📊 Running performance test: {scenario_name}")

        # Run the performance test
        results = await run_performance_test(hass, mock_hass_users, scenario_file)

        # Save results
        save_performance_results(scenario_name, results)

        # Print summary
        print(
            f"🚀 PERFORMANCE: {results['entity_count']} entities | "
            f"Badge: {results['badge_duration_ms']:.2f}ms | "
            f"Overdue: {results['overdue_duration_ms']:.2f}ms | "
            f"Persist: {results['persist_queue_us']:.1f}µs"
        )
        print(
            f"   Dataset: {results['kids_count']} kids, "
            f"{results['chores_count']} chores, "
            f"{results['badges_count']} badges"
        )

        # Performance assertions - scale with entity count
        entity_count = results["entity_count"]
        max_badge_ms = max(1500, entity_count * 3)  # ~3ms per entity baseline
        max_overdue_ms = max(300, entity_count * 0.6)  # ~0.6ms per entity baseline

        assert results["badge_duration_ms"] < max_badge_ms, (
            f"Badge check too slow: {results['badge_duration_ms']:.2f}ms "
            f"(limit: {max_badge_ms}ms for {entity_count} entities)"
        )
        assert results["overdue_duration_ms"] < max_overdue_ms, (
            f"Overdue check too slow: {results['overdue_duration_ms']:.2f}ms "
            f"(limit: {max_overdue_ms}ms for {entity_count} entities)"
        )
        assert results["persist_queue_us"] < 15000, (
            f"Persist queue too slow: {results['persist_queue_us']:.1f}µs"
        )
        assert results["entity_count"] > 0, "No entities created"

    finally:
        ha_logger.setLevel(original_level)
