"""Tests for user profile feature-gating helper behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from custom_components.choreops import const
from custom_components.choreops.helpers import entity_helpers as eh


@dataclass
class _DummyCoordinator:
    """Minimal coordinator stub for helper tests."""

    users_data: dict[str, dict[str, Any]]
    approvers_data: dict[str, dict[str, Any]]


def test_feature_gated_user_respects_workflow_and_gamification_flags() -> None:
    """Feature-gated users should follow explicit workflow/gamification flags."""
    user_id = "user-1"
    coordinator = _DummyCoordinator(
        users_data={
            user_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: True,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
        approvers_data={
            user_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: True,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
    )

    assert eh.is_user_feature_gated_profile(coordinator, user_id)
    assert eh.is_user_assignment_participant(coordinator, user_id)
    assert not eh.should_create_workflow_buttons(coordinator, user_id)
    assert not eh.should_create_gamification_entities(coordinator, user_id)


def test_non_assignable_user_is_not_assignment_participant() -> None:
    """Users with assignment disabled should not be assignment participants."""
    user_id = "user-2"
    coordinator = _DummyCoordinator(
        users_data={
            user_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: False,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
        approvers_data={
            user_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: False,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
    )

    assert not eh.is_user_assignment_participant(coordinator, user_id)
    assert not eh.should_create_workflow_buttons(coordinator, user_id)
    assert not eh.should_create_gamification_entities(coordinator, user_id)
