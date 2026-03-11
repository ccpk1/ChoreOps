"""Contract tests for StatisticsManager report rollup payload."""

from __future__ import annotations

from types import MethodType
from typing import Any

from custom_components.choreops import const
from custom_components.choreops.managers.statistics_manager import StatisticsManager


def test_empty_report_rollup_uses_points_spent_keys() -> None:
    """Empty rollup exposes normalized reward points_spent keys."""
    manager = StatisticsManager.__new__(StatisticsManager)

    rollup = StatisticsManager._empty_report_rollup(manager)

    rewards = rollup["rewards"]
    assert "in_range_points_spent" in rewards
    assert "all_time_points_spent" in rewards
    assert "in_range_points" not in rewards
    assert "all_time_points" not in rewards


def test_get_report_rollup_returns_normalized_reward_keys() -> None:
    """Public rollup contract returns reward points_spent keys."""
    manager = StatisticsManager.__new__(StatisticsManager)

    def _get_assignee(_self: StatisticsManager, _assignee_id: str) -> dict[str, Any]:
        return {"assignee_data": True}

    def _rollup_period_metrics(
        _self: StatisticsManager,
        _periods: dict[str, Any],
        metrics: list[str],
        _start_iso: str,
        _end_iso: str,
    ) -> dict[str, dict[str, int | float]]:
        defaults: dict[str, int | float] = dict.fromkeys(metrics, 0)
        return {"in_range": defaults, "all_time": defaults}

    def _rollup_period_collections(
        _self: StatisticsManager,
        _period_collections: list[dict[str, Any]],
        metrics: list[str],
        _start_iso: str,
        _end_iso: str,
    ) -> dict[str, dict[str, int | float]]:
        defaults: dict[str, int | float] = dict.fromkeys(metrics, 0)
        return {"in_range": defaults, "all_time": defaults}

    def _get_badge_rollup(
        _self: StatisticsManager, _assignee_info: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "earned_unique_count": 0,
            "all_time_award_count": 0,
            "earned_badge_names": [],
            "by_badge": {},
        }

    def _get_streak_rollup(
        _self: StatisticsManager,
        _assignee_info: dict[str, Any],
        _chore_periods: dict[str, Any],
    ) -> dict[str, int]:
        return {
            "current_streak": 0,
            "current_missed_streak": 0,
            "all_time_longest_streak": 0,
            "all_time_longest_missed_streak": 0,
        }

    manager._get_assignee = MethodType(_get_assignee, manager)
    manager._rollup_period_metrics = MethodType(_rollup_period_metrics, manager)
    manager._rollup_period_collections = MethodType(_rollup_period_collections, manager)
    manager._get_badge_rollup = MethodType(_get_badge_rollup, manager)
    manager._get_streak_rollup = MethodType(_get_streak_rollup, manager)

    rollup = StatisticsManager.get_report_rollup(
        manager,
        assignee_id="assignee-1",
        start_iso="2026-02-10T00:00:00+00:00",
        end_iso="2026-02-17T00:00:00+00:00",
    )

    rewards = rollup["rewards"]
    assert "in_range_points_spent" in rewards
    assert "all_time_points_spent" in rewards
    assert "in_range_points" not in rewards
    assert "all_time_points" not in rewards


def test_get_stats_rehydrates_partial_cache_entry() -> None:
    """Partial cache entries should be rebuilt before being returned."""
    manager = StatisticsManager.__new__(StatisticsManager)
    manager._stats_cache = {
        "assignee-1": {
            const.CACHE_DOMAIN_POINTS: {
                const.PRES_USER_POINTS_EARNED_TODAY: 5.0,
            }
        }
    }

    def _refresh_all_cache(_self: StatisticsManager, assignee_id: str) -> None:
        _self._stats_cache[assignee_id] = {
            const.CACHE_DOMAIN_POINTS: {
                const.PRES_USER_POINTS_EARNED_TODAY: 5.0,
            },
            const.CACHE_DOMAIN_CHORES: {
                const.PRES_USER_CHORES_APPROVED_WEEK: 4,
            },
            const.CACHE_DOMAIN_REWARDS: {
                const.PRES_USER_REWARDS_CLAIMED_TODAY: 0,
            },
            const.CACHE_DOMAIN_META: {
                const.PRES_USER_LAST_UPDATED: "2026-03-11T00:00:00+00:00",
            },
        }

    manager._refresh_all_cache = MethodType(_refresh_all_cache, manager)

    stats = StatisticsManager.get_stats(manager, "assignee-1")

    assert stats[const.PRES_USER_CHORES_APPROVED_WEEK] == 4
    assert const.PRES_USER_LAST_UPDATED in stats


def test_get_chore_stats_rehydrates_and_returns_stable_defaults() -> None:
    """Chore stats getter should always return the full chore contract."""
    manager = StatisticsManager.__new__(StatisticsManager)
    manager._stats_cache = {
        "assignee-1": {
            const.CACHE_DOMAIN_POINTS: {
                const.PRES_USER_POINTS_EARNED_TODAY: 5.0,
            }
        }
    }

    def _refresh_chore_cache(_self: StatisticsManager, assignee_id: str) -> None:
        _self._stats_cache.setdefault(assignee_id, {})[const.CACHE_DOMAIN_CHORES] = {
            const.PRES_USER_CHORES_APPROVED_WEEK: 4,
            const.PRES_USER_CHORES_CURRENT_OVERDUE: 2,
        }

    manager._refresh_chore_cache = MethodType(_refresh_chore_cache, manager)

    stats = StatisticsManager.get_chore_stats(manager, "assignee-1")

    assert stats[const.PRES_USER_CHORES_APPROVED_WEEK] == 4
    assert stats[const.PRES_USER_CHORES_CURRENT_OVERDUE] == 2
    assert stats[const.PRES_USER_CHORES_COMPLETED_TODAY] == 0
    assert stats[const.PRES_USER_TOP_CHORES_WEEK] == ""
