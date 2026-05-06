"""Opt-in dashboard helper density stress tests.

These tests are skipped by default. Enable them with:

    CHOREOPS_RUN_STRESS=1 pytest tests/test_dashboard_helper_density_stress.py -s

The scenarios under test use the standard Stårblüm family and assign the same
number of independent chores to each assignee so per-user dashboard helper size
can be compared directly at higher densities.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

from custom_components.choreops import const
from tests.helpers.setup import setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

RUN_STRESS = os.environ.get("CHOREOPS_RUN_STRESS") == "1"
RECORDER_LIMIT_BYTES = 16 * 1024
SCENARIO_COUNTS = (40, 50, 60, 70, 80, 90, 100, 120)
ASSIGNEE_SLUGS = ("zoe", "max", "lila")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.stress,
    pytest.mark.skipif(
        not RUN_STRESS,
        reason="Set CHOREOPS_RUN_STRESS=1 to run dense dashboard helper stress tests",
    ),
]


def _get_helper_size(hass: HomeAssistant, assignee_slug: str) -> int:
    """Return the JSON-serialized dashboard helper attribute size in bytes."""
    entity_id = f"sensor.{assignee_slug}_choreops_ui_dashboard_helper"
    helper_state = hass.states.get(entity_id)
    assert helper_state is not None, f"Dashboard helper not found: {entity_id}"
    return len(json.dumps(helper_state.attributes).encode("utf-8"))


def _get_helper_chores(
    hass: HomeAssistant, assignee_slug: str
) -> list[dict[str, object]]:
    """Return merged chores from the main helper and any chore shard helpers."""
    helper_entity_id = f"sensor.{assignee_slug}_choreops_ui_dashboard_helper"
    helper_state = hass.states.get(helper_entity_id)
    assert helper_state is not None, f"Dashboard helper not found: {helper_entity_id}"

    merged_chores = list(helper_state.attributes.get("chores", []))
    dashboard_helpers = helper_state.attributes.get("dashboard_helpers", {})
    chore_helper_eids = dashboard_helpers.get(const.ATTR_CHORE_HELPER_EIDS, [])

    for shard_entity_id in chore_helper_eids:
        shard_state = hass.states.get(shard_entity_id)
        assert shard_state is not None, (
            f"Chore shard helper not found: {shard_entity_id}"
        )
        merged_chores.extend(shard_state.attributes.get("chores", []))

    return merged_chores


@pytest.mark.parametrize("chores_per_assignee", SCENARIO_COUNTS)
async def test_dashboard_helper_size_under_recorder_limit(
    hass: HomeAssistant,
    mock_hass_users: dict[str, object],
    chores_per_assignee: int,
) -> None:
    """Validate dense scenarios stay under the recorder attribute limit."""
    scenario_path = (
        f"tests/scenarios/scenario_density_starblum_{chores_per_assignee}.yaml"
    )
    await setup_from_yaml(hass, mock_hass_users, scenario_path)

    helper_sizes = {
        assignee_slug: _get_helper_size(hass, assignee_slug)
        for assignee_slug in ASSIGNEE_SLUGS
    }
    oversize_helpers: dict[str, int] = {}

    for assignee_slug, helper_size in helper_sizes.items():
        print(
            f"dashboard helper size | chores_per_assignee={chores_per_assignee} "
            f"| assignee={assignee_slug} | bytes={helper_size}"
        )
        if helper_size >= RECORDER_LIMIT_BYTES:
            oversize_helpers[assignee_slug] = helper_size

    assert not oversize_helpers, (
        f"Dashboard helpers exceeded {RECORDER_LIMIT_BYTES} bytes for "
        f"{chores_per_assignee} chores per assignee: {oversize_helpers}"
    )


@pytest.mark.parametrize("chores_per_assignee", SCENARIO_COUNTS)
async def test_dense_scenario_claim_chore_stays_operational(
    hass: HomeAssistant,
    mock_hass_users: dict[str, object],
    chores_per_assignee: int,
) -> None:
    """Verify a representative claim path still works under dense load."""
    scenario_path = (
        f"tests/scenarios/scenario_density_starblum_{chores_per_assignee}.yaml"
    )
    setup_result = await setup_from_yaml(hass, mock_hass_users, scenario_path)
    coordinator = setup_result.coordinator
    zoe_id = setup_result.assignee_ids["Zoë"]
    first_chore_id = setup_result.chore_ids["Zoë Dense Chore 001"]

    await coordinator.ui_manager.async_reconcile_chore_shards_for_users([zoe_id])
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    await coordinator.chore_manager.claim_chore(zoe_id, first_chore_id, "Zoë")
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    chores = _get_helper_chores(hass, "zoe")
    claimed_chore = next(
        chore for chore in chores if chore.get("name") == "Zoë Dense Chore 001"
    )
    assert claimed_chore["state"] in {"claimed", "completed", "waiting"}
