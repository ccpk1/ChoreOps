"""Performance baseline test for KidsChores coordinator.

Measures performance of instrumented coordinator methods to establish baseline
metrics before optimization work begins.

**Run only when needed**: pytest tests/test_performance.py -v -m performance

**DEPRECATED**: scenario_full fixture not yet defined. This test is scheduled
for Phase 9 when scenario fixtures are completed.
"""

# Accessing coordinator internals for perf testing

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops.utils.dt_utils import dt_now_utc
from tests.helpers import CHORE_STATE_APPROVED, CHORE_STATE_CLAIMED

pytestmark = pytest.mark.performance


@pytest.mark.skip(reason="scenario_full fixture not yet defined - Phase 9 work")
@pytest.mark.asyncio
async def test_performance_baseline_with_scenario_full(
    hass: HomeAssistant,
    scenario_full: tuple[Any, dict[str, str]],
) -> None:
    """Capture baseline performance with full scenario data.

    Uses scenario_full fixture: 3 kids, 7 chores, 5 badges, realistic data.

    Run with: pytest tests/test_performance.py -v -s -m performance
    """
    config_entry, _ = scenario_full  # name_to_id_map unused but needed for fixture
    coordinator = config_entry.runtime_data

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
        # Test 1: Check overdue chores (O(chores × kids))
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Test 2: Persist operation
        coordinator._persist()

        # Test 3: Badge evaluation for each kid (via GamificationManager)
        for kid_id in coordinator.kids_data:
            coordinator.gamification_manager._mark_dirty(kid_id)
        # Trigger immediate evaluation
        coordinator.gamification_manager._evaluate_pending_kids()

        # Test 4: Parent notifications (via NotificationManager directly)
        if coordinator.parents_data and coordinator.kids_data:
            first_kid_id = list(coordinator.kids_data.keys())[0]
            await coordinator.notification_manager.notify_parents_translated(
                first_kid_id,
                "notification_title_chore_claimed",
                "notification_message_chore_claimed",
                message_data={"kid_name": "Test", "chore_name": "Performance Test"},
            )

        # Test 5: Entity cleanup
        await coordinator._remove_orphaned_kid_chore_entities()

        # Test 6: Chore claim operation
        if coordinator.chores_data and coordinator.kids_data:
            # Find a claimable chore (one not already claimed/approved)
            kid_id = list(coordinator.kids_data.keys())[0]
            kid_info = coordinator.kids_data[kid_id]
            chore_data = kid_info.get("chore_data", {})

            # Find a chore assigned to this kid that isn't already claimed/approved
            claimable_chore_id = None
            for chore_id, chore_info in coordinator.chores_data.items():
                kid_chore_state = chore_data.get(chore_id, {}).get("state")
                if kid_id in chore_info.get(
                    "assigned_kids", []
                ) and kid_chore_state not in (
                    CHORE_STATE_CLAIMED,
                    CHORE_STATE_APPROVED,
                ):
                    claimable_chore_id = chore_id
                    break

            if claimable_chore_id:
                await coordinator.chore_manager.claim_chore(
                    kid_id, claimable_chore_id, "test_user"
                )

        # Test 7: Chore approval and point addition
        if coordinator.chores_data and coordinator.kids_data:
            # Find a claimed chore to approve
            kid_id = list(coordinator.kids_data.keys())[0]
            kid_info = coordinator.kids_data[kid_id]
            chore_data = kid_info.get("chore_data", {})

            # Find a chore in claimed state
            chore_id_to_approve = None
            for chore_id, cd in chore_data.items():
                if cd.get("state") == CHORE_STATE_CLAIMED:
                    chore_id_to_approve = chore_id
                    break

            if chore_id_to_approve:
                await coordinator.chore_manager.approve_chore(
                    "test_user", kid_id, chore_id_to_approve
                )

        # Test 8: Bulk operations - approve multiple chores
        if len(coordinator.kids_data) >= 2 and len(coordinator.chores_data) >= 2:
            operations_count = 0
            for kid_id in list(coordinator.kids_data.keys())[:2]:  # Just first 2 kids
                kid_info = coordinator.kids_data[kid_id]
                chore_data = kid_info.get("chore_data", {})

                # Find up to 2 chores per kid we can work with
                for chore_id, chore_info in list(coordinator.chores_data.items())[:2]:
                    kid_chore_state = chore_data.get(chore_id, {}).get("state")
                    if kid_id in chore_info.get(
                        "assigned_kids", []
                    ) and kid_chore_state not in (
                        CHORE_STATE_CLAIMED,
                        CHORE_STATE_APPROVED,
                    ):
                        # Reset chore state to pending first
                        coordinator._process_chore_state(kid_id, chore_id, "pending")
                        # Claim it
                        await coordinator.chore_manager.claim_chore(
                            kid_id, chore_id, "test_user"
                        )
                        # Approve it
                        await coordinator.chore_manager.approve_chore(
                            "test_user", kid_id, chore_id
                        )
                        operations_count += 2
                        if (
                            operations_count >= 6
                        ):  # Limit to avoid test running too long
                            break
                if operations_count >= 6:
                    break
