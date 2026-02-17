"""Kid undo claim feature tests.

These tests verify that kids can undo their own chore/reward claims
without it counting as a disapproval (no stat tracking), while parent/admin
disapproval continues to track stats normally.

Test Organization:
- TestKidUndoChore: Kid undo for chores
- TestParentDisapproveChore: Parent disapproval still tracks stats
- TestKidUndoReward: Kid undo for rewards
- TestSharedFirstUndo: SHARED_FIRST chore undo behavior
- TestMultipleUndos: Repeated undo operations

Coordinator API Reference:
- undo_chore_claim(kid_id, chore_id) - Kid removes own claim, no stats
- undo_reward_claim(kid_id, reward_id) - Kid removes own reward claim, no stats
- disapprove_chore(parent_name, kid_id, chore_id) - Parent disapproval, tracks stats
- disapprove_reward(parent_name, kid_id, reward_id) - Parent disapproval, tracks stats
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
    DATA_KID_CHORE_DATA,
    DATA_KID_CHORE_DATA_LAST_DISAPPROVED,
    DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT,
    DATA_KID_CHORE_DATA_STATE,
    DATA_KID_REWARD_DATA,
    DATA_KID_REWARD_DATA_PENDING_COUNT,
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
    """Load minimal scenario: 1 kid, 1 parent, 5 chores."""
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
    """Load shared scenario: 3 kids, 1 parent, 8 shared chores."""
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


def get_kid_chore_state(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> str:
    """Get the current state of a chore for a specific kid."""
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.get(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    return per_chore.get(DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def get_disapproval_stats(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> dict[str, Any]:
    """Get disapproval stats for a kid/chore combination."""
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.get(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})

    return {
        "last_disapproved": per_chore.get(DATA_KID_CHORE_DATA_LAST_DISAPPROVED, ""),
        "pending_count": per_chore.get(DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0),
    }


def get_chore_stats_disapproved(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> int:
    """Get all-time disapproved count from chore_data periods.

    Stats are stored per-chore in chore_data[chore_id]["periods"]["all_time"]["all_time"]["disapproved"].
    The all_time structure uses nested all_time keys for consistency with other periods.
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.get(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    periods = per_chore.get("periods", {})
    all_time_container = periods.get("all_time", {})
    all_time_data = all_time_container.get("all_time", {})
    return all_time_data.get("disapproved", 0)


def get_reward_pending_count(
    coordinator: Any,
    kid_id: str,
    reward_id: str,
) -> int:
    """Get pending count for a reward."""
    kid_data = coordinator.kids_data.get(kid_id, {})
    reward_data = kid_data.get(DATA_KID_REWARD_DATA, {})
    reward_entry = reward_data.get(reward_id, {})
    return reward_entry.get(DATA_KID_REWARD_DATA_PENDING_COUNT, 0)


# =============================================================================
# KID UNDO CHORE TESTS
# =============================================================================


class TestKidUndoChore:
    """Tests for kid undo chore claim (no stat tracking)."""

    @pytest.mark.asyncio
    async def test_kid_undo_removes_claim(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Kid undo removes chore claim and resets state to pending."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Kid claims chore
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            assert (
                get_kid_chore_state(coordinator, kid_id, chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Kid undoes claim (no parent_name parameter)
            await coordinator.chore_manager.undo_claim(kid_id, chore_id)

        # State should be reset to pending
        state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_kid_undo_no_stat_tracking(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Kid undo does NOT update last_disapproved or disapproval counters."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Kid claims chore
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")

            # Get initial stats
            initial_stats = get_disapproval_stats(coordinator, kid_id, chore_id)
            initial_all_time = get_chore_stats_disapproved(
                coordinator, kid_id, chore_id
            )

            # Kid undoes claim
            await coordinator.chore_manager.undo_claim(kid_id, chore_id)

            # Get final stats
            final_stats = get_disapproval_stats(coordinator, kid_id, chore_id)
            final_all_time = get_chore_stats_disapproved(coordinator, kid_id, chore_id)

        # last_disapproved should NOT be updated (remains None or empty)
        assert final_stats["last_disapproved"] in ("", None)
        assert initial_stats["last_disapproved"] == final_stats["last_disapproved"]

        # All-time disapproved count should NOT increment
        assert final_all_time == initial_all_time
        assert final_all_time == 0

        # Pending count should be decremented
        assert final_stats["pending_count"] == 0

    @pytest.mark.asyncio
    async def test_kid_undo_clears_parent_claim_notification(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Kid undo clears parent claim notification for the chore."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager,
            "clear_notification_for_parents",
            new=AsyncMock(),
        ) as mock_clear:
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.undo_claim(kid_id, chore_id)
            await hass.async_block_till_done()

        mock_clear.assert_awaited_once_with(
            kid_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            chore_id,
        )


# =============================================================================
# PARENT DISAPPROVE TESTS (Verify stats still work)
# =============================================================================


class TestParentDisapproveChore:
    """Tests to verify parent/admin disapproval still tracks stats."""

    @pytest.mark.asyncio
    async def test_parent_disapprove_tracks_stats(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Parent disapproval DOES update last_disapproved and counters."""
        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Kid claims chore
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")

            # Get initial stats
            initial_all_time = get_chore_stats_disapproved(
                coordinator, kid_id, chore_id
            )

            # Parent disapproves
            await coordinator.chore_manager.disapprove_chore("Mom", kid_id, chore_id)

            # Get final stats
            final_stats = get_disapproval_stats(coordinator, kid_id, chore_id)
            final_all_time = get_chore_stats_disapproved(coordinator, kid_id, chore_id)

        # last_disapproved SHOULD be updated (non-empty timestamp)
        assert final_stats["last_disapproved"] != ""

        # All-time disapproved count SHOULD increment
        assert final_all_time == initial_all_time + 1
        assert final_all_time == 1

        # State should be reset to pending
        state = get_kid_chore_state(coordinator, kid_id, chore_id)
        assert state == CHORE_STATE_PENDING


# =============================================================================
# KID UNDO REWARD TESTS
# =============================================================================


class TestKidUndoReward:
    """Tests for kid undo reward claim (no stat tracking)."""

    @pytest.mark.asyncio
    async def test_kid_undo_reward_clears_parent_claim_notification(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Kid undo clears parent claim notification for the reward."""
        coordinator = scenario_full.coordinator
        kid_id = scenario_full.kid_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        # Ensure enough points to claim reward in scenario
        coordinator.kids_data[kid_id][const.DATA_KID_POINTS] = 100.0

        with patch.object(
            coordinator.notification_manager,
            "clear_notification_for_parents",
            new=AsyncMock(),
        ) as mock_clear:
            await coordinator.reward_manager.redeem(
                parent_name="Môm Astrid Stârblüm",
                kid_id=kid_id,
                reward_id=reward_id,
            )
            await coordinator.reward_manager.undo_claim(kid_id, reward_id)
            await hass.async_block_till_done()

        mock_clear.assert_awaited_once_with(
            kid_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            reward_id,
        )


# =============================================================================
# SHARED_FIRST UNDO TESTS
# =============================================================================


class TestSharedFirstUndo:
    """Tests for kid undo with SHARED_FIRST chores."""

    @pytest.mark.asyncio
    async def test_shared_first_undo_resets_all_kids(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Kid undo on SHARED_FIRST chore resets ALL kids to pending."""
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

        kid1_id = scenario_shared.kid_ids["Zoë"]
        kid2_id = scenario_shared.kid_ids["Max!"]
        kid3_id = scenario_shared.kid_ids["Lila"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Kid1 claims the SHARED_FIRST chore
            await coordinator.chore_manager.claim_chore(
                kid1_id, shared_first_chore_id, "Zoë"
            )

            # Verify kid1 is claimed, others are completed_by_other
            assert (
                get_kid_chore_state(coordinator, kid1_id, shared_first_chore_id)
                == CHORE_STATE_CLAIMED
            )

            # Kid1 undoes the claim
            await coordinator.chore_manager.undo_claim(kid1_id, shared_first_chore_id)

        # ALL kids should be reset to pending
        assert (
            get_kid_chore_state(coordinator, kid1_id, shared_first_chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_kid_chore_state(coordinator, kid2_id, shared_first_chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_kid_chore_state(coordinator, kid3_id, shared_first_chore_id)
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
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Undo 3 times
            for _ in range(3):
                # Kid claims chore
                await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
                assert (
                    get_kid_chore_state(coordinator, kid_id, chore_id)
                    == CHORE_STATE_CLAIMED
                )

                # Kid undoes claim
                await coordinator.chore_manager.undo_claim(kid_id, chore_id)
                assert (
                    get_kid_chore_state(coordinator, kid_id, chore_id)
                    == CHORE_STATE_PENDING
                )

            # Get final stats
            final_stats = get_disapproval_stats(coordinator, kid_id, chore_id)
            final_all_time = get_chore_stats_disapproved(coordinator, kid_id, chore_id)

        # last_disapproved should still be None or empty (never set)
        assert final_stats["last_disapproved"] in ("", None)

        # All-time disapproved count should still be 0
        assert final_all_time == 0
