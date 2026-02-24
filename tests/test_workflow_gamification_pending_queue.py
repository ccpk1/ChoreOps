"""Integration tests for GamificationManager pending queue event flow.

Covers manager-level queueing and debounce-batch evaluation entry points:
- chore_approved / chore_disapproved / chore_overdue event paths
- midnight rollover global recalc path
- pending queue drain behavior in evaluation batch
"""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def setup_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for pending queue integration tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class TestGamificationPendingQueueEvents:
    """Manager integration tests for pending queue + event-driven evaluation."""

    async def test_event_paths_mark_assignee_pending_and_batch_drains(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Approved/disapproved/overdue events queue assignee and batch drains queue."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))

        manager._on_chore_approved({"assignee_id": assignee_id})
        manager._on_chore_disapproved({"assignee_id": assignee_id})
        manager._on_chore_overdue({"assignee_id": assignee_id})
        await hass.async_block_till_done()

        assert assignee_id in manager._pending_evaluations

        await manager._evaluate_pending_assignees()
        await hass.async_block_till_done()

        assert assignee_id not in manager._pending_evaluations

        pending_meta = coordinator._data.get(const.DATA_META, {}).get(
            const.DATA_META_PENDING_EVALUATIONS,
            [],
        )
        assert pending_meta == []

    async def test_midnight_rollover_marks_all_assignees_pending(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Midnight rollover uses recalculate-all path and queues all assignees."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager

        await manager._on_midnight_rollover({})
        await hass.async_block_till_done()

        expected_assignees = set(coordinator.assignees_data.keys())
        assert manager._pending_evaluations == expected_assignees

        await manager._evaluate_pending_assignees()
        await hass.async_block_till_done()

        assert manager._pending_evaluations == set()

    async def test_challenge_lifecycle_wrapper_skips_future_window(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Manager lifecycle wrapper skips challenge evaluation before start date."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))

        challenge_id = "challenge-future-window"
        coordinator.challenges_data[challenge_id] = {
            const.DATA_CHALLENGE_INTERNAL_ID: challenge_id,
            const.DATA_CHALLENGE_NAME: "Future window challenge",
            const.DATA_CHALLENGE_TYPE: const.CHALLENGE_TYPE_DAILY_MIN,
            const.DATA_CHALLENGE_TARGET_VALUE: 1,
            const.DATA_CHALLENGE_ASSIGNED_USER_IDS: [assignee_id],
            const.DATA_CHALLENGE_PROGRESS: {
                assignee_id: {const.DATA_CHALLENGE_AWARDED: False}
            },
            const.DATA_CHALLENGE_AWARDED: {},
            const.DATA_CHALLENGE_START_DATE: "2099-01-01",
            const.DATA_CHALLENGE_END_DATE: "2099-12-31",
            const.DATA_CHALLENGE_REWARD_POINTS: 1.0,
            const.DATA_CHALLENGE_CRITERIA: "future",
            const.DATA_CHALLENGE_DESCRIPTION: "future",
            const.DATA_CHALLENGE_ICON: "mdi:trophy",
            const.DATA_CHALLENGE_LABELS: [],
        }

        context = manager._build_evaluation_context(assignee_id)
        assert context is not None

        manager.award_challenge = AsyncMock()
        await manager._evaluate_challenge_for_assignee(
            context,
            challenge_id,
            coordinator.challenges_data[challenge_id],
        )

        manager.award_challenge.assert_not_called()

    async def test_achievement_selected_chore_maps_to_tracked_scope(
        self,
        setup_minimal: SetupResult,
    ) -> None:
        """Achievement selected_chore_id maps to canonical tracked scope."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))
        selected_chore_id = next(iter(coordinator.chores_data.keys()))

        mapped = manager._map_achievement_to_canonical_target(
            assignee_id,
            "achievement-scope",
            {
                const.DATA_ACHIEVEMENT_TYPE: const.ACHIEVEMENT_TYPE_DAILY_MIN,
                const.DATA_ACHIEVEMENT_TARGET_VALUE: 1,
                const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: selected_chore_id,
            },
            {},
        )

        assert mapped.get("tracked_chore_ids") == [selected_chore_id]

    async def test_challenge_selected_chore_maps_to_tracked_scope(
        self,
        setup_minimal: SetupResult,
    ) -> None:
        """Challenge selected_chore_id maps to canonical tracked scope."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))
        selected_chore_id = next(iter(coordinator.chores_data.keys()))

        mapped = manager._map_challenge_to_canonical_target(
            assignee_id,
            "challenge-scope",
            {
                const.DATA_CHALLENGE_TYPE: const.CHALLENGE_TYPE_DAILY_MIN,
                const.DATA_CHALLENGE_TARGET_VALUE: 1,
                const.DATA_CHALLENGE_SELECTED_CHORE_ID: selected_chore_id,
            },
        )

        assert mapped.get("tracked_chore_ids") == [selected_chore_id]

    async def test_source_runtime_context_respects_explicit_empty_scope(
        self,
        setup_minimal: SetupResult,
    ) -> None:
        """Explicit empty tracked scope does not fall back to assigned chores."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))

        captured_tracked: list[list[str]] = []

        def _capture_today_stats(
            _assignee_id: str,
            tracked_chores: list[str],
            *,
            today_iso: str,
            current_badge_progress: dict[str, Any] | None,
        ) -> dict[str, Any]:
            captured_tracked.append(list(tracked_chores))
            return {
                "today_points": 0,
                "today_approved": 0,
                "total_earned": 0,
                "streak_yesterday": False,
            }

        def _capture_today_completion(
            _assignee_id: str,
            tracked_chores: list[str],
            *,
            today_iso: str,
            only_due_today: bool,
        ) -> dict[str, Any]:
            captured_tracked.append(list(tracked_chores))
            return {"approved_count": 0, "total_count": 0, "has_overdue": False}

        coordinator.statistics_manager.get_badge_scoped_today_stats = (
            _capture_today_stats
        )
        coordinator.statistics_manager.get_badge_scoped_today_completion = (
            _capture_today_completion
        )

        context = manager._build_evaluation_context(assignee_id)
        assert context is not None

        manager._build_source_runtime_context(
            context,
            assignee_id=assignee_id,
            canonical_target={
                "target_type": const.CANONICAL_TARGET_TYPE_DAILY_MINIMUM,
                "tracked_chore_ids": [],
            },
        )

        assert captured_tracked
        assert all(tracked == [] for tracked in captured_tracked)

    async def test_achievement_selected_unassigned_chore_not_awarded(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Selected chore outside assignee assignment yields zero in-scope progress."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))

        selected_chore_id = next(iter(coordinator.chores_data.keys()))
        coordinator.chores_data[selected_chore_id][
            const.DATA_CHORE_ASSIGNED_USER_IDS
        ] = ["non-existent-assignee"]

        achievement_id = "achievement-unassigned-scope"
        achievement_data = {
            const.DATA_ACHIEVEMENT_INTERNAL_ID: achievement_id,
            const.DATA_ACHIEVEMENT_NAME: "Unassigned scope achievement",
            const.DATA_ACHIEVEMENT_TYPE: const.ACHIEVEMENT_TYPE_DAILY_MIN,
            const.DATA_ACHIEVEMENT_TARGET_VALUE: 1,
            const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: selected_chore_id,
            const.DATA_ACHIEVEMENT_PROGRESS: {
                assignee_id: {const.DATA_ACHIEVEMENT_AWARDED: False}
            },
            const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS: [assignee_id],
            const.DATA_ACHIEVEMENT_REWARD_POINTS: 1.0,
            const.DATA_ACHIEVEMENT_CRITERIA: "test",
            const.DATA_ACHIEVEMENT_DESCRIPTION: "test",
            const.DATA_ACHIEVEMENT_ICON: "mdi:trophy",
            const.DATA_ACHIEVEMENT_LABELS: [],
        }

        context = manager._build_evaluation_context(assignee_id)
        assert context is not None

        manager.award_achievement = AsyncMock()
        await manager._evaluate_achievement_for_assignee(
            context,
            achievement_id,
            achievement_data,
        )
        await hass.async_block_till_done()

        manager.award_achievement.assert_not_called()
