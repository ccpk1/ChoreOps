"""Assignee undo claim feature tests.

These tests verify that assignees can undo their own chore/reward claims
without it counting as a disapproval (no stat tracking), while approver/admin
disapproval continues to track stats normally.

Test Organization:
- TestAssigneeUndoChore: Assignee undo for chores
- TestApproverDisapproveChore: Approver disapproval still tracks stats
- TestAssigneeUndoReward: Assignee undo for rewards
- TestSharedFirstUndo: SHARED_FIRST chore undo behavior
- TestMultipleUndos: Repeated undo operations

Coordinator API Reference:
- undo_chore_claim(assignee_id, chore_id) - Assignee removes own claim, no stats
- undo_reward_claim(assignee_id, reward_id) - Assignee removes own reward claim, no stats
- disapprove_chore(approver_name, assignee_id, chore_id) - Approver disapproval, tracks stats
- disapprove_reward(approver_name, assignee_id, reward_id) - Approver disapproval, tracks stats
"""

# pylint: disable=redefined-outer-name
# hass fixture required for HA test setup

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from tests.helpers import (
    CHORE_STATE_CLAIMED,
    CHORE_STATE_PENDING,
    DATA_ASSIGNEE_CHORE_DATA,
    DATA_ASSIGNEE_CHORE_DATA_LAST_DISAPPROVED,
    DATA_ASSIGNEE_CHORE_DATA_PENDING_CLAIM_COUNT,
    DATA_ASSIGNEE_CHORE_DATA_STATE,
    DATA_ASSIGNEE_REWARD_DATA,
    DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

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
    """Load shared scenario: 3 assignees, 1 approver, 8 shared chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario with rewards for reward undo tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_assignee_chore_state(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
) -> str:
    """Get the current state of a chore for a specific assignee."""
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    chore_data = assignee_data.get(DATA_ASSIGNEE_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    return per_chore.get(DATA_ASSIGNEE_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def get_disapproval_stats(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
) -> dict[str, Any]:
    """Get disapproval stats for a assignee/chore combination."""
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    chore_data = assignee_data.get(DATA_ASSIGNEE_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})

    return {
        "last_disapproved": per_chore.get(
            DATA_ASSIGNEE_CHORE_DATA_LAST_DISAPPROVED, ""
        ),
        "pending_count": per_chore.get(DATA_ASSIGNEE_CHORE_DATA_PENDING_CLAIM_COUNT, 0),
    }


def get_chore_stats_disapproved(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
) -> int:
    """Get all-time disapproved count from chore_data periods.

    Stats are stored per-chore in chore_data[chore_id]["periods"]["all_time"]["all_time"]["disapproved"].
    The all_time structure uses nested all_time keys for consistency with other periods.
    """
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    chore_data = assignee_data.get(DATA_ASSIGNEE_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    periods = per_chore.get("periods", {})
    all_time_container = periods.get("all_time", {})
    all_time_data = all_time_container.get("all_time", {})
    return all_time_data.get("disapproved", 0)


def get_reward_pending_count(
    coordinator: Any,
    assignee_id: str,
    reward_id: str,
) -> int:
    """Get pending count for a reward."""
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    reward_data = assignee_data.get(DATA_ASSIGNEE_REWARD_DATA, {})
    reward_entry = reward_data.get(reward_id, {})
    return reward_entry.get(DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0)


# =============================================================================
# KID UNDO CHORE TESTS
# =============================================================================


class TestAssigneeUndoChore:
    """Tests for assignee undo chore claim (no stat tracking)."""

    @pytest.mark.asyncio
    async def test_assignee_undo_removes_claim(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Assignee undo removes chore claim and resets state to pending."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Assignee claims chore
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            assert (
                get_assignee_chore_state(coordinator, assignee_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Assignee undoes claim (no approver_name parameter)
            await coordinator.chore_manager.undo_claim(assignee_id, chore_id)

        # State should be reset to pending
        state = get_assignee_chore_state(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_assignee_undo_no_stat_tracking(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Assignee undo does NOT update last_disapproved or disapproval counters."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Assignee claims chore
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")

            # Get initial stats
            initial_stats = get_disapproval_stats(coordinator, assignee_id, chore_id)
            initial_all_time = get_chore_stats_disapproved(
                coordinator, assignee_id, chore_id
            )

            # Assignee undoes claim
            await coordinator.chore_manager.undo_claim(assignee_id, chore_id)

            # Get final stats
            final_stats = get_disapproval_stats(coordinator, assignee_id, chore_id)
            final_all_time = get_chore_stats_disapproved(
                coordinator, assignee_id, chore_id
            )

        # last_disapproved should NOT be updated (remains None or empty)
        assert final_stats["last_disapproved"] in ("", None)
        assert initial_stats["last_disapproved"] == final_stats["last_disapproved"]

        # All-time disapproved count should NOT increment
        assert final_all_time == initial_all_time
        assert final_all_time == 0

        # Pending count should be decremented
        assert final_stats["pending_count"] == 0

    @pytest.mark.asyncio
    async def test_assignee_undo_clears_approver_claim_notification(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Assignee undo clears approver claim notification for the chore."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager,
            "clear_notification_for_approvers",
            new=AsyncMock(),
        ) as mock_clear:
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.undo_claim(assignee_id, chore_id)
            await hass.async_block_till_done()

        mock_clear.assert_awaited_once_with(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            chore_id,
        )


# =============================================================================
# PARENT DISAPPROVE TESTS (Verify stats still work)
# =============================================================================


class TestApproverDisapproveChore:
    """Tests to verify approver/admin disapproval still tracks stats."""

    @pytest.mark.asyncio
    async def test_approver_disapprove_tracks_stats(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Approver disapproval DOES update last_disapproved and counters."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Assignee claims chore
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")

            # Get initial stats
            initial_all_time = get_chore_stats_disapproved(
                coordinator, assignee_id, chore_id
            )

            # Approver disapproves
            await coordinator.chore_manager.disapprove_chore(
                "Mom", assignee_id, chore_id
            )

            # Get final stats
            final_stats = get_disapproval_stats(coordinator, assignee_id, chore_id)
            final_all_time = get_chore_stats_disapproved(
                coordinator, assignee_id, chore_id
            )

        # last_disapproved SHOULD be updated (non-empty timestamp)
        assert final_stats["last_disapproved"] != ""

        # All-time disapproved count SHOULD increment
        assert final_all_time == initial_all_time + 1
        assert final_all_time == 1

        # State should be reset to pending
        state = get_assignee_chore_state(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_PENDING


# =============================================================================
# KID UNDO REWARD TESTS
# =============================================================================


class TestAssigneeUndoReward:
    """Tests for assignee undo reward claim (no stat tracking)."""

    @pytest.mark.asyncio
    async def test_assignee_undo_reward_clears_approver_claim_notification(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Assignee undo clears approver claim notification for the reward."""
        coordinator = scenario_full.coordinator
        assignee_id = scenario_full.assignee_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        # Ensure enough points to claim reward in scenario
        coordinator.assignees_data[assignee_id][const.DATA_ASSIGNEE_POINTS] = 100.0

        with patch.object(
            coordinator.notification_manager,
            "clear_notification_for_approvers",
            new=AsyncMock(),
        ) as mock_clear:
            await coordinator.reward_manager.redeem(
                approver_name="Môm Astrid Stârblüm",
                assignee_id=assignee_id,
                reward_id=reward_id,
            )
            await coordinator.reward_manager.undo_claim(assignee_id, reward_id)
            await hass.async_block_till_done()

        mock_clear.assert_awaited_once_with(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            reward_id,
        )


# =============================================================================
# SHARED_FIRST UNDO TESTS
# =============================================================================


class TestSharedFirstUndo:
    """Tests for assignee undo with SHARED_FIRST chores."""

    @pytest.mark.asyncio
    async def test_shared_first_undo_resets_all_assignees(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Assignee undo on SHARED_FIRST chore resets ALL assignees to pending."""
        coordinator = scenario_shared.coordinator

        # Get a SHARED_FIRST chore from scenario
        # Find chore with completion_criteria='shared_first'
        shared_first_chore_id = None
        for chore_id in scenario_shared.chore_ids.values():
            chore_info = coordinator.chores_data.get(chore_id, {})
            if chore_info.get("completion_criteria") == "shared_first":
                shared_first_chore_id = chore_id
                break

        if not shared_first_chore_id:
            pytest.skip("scenario_shared has no shared_first chores")

        assignee1_id = scenario_shared.assignee_ids["Zoë"]
        assignee2_id = scenario_shared.assignee_ids["Max!"]
        assignee3_id = scenario_shared.assignee_ids["Lila"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Assignee1 claims the SHARED_FIRST chore
            await coordinator.chore_manager.claim_chore(
                assignee1_id, shared_first_chore_id, "Zoë"
            )

            # Verify assignee1 is claimed, others are completed_by_other
            assert (
                get_assignee_chore_state(
                    coordinator, assignee1_id, shared_first_chore_id
                )
                == CHORE_STATE_CLAIMED
            )

            # Assignee1 undoes the claim
            await coordinator.chore_manager.undo_claim(
                assignee1_id, shared_first_chore_id
            )

        # ALL assignees should be reset to pending
        assert (
            get_assignee_chore_state(coordinator, assignee1_id, shared_first_chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_chore_state(coordinator, assignee2_id, shared_first_chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_chore_state(coordinator, assignee3_id, shared_first_chore_id)
            == CHORE_STATE_PENDING
        )


# =============================================================================
# MULTIPLE UNDO TESTS
# =============================================================================


class TestMultipleUndos:
    """Tests for repeated undo operations."""

    @pytest.mark.asyncio
    async def test_multiple_undos_no_stat_accumulation(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Multiple undo operations do NOT accumulate disapproval stats."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Undo 3 times
            for _ in range(3):
                # Assignee claims chore
                await coordinator.chore_manager.claim_chore(
                    assignee_id, chore_id, "Zoë"
                )
                assert (
                    get_assignee_chore_state(coordinator, assignee_id, chore_id)
                    == CHORE_STATE_CLAIMED
                )

                # Assignee undoes claim
                await coordinator.chore_manager.undo_claim(assignee_id, chore_id)
                assert (
                    get_assignee_chore_state(coordinator, assignee_id, chore_id)
                    == CHORE_STATE_PENDING
                )

            # Get final stats
            final_stats = get_disapproval_stats(coordinator, assignee_id, chore_id)
            final_all_time = get_chore_stats_disapproved(
                coordinator, assignee_id, chore_id
            )

        # last_disapproved should still be None or empty (never set)
        assert final_stats["last_disapproved"] in ("", None)

        # All-time disapproved count should still be 0
        assert final_all_time == 0
