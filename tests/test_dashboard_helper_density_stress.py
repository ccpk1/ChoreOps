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

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers.setup import setup_from_yaml

RUN_STRESS = os.environ.get("CHOREOPS_RUN_STRESS") == "1"
RECORDER_LIMIT_BYTES = 16 * 1024
SCENARIO_COUNTS = (40, 50, 60, 70, 80, 90, 100)
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

    await coordinator.chore_manager.claim_chore(zoe_id, first_chore_id, "Zoë")
    await hass.async_block_till_done()

    helper_state = hass.states.get("sensor.zoe_choreops_ui_dashboard_helper")
    assert helper_state is not None
    chores = helper_state.attributes.get("chores", [])
    claimed_chore = next(
        chore for chore in chores if chore.get("name") == "Zoë Dense Chore 001"
    )
    assert claimed_chore["state"] in {"claimed", "completed", "waiting"}
