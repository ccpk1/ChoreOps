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

        manager._on_chore_approved({"user_id": assignee_id})
        manager._on_chore_disapproved({"user_id": assignee_id})
        manager._on_chore_overdue({"user_id": assignee_id})
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
        """Midnight rollover drains the global pending queue immediately."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        expected_assignees = set(coordinator.assignees_data.keys())

        evaluated: list[str] = []

        async def _capture_evaluation(assignee_id: str) -> None:
            evaluated.append(assignee_id)

        manager._evaluate_assignee = _capture_evaluation

        await manager._on_midnight_rollover({})
        await hass.async_block_till_done()

        assert manager._pending_evaluations == set()
        assert set(evaluated) == expected_assignees

        pending_meta = coordinator._data.get(const.DATA_META, {}).get(
            const.DATA_META_PENDING_EVALUATIONS,
            [],
        )
        assert pending_meta == []

    async def test_midnight_catchup_payload_uses_same_immediate_drain_path(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Startup catch-up payload reuses the same immediate midnight drain path."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        expected_assignees = set(coordinator.assignees_data.keys())

        evaluated: list[str] = []

        async def _capture_evaluation(assignee_id: str) -> None:
            evaluated.append(assignee_id)

        manager._evaluate_assignee = _capture_evaluation

        await manager._on_midnight_rollover({"catch_up": True})
        await hass.async_block_till_done()

        assert manager._pending_evaluations == set()
        assert set(evaluated) == expected_assignees

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

    async def test_scoped_all_time_stats_aggregates_only_tracked_chores(
        self,
        setup_minimal: SetupResult,
    ) -> None:
        """Scoped all-time stats helper sums only the tracked chore buckets."""
        coordinator = setup_minimal.coordinator
        assignee_id = next(iter(coordinator.assignees_data.keys()))
        chore_ids = list(coordinator.chores_data.keys())
        assert len(chore_ids) >= 2
        chore_a, chore_b = chore_ids[0], chore_ids[1]

        assignee_data = coordinator.assignees_data[assignee_id]
        chore_data = assignee_data.setdefault(const.DATA_USER_CHORE_DATA, {})
        for chore_id, approved in ((chore_a, 3), (chore_b, 7)):
            chore_data.setdefault(chore_id, {}).setdefault(
                const.DATA_USER_CHORE_DATA_PERIODS, {}
            )[const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME] = {
                const.PERIOD_ALL_TIME: {
                    const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: approved,
                    const.DATA_USER_CHORE_DATA_PERIOD_POINTS: approved * 5.0,
                }
            }

        scoped = coordinator.statistics_manager.get_badge_scoped_all_time_stats(
            assignee_id,
            [chore_a],
        )
        assert scoped.get(const.DATA_USER_CHORE_DATA_PERIOD_APPROVED) == 3
        assert scoped.get(const.DATA_USER_CHORE_DATA_PERIOD_POINTS) == 15.0

        scoped_both = coordinator.statistics_manager.get_badge_scoped_all_time_stats(
            assignee_id,
            [chore_a, chore_b],
        )
        assert scoped_both.get(const.DATA_USER_CHORE_DATA_PERIOD_APPROVED) == 10

        empty = coordinator.statistics_manager.get_badge_scoped_all_time_stats(
            assignee_id,
            [],
        )
        assert empty == {}

    async def test_source_runtime_context_scopes_all_time_to_tracked_chores(
        self,
        setup_minimal: SetupResult,
    ) -> None:
        """Runtime context overrides chore_periods_all_time with scoped data."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))
        chore_ids = list(coordinator.chores_data.keys())
        assert len(chore_ids) >= 2
        chore_a, chore_b = chore_ids[0], chore_ids[1]

        assignee_data = coordinator.assignees_data[assignee_id]
        chore_data = assignee_data.setdefault(const.DATA_USER_CHORE_DATA, {})
        for chore_id, approved in ((chore_a, 3), (chore_b, 7)):
            chore_data.setdefault(chore_id, {}).setdefault(
                const.DATA_USER_CHORE_DATA_PERIODS, {}
            )[const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME] = {
                const.PERIOD_ALL_TIME: {
                    const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: approved,
                }
            }

        context = manager._build_evaluation_context(assignee_id)
        assert context is not None

        runtime = manager._build_source_runtime_context(
            context,
            assignee_id=assignee_id,
            canonical_target={
                "target_type": const.CANONICAL_TARGET_TYPE_TOTAL_WITH_BASELINE,
                "tracked_chore_ids": [chore_a],
            },
        )
        scoped_all_time = runtime.get("chore_periods_all_time") or {}
        assert scoped_all_time.get(const.DATA_USER_CHORE_DATA_PERIOD_APPROVED) == 3

    async def test_scoped_chore_total_achievements_evaluate_independently(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Two scoped Chore Total achievements only count their own chore."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))
        chore_ids = list(coordinator.chores_data.keys())
        assert len(chore_ids) >= 2
        chore_a, chore_b = chore_ids[0], chore_ids[1]

        assignee_data = coordinator.assignees_data[assignee_id]
        chore_data = assignee_data.setdefault(const.DATA_USER_CHORE_DATA, {})
        for chore_id, approved in ((chore_a, 3), (chore_b, 7)):
            chore_data.setdefault(chore_id, {}).setdefault(
                const.DATA_USER_CHORE_DATA_PERIODS, {}
            )[const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME] = {
                const.PERIOD_ALL_TIME: {
                    const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: approved,
                }
            }

        def _make_achievement(
            ach_id: str, chore_id: str, target: int
        ) -> dict[str, Any]:
            return {
                const.DATA_ACHIEVEMENT_INTERNAL_ID: ach_id,
                const.DATA_ACHIEVEMENT_NAME: ach_id,
                const.DATA_ACHIEVEMENT_TYPE: const.ACHIEVEMENT_TYPE_TOTAL,
                const.DATA_ACHIEVEMENT_TARGET_VALUE: target,
                const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: chore_id,
                const.DATA_ACHIEVEMENT_PROGRESS: {
                    assignee_id: {
                        const.DATA_ACHIEVEMENT_AWARDED: False,
                        const.DATA_ACHIEVEMENT_BASELINE: 0,
                    }
                },
                const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS: [assignee_id],
                const.DATA_ACHIEVEMENT_REWARD_POINTS: 1.0,
                const.DATA_ACHIEVEMENT_CRITERIA: "test",
                const.DATA_ACHIEVEMENT_DESCRIPTION: "test",
                const.DATA_ACHIEVEMENT_ICON: "mdi:trophy",
                const.DATA_ACHIEVEMENT_LABELS: [],
            }

        # Achievement A targets chore A (3 approved) with threshold 5.
        # Achievement B targets chore B (7 approved) with threshold 5.
        coordinator.achievements_data["ach-a"] = _make_achievement("ach-a", chore_a, 5)
        coordinator.achievements_data["ach-b"] = _make_achievement("ach-b", chore_b, 5)

        context = manager._build_evaluation_context(assignee_id)
        assert context is not None

        manager.award_achievement = AsyncMock()
        await manager._evaluate_achievement_for_assignee(
            context,
            "ach-a",
            coordinator.achievements_data["ach-a"],
        )
        await manager._evaluate_achievement_for_assignee(
            context,
            "ach-b",
            coordinator.achievements_data["ach-b"],
        )
        await hass.async_block_till_done()

        # Only achievement B (chore B has 7 >= 5) should be awarded.
        manager.award_achievement.assert_called_once_with(assignee_id, "ach-b")

    async def test_scoped_achievement_baseline_guard_self_heals(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Global baseline exceeding scoped total does not clamp progress to 0."""
        coordinator = setup_minimal.coordinator
        manager = coordinator.gamification_manager
        assignee_id = next(iter(coordinator.assignees_data.keys()))
        chore_ids = list(coordinator.chores_data.keys())
        assert len(chore_ids) >= 1
        chore_a = chore_ids[0]

        assignee_data = coordinator.assignees_data[assignee_id]
        chore_data = assignee_data.setdefault(const.DATA_USER_CHORE_DATA, {})
        chore_data.setdefault(chore_a, {}).setdefault(
            const.DATA_USER_CHORE_DATA_PERIODS, {}
        )[const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME] = {
            const.PERIOD_ALL_TIME: {
                const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 3,
            }
        }

        achievement_id = "ach-baseline-guard"
        coordinator.achievements_data[achievement_id] = {
            const.DATA_ACHIEVEMENT_INTERNAL_ID: achievement_id,
            const.DATA_ACHIEVEMENT_NAME: "Baseline guard",
            const.DATA_ACHIEVEMENT_TYPE: const.ACHIEVEMENT_TYPE_TOTAL,
            const.DATA_ACHIEVEMENT_TARGET_VALUE: 5,
            const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: chore_a,
            const.DATA_ACHIEVEMENT_PROGRESS: {
                assignee_id: {
                    const.DATA_ACHIEVEMENT_AWARDED: False,
                    # Stale GLOBAL baseline (all chores) larger than scoped total.
                    const.DATA_ACHIEVEMENT_BASELINE: 10,
                }
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
            coordinator.achievements_data[achievement_id],
        )
        await hass.async_block_till_done()

        # Without the guard, current_value would be max(3 - 10, 0) = 0 and the
        # achievement would never award. With the guard, baseline resets to 0 so
        # current_value = 3, still below threshold 5 -> not awarded, but progress
        # is tracked (not stuck at 0).
        manager.award_achievement.assert_not_called()
        progress = coordinator.achievements_data[achievement_id][
            const.DATA_ACHIEVEMENT_PROGRESS
        ][assignee_id]
        assert progress.get(const.DATA_ACHIEVEMENT_CURRENT_VALUE) == 3
