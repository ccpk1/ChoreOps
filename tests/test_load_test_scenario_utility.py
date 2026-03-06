"""Tests for the live scenario loading utility helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "utils"
        / "load_test_scenario_to_live_ha.py"
    )
    spec = importlib.util.spec_from_file_location("scenario_loader", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_scenario_path_relative() -> None:
    """It resolves repo-relative scenario paths."""
    module = _load_module()
    repo_root = Path("/workspaces/choreops")

    resolved = module.resolve_scenario_path(
        "tests/scenarios/scenario_full.yaml", repo_root
    )

    assert resolved == Path("/workspaces/choreops/tests/scenarios/scenario_full.yaml")


def test_resolve_scenario_path_absolute() -> None:
    """It preserves absolute scenario paths."""
    module = _load_module()
    absolute_path = Path("/workspaces/choreops/tests/scenarios/scenario_minimal.yaml")

    resolved = module.resolve_scenario_path(
        str(absolute_path), Path("/workspaces/choreops")
    )

    assert resolved == absolute_path


def test_extract_scenario_collections_modern_shape() -> None:
    """It extracts modern scenario keys correctly."""
    module = _load_module()
    scenario = {
        "assignees": [{"name": "A"}],
        "approvers": [{"name": "P"}],
        "chores": [{"name": "C"}],
        "badges": [{"name": "G"}],
        "rewards": [{"name": "R"}],
        "bonuses": [{"name": "B"}],
        "penalties": [{"name": "N"}],
    }

    assignees, approvers, chores, badges, rewards, bonuses, penalties = (
        module.extract_scenario_collections(scenario)
    )

    assert len(assignees) == 1
    assert len(approvers) == 1
    assert len(chores) == 1
    assert len(badges) == 1
    assert len(rewards) == 1
    assert len(bonuses) == 1
    assert len(penalties) == 1


def test_extract_scenario_collections_legacy_family_shape() -> None:
    """It falls back to legacy family.kids and family.parents keys."""
    module = _load_module()
    scenario = {
        "family": {
            "kids": [{"name": "Kid 1"}],
            "parents": [{"name": "Parent 1"}],
        },
        "chores": [{"name": "Chore 1"}],
    }

    assignees, approvers, chores, badges, rewards, bonuses, penalties = (
        module.extract_scenario_collections(scenario)
    )

    assert [item["name"] for item in assignees] == ["Kid 1"]
    assert [item["name"] for item in approvers] == ["Parent 1"]
    assert [item["name"] for item in chores] == ["Chore 1"]
    assert badges == []
    assert rewards == []
    assert bonuses == []
    assert penalties == []


def test_build_chore_payload_defaults_and_custom_fields() -> None:
    """It builds expected chore payload fields with defaults and custom overrides."""
    module = _load_module()
    payload = module.build_chore_payload(
        {
            "name": "Feed Cat",
            "assigned_to": ["Zoë"],
            "recurring_frequency": "custom",
            "custom_interval": 3,
            "custom_interval_unit": "days",
        }
    )

    assert payload["name"] == "Feed Cat"
    assert payload["assigned_user_ids"] == ["Zoë"]
    assert payload["default_points"] == 10.0
    assert payload["recurring_frequency"] == "custom"
    assert payload["custom_interval"] == 3
    assert payload["custom_interval_unit"] == "days"


def test_build_bonus_and_penalty_payloads_force_positive_points() -> None:
    """It normalizes bonus and penalty points to positive form values."""
    module = _load_module()

    bonus_payload = module.build_bonus_payload({"name": "Bonus", "points": -7})
    penalty_payload = module.build_penalty_payload({"name": "Penalty", "points": -9})

    assert bonus_payload["bonus_points"] == 7.0
    assert penalty_payload["penalty_points"] == 9.0


def test_build_chore_payload_includes_due_window_fields() -> None:
    """It forwards due-window and claim-lock fields when provided."""
    module = _load_module()

    payload = module.build_chore_payload(
        {
            "name": "Window chore",
            "assigned_to": ["Zoë"],
            "chore_due_window_offset": "1h",
            "chore_claim_lock_until_window": True,
        }
    )

    assert payload["chore_due_window_offset"] == "1h"
    assert payload["chore_claim_lock_until_window"] is True


def test_build_per_assignee_details_payload() -> None:
    """It builds per-assignee applicable-day fields for helper flow."""
    module = _load_module()
    payload = module.build_per_assignee_details_payload(
        {
            "assigned_user_ids": ["Zoë", "Max"],
            "applicable_days": ["mon", "wed"],
        }
    )

    assert payload == {
        "applicable_days_Zoë": ["mon", "wed"],
        "applicable_days_Max": ["mon", "wed"],
    }


def test_extract_state_seed_actions_direct() -> None:
    """It reads top-level state_seed_actions definitions."""
    module = _load_module()
    actions = module.extract_state_seed_actions(
        {
            "state_seed_actions": [
                {"service": "claim_chore", "data": {"user_name": "Zoë"}},
                {"service": "approve_chore", "data": {"user_name": "Zoë"}},
            ]
        }
    )

    assert actions == [
        {"service": "claim_chore", "data": {"user_name": "Zoë"}},
        {"service": "approve_chore", "data": {"user_name": "Zoë"}},
    ]


def test_extract_state_seed_actions_nested() -> None:
    """It reads nested state_seed.actions definitions."""
    module = _load_module()
    actions = module.extract_state_seed_actions(
        {
            "state_seed": {
                "actions": [{"service": "redeem_reward", "data": {"reward_name": "R"}}]
            }
        }
    )

    assert actions == [{"service": "redeem_reward", "data": {"reward_name": "R"}}]


def test_extract_state_seed_actions_filters_invalid() -> None:
    """It ignores invalid state seed action records."""
    module = _load_module()
    actions = module.extract_state_seed_actions(
        {
            "state_seed_actions": [
                {"service": "claim_chore", "data": {"user_name": "Zoë"}},
                {"service": "claim_chore", "data": "not-dict"},
                {"service": "", "data": {}},
                {"data": {"user_name": "Zoë"}},
            ]
        }
    )

    assert actions == [{"service": "claim_chore", "data": {"user_name": "Zoë"}}]


def test_build_state_seed_payload_injects_config_entry_id() -> None:
    """It injects config_entry_id when scenario action omits target fields."""
    module = _load_module()
    service, payload = module.build_state_seed_payload(
        {
            "service": "claim_chore",
            "data": {"user_name": "Zoë", "chore_name": "Test"},
        },
        "entry-123",
    )

    assert service == "claim_chore"
    assert payload["config_entry_id"] == "entry-123"


def test_build_state_seed_payload_preserves_explicit_target() -> None:
    """It keeps explicit config target fields from scenario action."""
    module = _load_module()
    service, payload = module.build_state_seed_payload(
        {
            "service": "claim_chore",
            "data": {
                "config_entry_title": "Sandbox",
                "user_name": "Zoë",
                "chore_name": "Test",
            },
        },
        "entry-123",
    )

    assert service == "claim_chore"
    assert "config_entry_id" not in payload
    assert payload["config_entry_title"] == "Sandbox"


def test_resolve_due_date_value_now() -> None:
    """It resolves plain now to an ISO UTC timestamp."""
    module = _load_module()
    fixed_now = datetime(2026, 3, 3, 12, 0, 0, tzinfo=UTC)

    assert module.resolve_due_date_value("now", now_utc=fixed_now) == (
        "2026-03-03T12:00:00+00:00"
    )


def test_resolve_due_date_value_offset_units() -> None:
    """It resolves positive/negative offsets with hour/day/week units."""
    module = _load_module()
    fixed_now = datetime(2026, 3, 3, 12, 0, 0, tzinfo=UTC)

    assert module.resolve_due_date_value("now+3h", now_utc=fixed_now) == (
        "2026-03-03T15:00:00+00:00"
    )
    assert module.resolve_due_date_value("now-15m", now_utc=fixed_now) == (
        "2026-03-03T11:45:00+00:00"
    )
    assert module.resolve_due_date_value("now+7d", now_utc=fixed_now) == (
        "2026-03-10T12:00:00+00:00"
    )
    assert module.resolve_due_date_value("now+1w", now_utc=fixed_now) == (
        "2026-03-10T12:00:00+00:00"
    )


def test_resolve_due_date_value_passthrough() -> None:
    """It leaves absolute timestamps and non-strings unchanged."""
    module = _load_module()

    absolute_due_date = "2030-01-01T10:00:00+00:00"
    assert module.resolve_due_date_value(absolute_due_date) == absolute_due_date
    assert module.resolve_due_date_value(123) == 123


def test_is_duplicate_flow_result_detects_duplicate_keys() -> None:
    """It detects duplicate markers in options-flow error payloads."""
    module = _load_module()

    assert module.is_duplicate_flow_result(
        {
            "type": "form",
            "errors": {
                "name": "duplicate_chore",
            },
        }
    )


def test_is_duplicate_flow_result_ignores_non_duplicate_errors() -> None:
    """It does not classify unrelated errors as duplicate add attempts."""
    module = _load_module()

    assert not module.is_duplicate_flow_result(
        {
            "type": "form",
            "errors": {
                "base": "cannot_connect",
            },
        }
    )
