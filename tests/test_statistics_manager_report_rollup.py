"""Contract tests for StatisticsManager report rollup payload."""

from __future__ import annotations

from types import MethodType
from typing import Any

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

    def _get_kid(_self: StatisticsManager, _kid_id: str) -> dict[str, Any]:
        return {"kid_data": True}

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
        _self: StatisticsManager, _kid_info: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "earned_unique_count": 0,
            "all_time_award_count": 0,
            "earned_badge_names": [],
            "by_badge": {},
        }

    def _get_streak_rollup(
        _self: StatisticsManager,
        _kid_info: dict[str, Any],
        _chore_periods: dict[str, Any],
    ) -> dict[str, int]:
        return {
            "current_streak": 0,
            "current_missed_streak": 0,
            "all_time_longest_streak": 0,
            "all_time_longest_missed_streak": 0,
        }

    manager._get_kid = MethodType(_get_kid, manager)
    manager._rollup_period_metrics = MethodType(_rollup_period_metrics, manager)
    manager._rollup_period_collections = MethodType(_rollup_period_collections, manager)
    manager._get_badge_rollup = MethodType(_get_badge_rollup, manager)
    manager._get_streak_rollup = MethodType(_get_streak_rollup, manager)

    rollup = StatisticsManager.get_report_rollup(
        manager,
        kid_id="kid-1",
        start_iso="2026-02-10T00:00:00+00:00",
        end_iso="2026-02-17T00:00:00+00:00",
    )

    rewards = rollup["rewards"]
    assert "in_range_points_spent" in rewards
    assert "all_time_points_spent" in rewards
    assert "in_range_points" not in rewards
    assert "all_time_points" not in rewards
