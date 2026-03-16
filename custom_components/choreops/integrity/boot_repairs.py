"""Boot-time data integrity repairs for modern storage payloads.

These repairs are not schema migrations. They normalize impossible runtime
state that may enter storage through historic bugs, imports, or interrupted
write sequences. Repairs in this module must be:

- idempotent
- safe to run on every startup
- named by invariant, not by incident or ticket number
"""

from __future__ import annotations

from typing import Any

from custom_components.choreops import const
from custom_components.choreops.engines.chore_engine import ChoreEngine


def run_boot_repairs(data: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Run all modern boot repairs and return per-repair summaries."""
    return {
        "repair_impossible_due_state_residue": repair_impossible_due_state_residue(data)
    }


def repair_impossible_due_state_residue(data: dict[str, Any]) -> dict[str, int]:
    """Clear impossible overdue residue when no active due date exists."""
    summary = {
        "chores_sanitized": 0,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 0,
        "global_states_normalized": 0,
    }

    chores_raw = data.get(const.DATA_CHORES)
    users_raw = data.get(const.DATA_USERS)
    if not isinstance(chores_raw, dict) or not isinstance(users_raw, dict):
        return summary

    for chore_id, chore_value in chores_raw.items():
        if not isinstance(chore_value, dict):
            continue

        chore_data: dict[str, Any] = chore_value
        chore_changed = False
        uses_chore_level_due_date = ChoreEngine.uses_chore_level_due_date(chore_data)
        due_date_raw = chore_data.get(const.DATA_CHORE_DUE_DATE)
        per_assignee_due_dates_raw = chore_data.get(
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )
        per_assignee_due_dates = (
            per_assignee_due_dates_raw
            if isinstance(per_assignee_due_dates_raw, dict)
            else {}
        )

        if not due_date_raw and uses_chore_level_due_date and per_assignee_due_dates:
            cleared_count = sum(
                1 for due_date in per_assignee_due_dates.values() if due_date
            )
            if cleared_count > 0:
                for assignee_id in list(per_assignee_due_dates):
                    per_assignee_due_dates[assignee_id] = None
                summary["stale_due_dates_cleared"] += cleared_count
                chore_changed = True

        has_active_due_date = (
            bool(due_date_raw)
            if uses_chore_level_due_date
            else any(
                due_date for due_date in per_assignee_due_dates.values() if due_date
            )
        )
        if has_active_due_date:
            if chore_changed:
                summary["chores_sanitized"] += 1
            continue

        assignee_ids_raw = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        assignee_ids = assignee_ids_raw if isinstance(assignee_ids_raw, list) else []
        assignee_states: dict[str, str] = {}

        for assignee_id in assignee_ids:
            user_value = users_raw.get(assignee_id, {})
            if not isinstance(user_value, dict):
                assignee_states[assignee_id] = const.CHORE_STATE_PENDING
                continue

            chore_tracking_raw = user_value.get(const.DATA_USER_CHORE_DATA, {})
            chore_tracking = (
                chore_tracking_raw if isinstance(chore_tracking_raw, dict) else {}
            )
            assignee_chore_value = chore_tracking.get(chore_id, {})
            assignee_chore_data = (
                assignee_chore_value if isinstance(assignee_chore_value, dict) else {}
            )

            current_state = assignee_chore_data.get(
                const.DATA_USER_CHORE_DATA_STATE,
                const.CHORE_STATE_PENDING,
            )
            if current_state in (
                const.CHORE_STATE_OVERDUE,
                const.CHORE_STATE_MISSED,
            ):
                assignee_chore_data[const.DATA_USER_CHORE_DATA_STATE] = (
                    const.CHORE_STATE_PENDING
                )
                current_state = const.CHORE_STATE_PENDING
                summary["assignee_states_normalized"] += 1
                chore_changed = True

            assignee_states[assignee_id] = (
                current_state
                if isinstance(current_state, str)
                else const.CHORE_STATE_PENDING
            )

        current_global_state = chore_data.get(const.DATA_CHORE_STATE)
        if current_global_state in (
            const.CHORE_STATE_OVERDUE,
            const.CHORE_STATE_MISSED,
        ):
            normalized_global_state = (
                ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
                if assignee_states
                else const.CHORE_STATE_PENDING
            )
            if current_global_state != normalized_global_state:
                chore_data[const.DATA_CHORE_STATE] = normalized_global_state
                summary["global_states_normalized"] += 1
                chore_changed = True

        if chore_changed:
            summary["chores_sanitized"] += 1

    return summary
