"""Tests for boot-time integrity repairs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.integrity import repair_impossible_due_state_residue

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _build_integrity_test_coordinator(data: dict[str, Any]) -> SimpleNamespace:
    """Build a minimal coordinator stub for integrity repair tests."""
    return SimpleNamespace(
        _data=data,
        config_entry=SimpleNamespace(
            entry_id="entry-1",
            options={const.CONF_SHOW_LEGACY_ENTITIES: False},
        ),
    )


@pytest.mark.asyncio
async def test_sanitizes_impossible_overdue_residue_without_due_date(
    hass: HomeAssistant,
) -> None:
    """Boot integrity clears stale overdue residue when no due date exists."""
    chore_id = "chore-1"
    assignee_id = "user-1"
    coordinator = _build_integrity_test_coordinator(
        {
            const.DATA_USERS: {
                assignee_id: {
                    const.DATA_USER_CHORE_DATA: {
                        chore_id: {
                            const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_OVERDUE,
                        }
                    }
                }
            },
            const.DATA_CHORES: {
                chore_id: {
                    const.DATA_CHORE_INTERNAL_ID: chore_id,
                    const.DATA_CHORE_ASSIGNED_USER_IDS: [assignee_id],
                    const.DATA_CHORE_COMPLETION_CRITERIA: (
                        const.COMPLETION_CRITERIA_SHARED_FIRST
                    ),
                    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_NONE,
                    const.DATA_CHORE_DUE_DATE: None,
                    const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: {
                        assignee_id: "2026-01-15T08:00:00+00:00"
                    },
                    const.DATA_CHORE_STATE: const.CHORE_STATE_OVERDUE,
                }
            },
        }
    )

    summary = repair_impossible_due_state_residue(coordinator._data)

    chore_data = coordinator._data[const.DATA_CHORES][chore_id]
    assignee_chore_data = coordinator._data[const.DATA_USERS][assignee_id][
        const.DATA_USER_CHORE_DATA
    ][chore_id]

    assert summary == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 1,
        "assignee_states_normalized": 1,
        "global_states_normalized": 1,
    }
    assert chore_data[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES][assignee_id] is None
    assert chore_data[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING
    assert (
        assignee_chore_data[const.DATA_USER_CHORE_DATA_STATE]
        == const.CHORE_STATE_PENDING
    )


@pytest.mark.asyncio
async def test_preserves_claimed_state_without_due_date(
    hass: HomeAssistant,
) -> None:
    """Boot integrity keeps valid claimed state while fixing impossible global overdue."""
    chore_id = "chore-1"
    assignee_id = "user-1"
    coordinator = _build_integrity_test_coordinator(
        {
            const.DATA_USERS: {
                assignee_id: {
                    const.DATA_USER_CHORE_DATA: {
                        chore_id: {
                            const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
                        }
                    }
                }
            },
            const.DATA_CHORES: {
                chore_id: {
                    const.DATA_CHORE_INTERNAL_ID: chore_id,
                    const.DATA_CHORE_ASSIGNED_USER_IDS: [assignee_id],
                    const.DATA_CHORE_COMPLETION_CRITERIA: (
                        const.COMPLETION_CRITERIA_SHARED_FIRST
                    ),
                    const.DATA_CHORE_DUE_DATE: None,
                    const.DATA_CHORE_STATE: const.CHORE_STATE_OVERDUE,
                }
            },
        }
    )

    summary = repair_impossible_due_state_residue(coordinator._data)

    chore_data = coordinator._data[const.DATA_CHORES][chore_id]
    assignee_chore_data = coordinator._data[const.DATA_USERS][assignee_id][
        const.DATA_USER_CHORE_DATA
    ][chore_id]

    assert summary == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 0,
        "global_states_normalized": 1,
    }
    assert chore_data[const.DATA_CHORE_STATE] == const.CHORE_STATE_CLAIMED
    assert (
        assignee_chore_data[const.DATA_USER_CHORE_DATA_STATE]
        == const.CHORE_STATE_CLAIMED
    )
