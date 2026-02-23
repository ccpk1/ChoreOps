"""Tests for report helper output used by generate_activity_report service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers import report_helpers


class _DummyStatisticsManager:
    """Minimal statistics manager stub for report helper tests."""

    def get_report_rollup(
        self,
        assignee_id: str,
        start_iso: str,
        end_iso: str,
    ) -> dict[str, Any]:
        _ = (assignee_id, start_iso, end_iso)
        return {
            "points": {
                "in_range_earned": 10.0,
                "in_range_spent": 3.0,
                "all_time_earned": 50.0,
                "all_time_spent": 20.0,
                "all_time_net": 30.0,
            },
            "chores": {
                "in_range_approved": 2,
                "in_range_claimed": 2,
                "in_range_disapproved": 0,
                "in_range_missed": 0,
                "in_range_overdue": 0,
                "all_time_approved": 7,
                "all_time_claimed": 9,
                "all_time_disapproved": 1,
                "all_time_missed": 2,
                "all_time_overdue": 6,
            },
            "rewards": {
                "in_range_approved": 1,
                "in_range_claimed": 1,
                "in_range_disapproved": 0,
                "in_range_points_spent": 3.0,
                "all_time_approved": 4,
                "all_time_claimed": 4,
                "all_time_disapproved": 0,
                "all_time_points_spent": 12.0,
            },
            "bonuses": {
                "in_range_applies": 1,
                "in_range_points": 1.5,
                "all_time_applies": 0,
                "all_time_points": 0.0,
            },
            "penalties": {
                "in_range_applies": 0,
                "in_range_points": 0.0,
                "all_time_applies": 0,
                "all_time_points": 0.0,
            },
            "streaks": {
                "current_streak": 4,
                "current_missed_streak": 1,
                "all_time_longest_streak": 5,
                "all_time_longest_missed_streak": 3,
            },
            "badges": {
                "earned_unique_count": 1,
                "all_time_award_count": 2,
                "earned_badge_names": ["Consistency"],
                "by_badge": {
                    "badge-1": {
                        "name": "Consistency",
                        "last_awarded": "2026-02-11",
                        "all_time_award_count": 2,
                        "periods": {
                            const.PERIOD_ALL_TIME: {
                                const.PERIOD_ALL_TIME: {
                                    const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: 2,
                                }
                            }
                        },
                    }
                },
            },
        }


class _NoBadgeStatisticsManager(_DummyStatisticsManager):
    """Statistics manager stub with empty badge rollup for fallback validation."""

    def get_report_rollup(
        self,
        assignee_id: str,
        start_iso: str,
        end_iso: str,
    ) -> dict[str, Any]:
        rollup = super().get_report_rollup(assignee_id, start_iso, end_iso)
        rollup["badges"] = {
            "earned_unique_count": 0,
            "all_time_award_count": 0,
            "earned_badge_names": [],
            "by_badge": {},
        }
        return rollup


def _build_test_assignees_data() -> dict[str, Any]:
    return {
        "assignee-1": {
            const.DATA_USER_NAME: "Zoë",
            const.DATA_ASSIGNEE_POINTS: 100.0,
            const.DATA_ASSIGNEE_DASHBOARD_LANGUAGE: "en",
            const.DATA_ASSIGNEE_LEDGER: [
                {
                    const.DATA_LEDGER_TIMESTAMP: "2026-02-10T12:00:00+00:00",
                    const.DATA_LEDGER_AMOUNT: 10.0,
                    const.DATA_LEDGER_SOURCE: const.POINTS_SOURCE_CHORES,
                    const.DATA_LEDGER_ITEM_NAME: "Dishes",
                },
                {
                    const.DATA_LEDGER_TIMESTAMP: "2026-02-11T12:00:00+00:00",
                    const.DATA_LEDGER_AMOUNT: -3.0,
                    const.DATA_LEDGER_SOURCE: const.POINTS_SOURCE_REWARDS,
                    const.DATA_LEDGER_ITEM_NAME: "Screen Time",
                },
            ],
            const.DATA_ASSIGNEE_POINT_PERIODS: {
                const.PERIOD_ALL_TIME: {
                    const.PERIOD_ALL_TIME: {
                        const.DATA_ASSIGNEE_POINT_PERIOD_POINTS_EARNED: 50.0,
                        const.DATA_ASSIGNEE_POINT_PERIOD_POINTS_SPENT: 20.0,
                    }
                }
            },
            const.DATA_ASSIGNEE_CHORE_PERIODS: {
                const.PERIOD_ALL_TIME: {
                    const.PERIOD_ALL_TIME: {
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED: 7,
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_CLAIMED: 9,
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_DISAPPROVED: 1,
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_MISSED: 2,
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_OVERDUE: 6,
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_LONGEST_STREAK: 5,
                        const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK: 3,
                    }
                }
            },
            const.DATA_ASSIGNEE_REWARD_PERIODS: {
                const.PERIOD_ALL_TIME: {
                    const.PERIOD_ALL_TIME: {
                        const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED: 4,
                        const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED: 4,
                        const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_ASSIGNEE_REWARD_DATA_PERIOD_POINTS: 12.0,
                    }
                }
            },
            const.DATA_ASSIGNEE_CHORE_DATA: {
                "chore-1": {
                    const.DATA_ASSIGNEE_CHORE_DATA_CURRENT_STREAK: 4,
                    const.DATA_ASSIGNEE_CHORE_DATA_CURRENT_MISSED_STREAK: 1,
                }
            },
            const.DATA_ASSIGNEE_BADGES_EARNED: {
                "badge-1": {
                    const.DATA_ASSIGNEE_BADGES_EARNED_NAME: "Consistency",
                    const.DATA_ASSIGNEE_BADGES_EARNED_LAST_AWARDED: "2026-02-11",
                    const.DATA_ASSIGNEE_BADGES_EARNED_PERIODS: {
                        "2026-02-11": {
                            "2026-02-11": {
                                const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: 1,
                            }
                        },
                        "2026-W07": {
                            "2026-W07": {
                                const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: 2,
                            }
                        },
                        "2026-02": {
                            "2026-02": {
                                const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: 2,
                            }
                        },
                        "2026": {
                            "2026": {
                                const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: 2,
                            }
                        },
                        const.PERIOD_ALL_TIME: {
                            const.PERIOD_ALL_TIME: {
                                const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT: 2,
                            }
                        },
                    },
                }
            },
        }
    }


def test_build_activity_report_includes_streaks_badges_and_translation() -> None:
    """Report includes new supplemental streak/badge fields and localized markdown labels."""
    range_result = report_helpers.resolve_report_range(
        mode=const.REPORT_RANGE_MODE_CUSTOM,
        start_date=datetime(2026, 2, 10, tzinfo=UTC),
        end_date=datetime(2026, 2, 12, tzinfo=UTC),
    )

    report = report_helpers.build_activity_report(
        assignees_data=_build_test_assignees_data(),
        range_result=range_result,
        assignee_id="assignee-1",
        stats_manager=_DummyStatisticsManager(),
        report_translations={
            "section_weekly_summary": "## Snapshot",
            "total_points_earned": "Earned total",
        },
    )

    assert report["supplemental"]["chores"]["all_time_missed"] == 2
    assert report["supplemental"]["chores"]["all_time_overdue"] == 6
    assert report["supplemental"]["streaks"]["current_streak"] == 4
    assert report["supplemental"]["streaks"]["current_missed_streak"] == 1
    assert report["supplemental"]["streaks"]["all_time_longest_streak"] == 5
    assert report["supplemental"]["streaks"]["all_time_longest_missed_streak"] == 3
    assert report["supplemental"]["badges"]["earned_unique_count"] == 1
    assert report["supplemental"]["badges"]["all_time_award_count"] == 2
    assert report["supplemental"]["badges"]["earned_badge_names"] == ["Consistency"]
    assert "badge-1" in report["supplemental"]["badges"]["by_badge"]
    assert (
        report["supplemental"]["badges"]["by_badge"]["badge-1"]["all_time_award_count"]
        == 2
    )
    assert (
        report["supplemental"]["badges"]["by_badge"]["badge-1"]["periods"]
        .get(const.PERIOD_ALL_TIME, {})
        .get(const.PERIOD_ALL_TIME, {})
        .get(const.DATA_ASSIGNEE_BADGES_EARNED_AWARD_COUNT)
        == 2
    )

    assert "## Snapshot" in report["markdown"]
    assert "- Earned total:" in report["markdown"]
    assert "- 🏅 Badges earned:" in report["markdown"]
    assert "  - Consistency (2026-02-11)" in report["markdown"]
    assert "- 🧾 Ledger detail:" in report["markdown"]
    assert "Range: 2026-02-10 → 2026-02-12" in report["markdown"]


def test_build_activity_report_badges_from_local_badge_records() -> None:
    """Badge highlights are sourced from local badge records for date-bucket accuracy."""
    range_result = report_helpers.resolve_report_range(
        mode=const.REPORT_RANGE_MODE_CUSTOM,
        start_date=datetime(2026, 2, 10, tzinfo=UTC),
        end_date=datetime(2026, 2, 14, tzinfo=UTC),
    )

    report = report_helpers.build_activity_report(
        assignees_data=_build_test_assignees_data(),
        range_result=range_result,
        assignee_id="assignee-1",
        stats_manager=_NoBadgeStatisticsManager(),
    )

    assert "- 🏅 Badges earned:" in report["markdown"]
    assert "  - Consistency (2026-02-11)" in report["markdown"]


def test_build_activity_report_uses_in_range_values_for_weekly_sections() -> None:
    """Weekly summary and highlights prefer in-range rollups over all-time totals."""
    range_result = report_helpers.resolve_report_range(
        mode=const.REPORT_RANGE_MODE_CUSTOM,
        start_date=datetime(2026, 2, 10, tzinfo=UTC),
        end_date=datetime(2026, 2, 12, tzinfo=UTC),
    )

    report = report_helpers.build_activity_report(
        assignees_data=_build_test_assignees_data(),
        range_result=range_result,
        assignee_id="assignee-1",
        stats_manager=_DummyStatisticsManager(),
    )

    assert "- Completed chores this week: 2" in report["markdown"]
    assert "- ✨ Bonus points: 1.5" in report["markdown"]
    assert "- 🎁 Rewards: claimed=1, spent=3.0" in report["markdown"]


def test_normalize_report_range_mode_handles_common_shapes() -> None:
    """Range mode normalization supports string/dict/list and custom inference."""
    assert (
        report_helpers.normalize_report_range_mode(const.REPORT_RANGE_MODE_LAST_30_DAYS)
        == const.REPORT_RANGE_MODE_LAST_30_DAYS
    )
    assert (
        report_helpers.normalize_report_range_mode({"value": "custom"})
        == const.REPORT_RANGE_MODE_CUSTOM
    )
    assert (
        report_helpers.normalize_report_range_mode(["last_7_days"])
        == const.REPORT_RANGE_MODE_LAST_7_DAYS
    )
    assert (
        report_helpers.normalize_report_range_mode(
            None,
            start_date="2026-01-01T00:00:00+00:00",
            end_date="2026-01-31T23:59:59+00:00",
        )
        == const.REPORT_RANGE_MODE_CUSTOM
    )


def test_resolve_report_range_last_30_days_uses_full_window() -> None:
    """Last 30 days mode computes a 30-day span from provided now."""
    now_utc = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)
    result = report_helpers.resolve_report_range(
        mode=const.REPORT_RANGE_MODE_LAST_30_DAYS,
        start_date=None,
        end_date=None,
        now_utc=now_utc,
    )

    assert result["mode"] == const.REPORT_RANGE_MODE_LAST_30_DAYS
    start_dt = datetime.fromisoformat(result["start_iso"])
    end_dt = datetime.fromisoformat(result["end_iso"])
    assert (end_dt - start_dt).days == 30


@pytest.mark.parametrize(
    ("style", "expect_assignee_header", "expect_automation_header", "expect_splitter"),
    [
        (const.REPORT_STYLE_ASSIGNEE, True, False, False),
        (const.REPORT_STYLE_AUTOMATION, False, True, False),
        (const.REPORT_STYLE_BOTH, True, True, True),
    ],
)
def test_build_activity_report_honors_report_style(
    style: str,
    expect_assignee_header: bool,
    expect_automation_header: bool,
    expect_splitter: bool,
) -> None:
    """Report markdown changes based on selected report style."""
    range_result = report_helpers.resolve_report_range(
        mode=const.REPORT_RANGE_MODE_CUSTOM,
        start_date=datetime(2026, 2, 10, tzinfo=UTC),
        end_date=datetime(2026, 2, 12, tzinfo=UTC),
    )

    report = report_helpers.build_activity_report(
        assignees_data=_build_test_assignees_data(),
        range_result=range_result,
        assignee_id="assignee-1",
        report_style=style,
        stats_manager=_DummyStatisticsManager(),
    )

    markdown = report["markdown"]
    assert ("# ChoreOps Activity Report" in markdown) is expect_automation_header
    assert ("## 📊 Weekly summary" in markdown) is expect_assignee_header
    assert ("\n\n---\n\n" in markdown) is expect_splitter
