"""Contract tests for StatisticsManager report rollup payload."""

from __future__ import annotations

from types import MethodType, SimpleNamespace
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


def test_periodic_update_refreshes_time_sensitive_chore_cache() -> None:
    """Periodic updates should refresh current chore snapshot stats."""
    manager = StatisticsManager.__new__(StatisticsManager)
    manager._coordinator = SimpleNamespace(
        assignees_data={
            "assignee-1": {"name": "Alice"},
            "assignee-2": {"name": "Bob"},
        }
    )
    manager._stats_cache = {
        "assignee-1": {
            const.CACHE_DOMAIN_CHORES: {
                const.PRES_USER_CHORES_CURRENT_DUE_TODAY: 0,
            }
        }
    }

    refreshed_assignees: list[str] = []
    marked_assignees: list[str] = []

    def _refresh_chore_cache(_self: StatisticsManager, assignee_id: str) -> None:
        refreshed_assignees.append(assignee_id)
        _self._stats_cache.setdefault(assignee_id, {})[const.CACHE_DOMAIN_CHORES] = {
            const.PRES_USER_CHORES_CURRENT_DUE_TODAY: 1,
        }

    def _mark_cache_updated(_self: StatisticsManager, assignee_id: str) -> None:
        marked_assignees.append(assignee_id)

    manager._refresh_chore_cache = MethodType(_refresh_chore_cache, manager)
    manager._mark_cache_updated = MethodType(_mark_cache_updated, manager)

    StatisticsManager._on_periodic_update(manager, {})

    assert refreshed_assignees == ["assignee-1", "assignee-2"]
    assert marked_assignees == ["assignee-1", "assignee-2"]
    assert (
        StatisticsManager.get_chore_stats(manager, "assignee-1")[
            const.PRES_USER_CHORES_CURRENT_DUE_TODAY
        ]
        == 1
    )


def test_refresh_chore_cache_uses_derived_status_context_for_current_snapshots() -> (
    None
):
    """Current chore snapshot stats should follow derived assignee-facing state."""
    manager = StatisticsManager.__new__(StatisticsManager)
    assignee_id = "assignee-1"
    due_today = "2026-03-12T18:00:00+00:00"
    due_tomorrow = "2026-03-13T18:00:00+00:00"

    contexts = {
        "stale-overdue": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_COMPLETED_BY_OTHER,
            const.CHORE_CTX_DUE_DATE: due_today,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_BLOCKED_COMPLETED_BY_OTHER,
        },
        "rotation-blocked": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_NOT_MY_TURN,
            const.CHORE_CTX_DUE_DATE: due_today,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_BLOCKED_NOT_MY_TURN,
        },
        "open-due-today": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_PENDING,
            const.CHORE_CTX_DUE_DATE: due_today,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_CLAIMABLE,
        },
        "claimed-due-today": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_CLAIMED,
            const.CHORE_CTX_DUE_DATE: due_today,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_CLAIMABLE,
        },
        "waiting-due-today": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_WAITING,
            const.CHORE_CTX_DUE_DATE: due_today,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_BLOCKED_WAITING_WINDOW,
        },
        "due-state-future-date": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_DUE,
            const.CHORE_CTX_DUE_DATE: due_tomorrow,
            const.CHORE_CTX_IS_DUE: True,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_CLAIMABLE,
        },
        "pending-no-due-date": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_PENDING,
            const.CHORE_CTX_DUE_DATE: None,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_CLAIMABLE,
        },
        "pending-blocked-claim": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_PENDING,
            const.CHORE_CTX_DUE_DATE: due_today,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_BLOCKED_PENDING_CLAIM,
        },
        "completed-due-today": {
            const.CHORE_CTX_STATE: const.CHORE_STATE_COMPLETED,
            const.CHORE_CTX_DUE_DATE: due_today,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_BLOCKED_ALREADY_APPROVED,
        },
    }

    manager._coordinator = SimpleNamespace(
        assignees_data={
            assignee_id: {
                const.DATA_USER_CHORE_DATA: {
                    "stale-overdue": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_OVERDUE,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "rotation-blocked": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "open-due-today": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "claimed-due-today": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "waiting-due-today": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "due-state-future-date": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "pending-no-due-date": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "pending-blocked-claim": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                    "completed-due-today": {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_APPROVED,
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                }
            }
        },
        chores_data={},
        chore_manager=SimpleNamespace(
            get_chore_status_context=lambda current_assignee_id, chore_id: contexts[
                chore_id
            ],
            chore_counts_toward_due_today_summary=(
                lambda current_assignee_id, chore_id, **kwargs: {
                    "stale-overdue": False,
                    "rotation-blocked": False,
                    "open-due-today": True,
                    "claimed-due-today": False,
                    "waiting-due-today": True,
                    "due-state-future-date": True,
                    "pending-no-due-date": False,
                    "pending-blocked-claim": False,
                    "completed-due-today": False,
                }[chore_id]
            ),
        ),
    )
    manager.coordinator = manager._coordinator
    manager._stats_cache = {}

    def _get_assignee(
        _self: StatisticsManager, current_assignee_id: str
    ) -> dict[str, Any]:
        return _self._coordinator.assignees_data[current_assignee_id]

    def _get_domain_cache(
        _self: StatisticsManager, current_assignee_id: str, domain: str
    ) -> dict[str, Any]:
        entry = _self._stats_cache.setdefault(current_assignee_id, {})
        return entry.setdefault(domain, {})

    manager._get_assignee = MethodType(_get_assignee, manager)
    manager._get_domain_cache = MethodType(_get_domain_cache, manager)

    StatisticsManager._refresh_chore_cache(manager, assignee_id)

    stats = manager._stats_cache[assignee_id][const.CACHE_DOMAIN_CHORES]
    assert stats[const.PRES_USER_CHORES_CURRENT_OVERDUE] == 0
    assert stats[const.PRES_USER_CHORES_CURRENT_CLAIMED] == 1
    assert stats[const.PRES_USER_CHORES_CURRENT_APPROVED] == 1
    assert stats[const.PRES_USER_CHORES_CURRENT_DUE_TODAY] == 3
