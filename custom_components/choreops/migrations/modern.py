"""Modern storage schema migrations for post-1.0.0 releases.

This module owns versioned migrations for current-schema storage payloads.
Unlike `migrations/pre_v50.py`, these migrations target modern storage-only
installs and should evolve with future GA schema bumps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.choreops import const

if TYPE_CHECKING:
    from custom_components.choreops.coordinator import ChoreOpsDataCoordinator


async def run_modern_schema_migrations(
    coordinator: ChoreOpsDataCoordinator,
    current_version: int,
) -> dict[str, Any]:
    """Run post-1.0.0 schema migrations and return a summary.

    When future GA releases introduce durable storage contract changes, add
    ordered migration steps here. Each step must be idempotent and safe to re-run.
    """
    summary: dict[str, Any] = {
        "from_version": current_version,
        "to_version": current_version,
        "migrations_applied": [],
    }

    if current_version < const.SCHEMA_VERSION_1_5_3:
        _add_badge_streak_history(coordinator)
        summary["migrations_applied"].append("add_badge_streak_history")
        summary["to_version"] = const.SCHEMA_VERSION_1_5_3

    return summary


def _add_badge_streak_history(coordinator: ChoreOpsDataCoordinator) -> None:
    """Seed `streak_history` on every badge progress entry that lacks it.

    Introduced with the badge streak repair service, which needs the recent
    per-day streak counts to restore a broken streak.

    Only the empty container is created — no values are backfilled, because a
    history cannot be invented for days that were never recorded. The history
    therefore starts accruing from the first evaluation after upgrade.

    Idempotent: an entry that already has the key is left untouched, so re-running
    is safe.
    """
    for assignee_data in coordinator.assignees_data.values():
        badge_progress = assignee_data.get(const.DATA_USER_BADGE_PROGRESS)
        if not isinstance(badge_progress, dict):
            continue
        for progress in badge_progress.values():
            if not isinstance(progress, dict):
                continue
            progress.setdefault(const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY, {})
