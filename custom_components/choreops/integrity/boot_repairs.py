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

from homeassistant.util import dt as dt_util

from custom_components.choreops import const
from custom_components.choreops.engines.chore_engine import ChoreEngine
from custom_components.choreops.utils.dt_utils import dt_parse, dt_to_utc


def run_boot_repairs(data: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Run all modern boot repairs and return per-repair summaries."""
    return {
        "repair_impossible_due_state_residue": repair_impossible_due_state_residue(data)
    }


def _is_due_date_future(due_date_raw: Any) -> bool:
    """Return True if a due date value exists and is strictly in the future."""
    if not due_date_raw:
        return False
    due_dt = dt_to_utc(due_date_raw) or dt_parse(due_date_raw)
    if due_dt is None:
        return False
    return due_dt > dt_util.utcnow()


def repair_impossible_due_state_residue(data: dict[str, Any]) -> dict[str, int]:
    """Clear impossible overdue residue when the due date is absent or in the future.

    Invariant: a per-assignee state of `overdue`/`missed` is only legitimate when
    the chore's due date is in the past. If the due date is absent or in the future,
    those states are impossible residue (e.g. left over from a prior cycle after the
    due date was rescheduled forward) and are normalized to `pending`.

    Issue #248: the prior guard only normalized residue when there was NO active due
    date, skipping chores WITH a future due date — exactly the reported bug scenario.
    """
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
        # Resolve the applicable due date for past/future determination.
        applicable_due_date_raw = (
            due_date_raw
            if uses_chore_level_due_date
            else next(
                (due_date for due_date in per_assignee_due_dates.values() if due_date),
                None,
            )
        )
        # Skip normalization only when a due date exists AND is in the PAST
        # (where overdue/missed is legitimate). Absent or future due dates mean
        # overdue/missed is impossible residue and must be normalized.
        due_date_is_past = has_active_due_date and not _is_due_date_future(
            applicable_due_date_raw
        )
        if due_date_is_past:
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
                assignee_chore_data.pop(
                    const.DATA_USER_CHORE_DATA_OVERDUE_STARTED_AT,
                    None,
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
