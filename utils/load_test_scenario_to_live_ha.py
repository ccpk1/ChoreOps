#!/usr/bin/env python3
"""Development utility for loading scenario data into a live ChoreOps instance.

This script is intentionally manual and is not part of automated CI paths.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import getpass
import os
from pathlib import Path
import re
from typing import Any

import aiohttp
import yaml

DEFAULT_HA_URL = "http://localhost:8123"
DEFAULT_SCENARIO_PATH = "tests/scenarios/scenario_full.yaml"
DEFAULT_TOKEN_ENV = "HASS_TOKEN"
DEFAULT_DELAY_SECONDS = 0.3

DOMAIN = "choreops"
MENU_SELECTION = "menu_selection"
MANAGE_ACTION = "manage_action"
MANAGE_ACTION_ADD = "add"

MENU_MANAGE_USER = "manage_user"
MENU_MANAGE_CHORE = "manage_chore"
MENU_MANAGE_BADGE = "manage_badge"
MENU_MANAGE_REWARD = "manage_reward"
MENU_MANAGE_BONUS = "manage_bonus"
MENU_MANAGE_PENALTY = "manage_penalty"

STEP_INIT = "init"
STEP_EDIT_CHORE_PER_USER_DETAILS = "edit_chore_per_user_details"
STEP_CHORES_DAILY_MULTI = "chores_daily_multi"

SERVICE_FIELD_CONFIG_ENTRY_ID = "config_entry_id"

ENTITY_ADD_STATUS_ADDED = "added"
ENTITY_ADD_STATUS_SKIPPED = "skipped"
ENTITY_ADD_STATUS_FAILED = "failed"

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_NOW_DUE_DATE_RE = re.compile(r"^now\s*([+-])\s*(\d+)\s*([smhdw])$", re.IGNORECASE)


def _collect_string_values(value: Any) -> list[str]:
    """Collect all string values recursively from nested structures."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for nested_value in value.values():
            values.extend(_collect_string_values(nested_value))
        return values
    if isinstance(value, list):
        values: list[str] = []
        for nested_value in value:
            values.extend(_collect_string_values(nested_value))
        return values
    return []


def is_duplicate_flow_result(flow_result: dict[str, Any]) -> bool:
    """Return True when a flow result contains duplicate-name style validation."""
    return any(
        "duplicate" in text_value.lower()
        for text_value in _collect_string_values(flow_result)
    )


def resolve_scenario_path(raw_path: str, repo_root: Path) -> Path:
    """Resolve a scenario path from CLI input or default value."""
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def resolve_due_date_value(
    raw_due_date: Any,
    now_utc: datetime | None = None,
) -> Any:
    """Resolve due-date value, supporting `now`-relative shorthand strings.

    Supported forms:
    - `now`
    - `now+15m`, `now-2h`, `now+7d`, `now+1w`, `now+30s`
    """
    if not isinstance(raw_due_date, str):
        return raw_due_date

    normalized = raw_due_date.strip().lower()
    base_now = (now_utc or datetime.now(UTC)).replace(microsecond=0)

    if normalized == "now":
        return base_now.isoformat()

    match = _NOW_DUE_DATE_RE.match(normalized)
    if match is None:
        return raw_due_date

    sign, amount_str, unit = match.groups()
    amount = int(amount_str)
    unit_multipliers = {
        "s": timedelta(seconds=amount),
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
        "w": timedelta(weeks=amount),
    }
    delta = unit_multipliers[unit.lower()]
    resolved = base_now + delta if sign == "+" else base_now - delta
    return resolved.isoformat()


def load_scenario_file(scenario_path: Path) -> dict[str, Any]:
    """Load and parse a YAML scenario file."""
    with scenario_path.open(encoding="utf-8") as scenario_file:
        data = yaml.safe_load(scenario_file)
    if not isinstance(data, dict):
        raise ValueError("Scenario root must be a dictionary")
    return data


def extract_scenario_collections(
    scenario: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Return assignees, approvers, chores, badges, rewards, bonuses, and penalties.

    Supports both modern (`assignees` / `approvers`) and legacy (`family` keys).
    """

    def _as_list(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    assignees = _as_list(scenario.get("assignees"))
    approvers = _as_list(scenario.get("approvers"))

    family = scenario.get("family")
    if isinstance(family, dict):
        if not assignees:
            assignees = _as_list(family.get("kids"))
        if not approvers:
            approvers = _as_list(family.get("parents"))

    chores = _as_list(scenario.get("chores"))
    badges = _as_list(scenario.get("badges"))
    rewards = _as_list(scenario.get("rewards"))
    bonuses = _as_list(scenario.get("bonuses"))
    penalties = _as_list(scenario.get("penalties"))
    return assignees, approvers, chores, badges, rewards, bonuses, penalties


def extract_state_seed_actions(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract optional post-load state seed actions from scenario data.

    Supported shapes:
    - `state_seed_actions: [{service: str, data: dict}, ...]`
    - `state_seed: {actions: [{service: str, data: dict}, ...]}`
    """

    def _normalize(raw_actions: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_actions, list):
            return []

        normalized: list[dict[str, Any]] = []
        for action in raw_actions:
            if not isinstance(action, dict):
                continue
            service = action.get("service")
            data = action.get("data")
            if isinstance(service, str) and service and isinstance(data, dict):
                normalized.append({"service": service, "data": dict(data)})
        return normalized

    direct = _normalize(scenario.get("state_seed_actions"))
    if direct:
        return direct

    state_seed = scenario.get("state_seed")
    if isinstance(state_seed, dict):
        return _normalize(state_seed.get("actions"))

    return []


def build_assignee_payload(assignee: dict[str, Any]) -> dict[str, Any]:
    """Build options-flow payload for an assignee user profile."""
    return {
        "name": assignee["name"],
        "dashboard_language": assignee.get("dashboard_language", "en"),
        "mobile_notify_service": assignee.get("mobile_notify_service", ""),
        "can_be_assigned": True,
        "enable_chore_workflow": bool(assignee.get("enable_chore_workflow", True)),
        "enable_gamification": bool(assignee.get("enable_gamification", True)),
        "can_approve": False,
        "can_manage": False,
        "associated_user_ids": [],
    }


def build_approver_payload(approver: dict[str, Any]) -> dict[str, Any]:
    """Build options-flow payload for an approver profile.

    This utility creates approvers as assignment-enabled users to avoid requiring
    runtime internal IDs for associated-user mappings.
    """
    return {
        "name": approver["name"],
        "dashboard_language": approver.get("dashboard_language", "en"),
        "mobile_notify_service": approver.get("mobile_notify_service", ""),
        "can_be_assigned": True,
        "enable_chore_workflow": bool(approver.get("enable_chore_workflow", False)),
        "enable_gamification": bool(approver.get("enable_gamification", False)),
        "can_approve": False,
        "can_manage": False,
        "associated_user_ids": [],
    }


def build_chore_payload(chore: dict[str, Any]) -> dict[str, Any]:
    """Build options-flow payload for a chore item."""
    payload: dict[str, Any] = {
        "name": chore["name"],
        "chore_description": chore.get("description", ""),
        "icon": chore.get("icon", "mdi:check"),
        "default_points": float(chore.get("points", 10.0)),
        "assigned_user_ids": list(chore.get("assigned_to", [])),
        "completion_criteria": chore.get("completion_criteria", "independent"),
        "recurring_frequency": chore.get("recurring_frequency", "daily"),
        "auto_approve": bool(chore.get("auto_approve", False)),
        "show_on_calendar": bool(chore.get("show_on_calendar", True)),
        "chore_labels": list(chore.get("labels", [])),
        "applicable_days": list(chore.get("applicable_days", WEEKDAY_KEYS)),
        "chore_notifications": list(chore.get("notifications", [])),
    }
    if "due_date" in chore:
        payload["due_date"] = resolve_due_date_value(chore["due_date"])
    if "custom_interval" in chore:
        payload["custom_interval"] = chore["custom_interval"]
    if "custom_interval_unit" in chore:
        payload["custom_interval_unit"] = chore["custom_interval_unit"]
    if "approval_reset_type" in chore:
        payload["approval_reset_type"] = chore["approval_reset_type"]
    if "approval_reset_pending_claim_action" in chore:
        payload["approval_reset_pending_claim_action"] = chore[
            "approval_reset_pending_claim_action"
        ]
    if "overdue_handling_type" in chore:
        payload["overdue_handling_type"] = chore["overdue_handling_type"]
    if "chore_due_window_offset" in chore:
        payload["chore_due_window_offset"] = chore["chore_due_window_offset"]
    if "chore_claim_lock_until_window" in chore:
        payload["chore_claim_lock_until_window"] = bool(
            chore["chore_claim_lock_until_window"]
        )
    return payload


def build_reward_payload(reward: dict[str, Any]) -> dict[str, Any]:
    """Build options-flow payload for a reward item."""
    return {
        "name": reward["name"],
        "description": reward.get("description", ""),
        "reward_labels": list(reward.get("labels", [])),
        "cost": float(reward.get("cost", 50.0)),
        "icon": reward.get("icon", "mdi:gift"),
    }


def build_badge_payload(badge: dict[str, Any]) -> dict[str, Any]:
    """Build options-flow payload for a badge item.

    This payload is submitted after badge type selection in the options flow.
    """
    award_items: list[str] = []
    award_points = float(badge.get("award_points", 0.0))
    if award_points > 0:
        award_items.append("points")

    points_multiplier_raw = badge.get("points_multiplier")
    points_multiplier: float | None = None
    if points_multiplier_raw is not None:
        points_multiplier = float(points_multiplier_raw)
        if points_multiplier > 0:
            award_items.append("multiplier")

    threshold_value = badge.get(
        "threshold_value", badge.get("target_threshold_value", 10)
    )

    return {
        "badge_name": badge["name"],
        "icon": badge.get("icon", "mdi:medal"),
        "assigned_user_ids": list(badge.get("assigned_to", [])),
        "award_items": award_items,
        "award_points": award_points,
        "points_multiplier": points_multiplier,
        "threshold_value": threshold_value,
        "maintenance_rules": badge.get("maintenance_rules", 0),
    }


def build_bonus_payload(bonus: dict[str, Any]) -> dict[str, Any]:
    """Build options-flow payload for a bonus item."""
    return {
        "name": bonus["name"],
        "bonus_description": bonus.get("description", ""),
        "bonus_labels": list(bonus.get("labels", [])),
        "bonus_points": float(abs(bonus.get("points", 10.0))),
        "icon": bonus.get("icon", "mdi:sparkles"),
    }


def build_penalty_payload(penalty: dict[str, Any]) -> dict[str, Any]:
    """Build options-flow payload for a penalty item."""
    return {
        "name": penalty["name"],
        "penalty_description": penalty.get("description", ""),
        "penalty_labels": list(penalty.get("labels", [])),
        "penalty_points": float(abs(penalty.get("points", 5.0))),
        "icon": penalty.get("icon", "mdi:alert"),
    }


def build_per_assignee_details_payload(chore_payload: dict[str, Any]) -> dict[str, Any]:
    """Build helper payload for per-assignee independent chore details."""
    assigned_user_names = chore_payload.get("assigned_user_ids", [])
    applicable_days = chore_payload.get("applicable_days", WEEKDAY_KEYS)
    if not isinstance(assigned_user_names, list):
        return {}

    helper_payload: dict[str, Any] = {}
    for assignee_name in assigned_user_names:
        if isinstance(assignee_name, str) and assignee_name:
            helper_payload[f"applicable_days_{assignee_name}"] = applicable_days
    return helper_payload


def get_token(args: argparse.Namespace) -> str:
    """Resolve token from CLI flag, environment variable, or interactive prompt."""
    if args.token:
        return args.token.strip()

    token_from_env = os.getenv(args.token_env, "").strip()
    if token_from_env:
        return token_from_env

    print("\n🔑 Long-lived access token required")  # noqa: T201
    print(f"   Create one at: {args.ha_url}/profile/security")  # noqa: T201
    return getpass.getpass("Token: ").strip()


async def _request_json(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    json_payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Run an HTTP request and return `(status_code, json_body)`.

    Raises `RuntimeError` on malformed JSON responses.
    """
    request_method = session.get if method == "GET" else session.post
    async with request_method(url, json=json_payload) as response:
        status = response.status
        try:
            payload = await response.json()
        except aiohttp.ContentTypeError as err:
            text = await response.text()
            raise RuntimeError(f"Non-JSON response from {url}: {text[:400]}") from err
    return status, payload if isinstance(payload, dict) else {"raw": payload}


async def find_choreops_entry_id(session: aiohttp.ClientSession, ha_url: str) -> str:
    """Find the first loaded ChoreOps config entry and return entry_id."""
    status, payload = await _request_json(
        session,
        "GET",
        f"{ha_url}/api/config/config_entries/entry",
    )
    if status != 200:
        raise RuntimeError(f"Could not fetch config entries (status={status})")

    entries = payload.get("raw") if "raw" in payload else payload
    if not isinstance(entries, list):
        raise RuntimeError("Unexpected config entry response shape")

    for entry in entries:
        if isinstance(entry, dict) and entry.get("domain") == DOMAIN:
            entry_id = entry.get("entry_id")
            if isinstance(entry_id, str) and entry_id:
                return entry_id

    raise RuntimeError(
        "ChoreOps integration not found. Add it via Settings → Integrations first"
    )


async def reset_transactional_data(
    session: aiohttp.ClientSession,
    ha_url: str,
    entry_id: str,
) -> None:
    """Call the transactional reset service before loading entities."""
    async with session.post(
        f"{ha_url}/api/services/{DOMAIN}/reset_transactional_data",
        json={
            "confirm_destructive": True,
            "scope": "global",
            SERVICE_FIELD_CONFIG_ENTRY_ID: entry_id,
        },
    ) as response:
        if response.status != 200:
            response_text = await response.text()
            raise RuntimeError(
                f"Reset failed (status={response.status}): {response_text[:300]}"
            )


async def add_entity_via_options_flow(
    session: aiohttp.ClientSession,
    ha_url: str,
    entry_id: str,
    menu_selection: str,
    entity_name: str,
    payload: dict[str, Any],
) -> str:
    """Add one entity through options flow and return status string."""
    status, flow_start = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow",
        {"handler": entry_id},
    )
    if status != 200:
        print(f"   ❌ Failed to start options flow for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    flow_id = flow_start.get("flow_id")
    if not isinstance(flow_id, str):
        print(f"   ❌ Flow did not return flow_id for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    status, _ = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
        {MENU_SELECTION: menu_selection},
    )
    if status != 200:
        print(f"   ❌ Menu selection failed for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    status, _ = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
        {MANAGE_ACTION: MANAGE_ACTION_ADD},
    )
    if status != 200:
        print(f"   ❌ Add action selection failed for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    status, flow_result = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
        payload,
    )
    if status != 200:
        print(  # noqa: T201
            f"   ❌ Submit failed for {entity_name}: "
            f"status={status}, response={flow_result}"
        )
        return ENTITY_ADD_STATUS_FAILED

    step_id = flow_result.get("step_id")
    if step_id == STEP_INIT and flow_result.get("type") == "form":
        return ENTITY_ADD_STATUS_ADDED

    if step_id == STEP_EDIT_CHORE_PER_USER_DETAILS:
        helper_payload = build_per_assignee_details_payload(payload)
        status, flow_result = await _request_json(
            session,
            "POST",
            f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
            helper_payload,
        )
        if status != 200:
            print(f"   ❌ Per-assignee helper failed for {entity_name}")  # noqa: T201
            return ENTITY_ADD_STATUS_FAILED
        step_id = flow_result.get("step_id")

    if step_id == STEP_CHORES_DAILY_MULTI:
        times_value = str(payload.get("daily_multi_times", "08:00|17:00"))
        status, flow_result = await _request_json(
            session,
            "POST",
            f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
            {"daily_multi_times": times_value},
        )
        if status != 200:
            print(f"   ❌ Daily multi helper failed for {entity_name}")  # noqa: T201
            return ENTITY_ADD_STATUS_FAILED

    if flow_result.get("type") == "form" and flow_result.get("step_id") == STEP_INIT:
        return ENTITY_ADD_STATUS_ADDED

    if is_duplicate_flow_result(flow_result):
        return ENTITY_ADD_STATUS_SKIPPED

    error_details = flow_result.get("errors")
    if error_details is not None:
        print(  # noqa: T201
            f"   ℹ️ Flow validation errors for {entity_name}: {error_details}"
        )
    else:
        print(  # noqa: T201
            f"   ℹ️ Unexpected flow response for {entity_name}: {flow_result}"
        )

    return ENTITY_ADD_STATUS_FAILED


async def add_badge_via_options_flow(
    session: aiohttp.ClientSession,
    ha_url: str,
    entry_id: str,
    entity_name: str,
    payload: dict[str, Any],
    badge_type: str,
) -> str:
    """Add one badge through options flow and return status string."""
    status, flow_start = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow",
        {"handler": entry_id},
    )
    if status != 200:
        print(f"   ❌ Failed to start options flow for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    flow_id = flow_start.get("flow_id")
    if not isinstance(flow_id, str):
        print(f"   ❌ Flow did not return flow_id for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    status, _ = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
        {MENU_SELECTION: MENU_MANAGE_BADGE},
    )
    if status != 200:
        print(f"   ❌ Menu selection failed for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    status, _ = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
        {MANAGE_ACTION: MANAGE_ACTION_ADD},
    )
    if status != 200:
        print(f"   ❌ Add action selection failed for {entity_name}")  # noqa: T201
        return ENTITY_ADD_STATUS_FAILED

    status, badge_form = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
        {"badge_type": badge_type},
    )
    if status != 200:
        print(  # noqa: T201
            f"   ❌ Badge type selection failed for {entity_name}: "
            f"status={status}, response={badge_form}"
        )
        return ENTITY_ADD_STATUS_FAILED

    resolved_payload = dict(payload)
    raw_assigned = resolved_payload.get("assigned_user_ids")
    if isinstance(raw_assigned, list) and raw_assigned:
        label_to_value: dict[str, str] = {}
        data_schema = badge_form.get("data_schema")
        if isinstance(data_schema, list):
            for field in data_schema:
                if (
                    not isinstance(field, dict)
                    or field.get("name") != "assigned_user_ids"
                ):
                    continue
                selector = field.get("selector")
                if not isinstance(selector, dict):
                    continue
                select_def = selector.get("select")
                if not isinstance(select_def, dict):
                    continue
                options = select_def.get("options")
                if not isinstance(options, list):
                    continue
                for option in options:
                    if not isinstance(option, dict):
                        continue
                    label = option.get("label")
                    value = option.get("value")
                    if isinstance(label, str) and isinstance(value, str):
                        label_to_value[label] = value
                break

        if label_to_value:
            resolved_payload["assigned_user_ids"] = [
                label_to_value.get(str(item), str(item)) for item in raw_assigned
            ]

    status, flow_result = await _request_json(
        session,
        "POST",
        f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
        resolved_payload,
    )
    if status != 200:
        print(  # noqa: T201
            f"   ❌ Submit failed for {entity_name}: "
            f"status={status}, response={flow_result}"
        )
        return ENTITY_ADD_STATUS_FAILED

    if flow_result.get("type") == "form" and flow_result.get("step_id") == STEP_INIT:
        return ENTITY_ADD_STATUS_ADDED

    if is_duplicate_flow_result(flow_result):
        return ENTITY_ADD_STATUS_SKIPPED

    error_details = flow_result.get("errors")
    if error_details is not None:
        print(  # noqa: T201
            f"   ℹ️ Flow validation errors for {entity_name}: {error_details}"
        )
    else:
        print(  # noqa: T201
            f"   ℹ️ Unexpected flow response for {entity_name}: {flow_result}"
        )

    return ENTITY_ADD_STATUS_FAILED


async def refresh_duplicate_chore_due_date(
    session: aiohttp.ClientSession,
    ha_url: str,
    entry_id: str,
    chore: dict[str, Any],
) -> None:
    """Refresh due date for an already-existing chore when scenario uses due_date.

    This keeps `now`/`now+offset` scenario shorthand deterministic across repeated
    loads even when a chore add is skipped as duplicate.
    """
    if "due_date" not in chore:
        return

    chore_name = chore.get("name")
    if not isinstance(chore_name, str) or not chore_name:
        return

    payload: dict[str, Any] = {
        SERVICE_FIELD_CONFIG_ENTRY_ID: entry_id,
        "chore_name": chore_name,
        "due_date": resolve_due_date_value(chore["due_date"]),
    }

    completion_criteria = chore.get("completion_criteria")
    assigned_to = chore.get("assigned_to", [])
    if (
        completion_criteria == "independent"
        and isinstance(assigned_to, list)
        and len(assigned_to) == 1
        and isinstance(assigned_to[0], str)
        and assigned_to[0]
    ):
        payload["user_name"] = assigned_to[0]

    async with session.post(
        f"{ha_url}/api/services/{DOMAIN}/set_chore_due_date",
        json=payload,
    ) as response:
        if response.status == 200:
            print(f"   🔄 Refreshed due date: {chore_name}")  # noqa: T201
            return
        body = await response.text()
        print(  # noqa: T201
            f"   ⚠️ Could not refresh due date for {chore_name} "
            f"(status={response.status}): {body[:180]}"
        )


def build_state_seed_payload(
    action: dict[str, Any], entry_id: str
) -> tuple[str, dict[str, Any]]:
    """Build domain service and payload for a post-load seed action."""
    service = str(action["service"])
    payload = dict(action["data"])

    if (
        SERVICE_FIELD_CONFIG_ENTRY_ID not in payload
        and "config_entry_title" not in payload
    ):
        payload[SERVICE_FIELD_CONFIG_ENTRY_ID] = entry_id

    return service, payload


async def run_state_seed_actions(
    session: aiohttp.ClientSession,
    ha_url: str,
    entry_id: str,
    actions: list[dict[str, Any]],
    delay_seconds: float,
) -> tuple[int, int]:
    """Execute optional state-seeding actions after entities are loaded."""
    success_count = 0
    total_count = 0

    print("\n🧪 Seeding chore/reward states...")  # noqa: T201
    for action in actions:
        total_count += 1
        service, payload = build_state_seed_payload(action, entry_id)
        async with session.post(
            f"{ha_url}/api/services/{DOMAIN}/{service}",
            json=payload,
        ) as response:
            if response.status == 200:
                success_count += 1
                print(f"   ✅ {service}")  # noqa: T201
            else:
                body = await response.text()
                print(  # noqa: T201
                    f"   ❌ {service} (status={response.status}): {body[:180]}"
                )
        await asyncio.sleep(delay_seconds)

    return success_count, total_count


async def normalize_rotation_turns(
    session: aiohttp.ClientSession,
    ha_url: str,
    entry_id: str,
    chores: list[dict[str, Any]],
    delay_seconds: float,
) -> tuple[int, int]:
    """Reset/set rotation turn for rotation chores to ensure deterministic seeds.

    Behavior:
    - For every scenario chore with rotation criteria, call `reset_rotation`
      so turn starts at the first assigned user.
    - If scenario chore defines `rotation_turn_user_name`, call
      `set_rotation_turn` after reset to force a specific starting user.
    """
    success_count = 0
    total_count = 0
    rotation_criteria = {"rotation_simple", "rotation_smart"}

    rotation_chores = [
        chore
        for chore in chores
        if str(chore.get("completion_criteria", "")) in rotation_criteria
    ]

    if not rotation_chores:
        return success_count, total_count

    print("\n🔁 Normalizing rotation turns...")  # noqa: T201

    for chore in rotation_chores:
        chore_name = str(chore.get("name", "")).strip()
        if not chore_name:
            continue

        reset_payload: dict[str, Any] = {
            SERVICE_FIELD_CONFIG_ENTRY_ID: entry_id,
            "chore_name": chore_name,
        }
        total_count += 1
        async with session.post(
            f"{ha_url}/api/services/{DOMAIN}/reset_rotation",
            json=reset_payload,
        ) as response:
            if response.status == 200:
                success_count += 1
                print(f"   ✅ reset_rotation: {chore_name}")  # noqa: T201
            else:
                body = await response.text()
                print(  # noqa: T201
                    f"   ❌ reset_rotation: {chore_name} "
                    f"(status={response.status}): {body[:180]}"
                )
        await asyncio.sleep(delay_seconds)

        target_user_name = str(chore.get("rotation_turn_user_name", "")).strip()
        if not target_user_name:
            continue

        set_payload: dict[str, Any] = {
            SERVICE_FIELD_CONFIG_ENTRY_ID: entry_id,
            "chore_name": chore_name,
            "user_name": target_user_name,
        }
        total_count += 1
        async with session.post(
            f"{ha_url}/api/services/{DOMAIN}/set_rotation_turn",
            json=set_payload,
        ) as response:
            if response.status == 200:
                success_count += 1
                print(  # noqa: T201
                    f"   ✅ set_rotation_turn: {chore_name} → {target_user_name}"
                )
            else:
                body = await response.text()
                print(  # noqa: T201
                    f"   ❌ set_rotation_turn: {chore_name} → {target_user_name} "
                    f"(status={response.status}): {body[:180]}"
                )
        await asyncio.sleep(delay_seconds)

    return success_count, total_count


async def load_scenario_to_live_instance(args: argparse.Namespace) -> None:
    """Load scenario entities into a live Home Assistant instance."""
    repo_root = Path(__file__).resolve().parents[1]
    scenario_path = resolve_scenario_path(args.scenario, repo_root)
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

    scenario = load_scenario_file(scenario_path)
    assignees, approvers, chores, badges, rewards, bonuses, penalties = (
        extract_scenario_collections(scenario)
    )
    state_seed_actions = extract_state_seed_actions(scenario)

    print(f"📄 Scenario: {scenario_path}")  # noqa: T201
    print(  # noqa: T201
        "📊 Planned load: "
        f"{len(assignees)} assignees, "
        f"{len(approvers)} approvers, "
        f"{len(chores)} chores, "
        f"{len(badges)} badges, "
        f"{len(rewards)} rewards, "
        f"{len(bonuses)} bonuses, "
        f"{len(penalties)} penalties"
    )
    if state_seed_actions:
        print(  # noqa: T201
            f"🧪 State seed actions available: {len(state_seed_actions)}"
        )

    if args.dry_run:
        print("🧪 Dry-run mode: scenario validated, no API calls made")  # noqa: T201
        return

    token = get_token(args)
    if not token:
        raise RuntimeError("No token provided")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"{args.ha_url}/api/") as response:
            if response.status != 200:
                raise RuntimeError(f"HA API unavailable (status={response.status})")

        entry_id = await find_choreops_entry_id(session, args.ha_url)
        print(f"✅ Connected to ChoreOps entry: {entry_id}")  # noqa: T201

        if args.reset:
            print("🗑️ Resetting transactional data...")  # noqa: T201
            await reset_transactional_data(session, args.ha_url, entry_id)
            await asyncio.sleep(1.0)
            print("✅ Reset complete")  # noqa: T201

        total_added = 0
        total_skipped = 0
        total_failed = 0
        total_attempted = 0
        present_chore_names: set[str] = set()

        async def _bulk_add(
            title: str,
            menu_key: str,
            entities: list[dict[str, Any]],
            payload_builder,
        ) -> None:
            nonlocal total_added, total_skipped, total_failed, total_attempted
            print(f"\n{title}")  # noqa: T201
            for entity in entities:
                name = str(entity.get("name", "(unnamed)"))
                entity_payload = payload_builder(entity)
                total_attempted += 1
                add_status = await add_entity_via_options_flow(
                    session,
                    args.ha_url,
                    entry_id,
                    menu_key,
                    name,
                    entity_payload,
                )
                if add_status == ENTITY_ADD_STATUS_ADDED:
                    total_added += 1
                    print(f"   ✅ {name}")  # noqa: T201
                    if menu_key == MENU_MANAGE_CHORE:
                        present_chore_names.add(name)
                elif add_status == ENTITY_ADD_STATUS_SKIPPED:
                    total_skipped += 1
                    print(f"   ⏭️ {name} (already exists)")  # noqa: T201
                    if menu_key == MENU_MANAGE_CHORE:
                        present_chore_names.add(name)
                        await refresh_duplicate_chore_due_date(
                            session,
                            args.ha_url,
                            entry_id,
                            entity,
                        )
                else:
                    total_failed += 1
                    print(f"   ❌ {name}")  # noqa: T201
                await asyncio.sleep(args.delay)

        await _bulk_add(
            "👤 Adding assignees...",
            MENU_MANAGE_USER,
            assignees,
            build_assignee_payload,
        )
        await _bulk_add(
            "🛡️ Adding approvers...", MENU_MANAGE_USER, approvers, build_approver_payload
        )
        await _bulk_add(
            "🧹 Adding chores...", MENU_MANAGE_CHORE, chores, build_chore_payload
        )

        print("\n🏅 Adding badges...")  # noqa: T201
        for badge in badges:
            name = str(badge.get("name", "(unnamed)"))
            badge_payload = build_badge_payload(badge)
            badge_type = str(badge.get("type", "cumulative"))
            total_attempted += 1
            add_status = await add_badge_via_options_flow(
                session,
                args.ha_url,
                entry_id,
                name,
                badge_payload,
                badge_type,
            )
            if add_status == ENTITY_ADD_STATUS_ADDED:
                total_added += 1
                print(f"   ✅ {name}")  # noqa: T201
            elif add_status == ENTITY_ADD_STATUS_SKIPPED:
                total_skipped += 1
                print(f"   ⏭️ {name} (already exists)")  # noqa: T201
            else:
                total_failed += 1
                print(f"   ❌ {name}")  # noqa: T201
            await asyncio.sleep(args.delay)

        if args.reset:
            rotation_chores_present = [
                chore
                for chore in chores
                if str(chore.get("name", "")).strip() in present_chore_names
            ]
            rotation_success, rotation_total = await normalize_rotation_turns(
                session,
                args.ha_url,
                entry_id,
                rotation_chores_present,
                args.delay,
            )
            if rotation_total:
                print(  # noqa: T201
                    f"✅ Rotation normalization succeeded: "
                    f"{rotation_success}/{rotation_total}"
                )

        await _bulk_add(
            "🎁 Adding rewards...", MENU_MANAGE_REWARD, rewards, build_reward_payload
        )
        await _bulk_add(
            "✨ Adding bonuses...", MENU_MANAGE_BONUS, bonuses, build_bonus_payload
        )
        await _bulk_add(
            "⚠️ Adding penalties...",
            MENU_MANAGE_PENALTY,
            penalties,
            build_penalty_payload,
        )

        if state_seed_actions and args.seed_states:
            seed_success, seed_total = await run_state_seed_actions(
                session,
                args.ha_url,
                entry_id,
                state_seed_actions,
                args.delay,
            )
            print(f"✅ Seed actions succeeded: {seed_success}/{seed_total}")  # noqa: T201
        elif state_seed_actions:
            print(  # noqa: T201
                "ℹ️ Scenario includes state seed actions. "
                "Re-run with --seed-states to apply them"
            )

    print("\n🎉 Scenario load complete")  # noqa: T201
    print(f"✅ Added: {total_added}/{total_attempted}")  # noqa: T201
    print(f"⏭️ Skipped: {total_skipped}/{total_attempted}")  # noqa: T201
    print(f"❌ Failed: {total_failed}/{total_attempted}")  # noqa: T201


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the scenario loader."""
    parser = argparse.ArgumentParser(
        description="Load ChoreOps scenario data into a live Home Assistant instance"
    )
    parser.add_argument(
        "--scenario",
        default=DEFAULT_SCENARIO_PATH,
        help=(
            "Scenario YAML path (absolute or repo-relative). "
            f"Default: {DEFAULT_SCENARIO_PATH}"
        ),
    )
    parser.add_argument(
        "--ha-url",
        default=DEFAULT_HA_URL,
        help=f"Home Assistant base URL. Default: {DEFAULT_HA_URL}",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Long-lived HA token (optional; use token env var for safer usage)",
    )
    parser.add_argument(
        "--token-env",
        default=DEFAULT_TOKEN_ENV,
        help=(
            "Environment variable to read token from when --token is omitted. "
            f"Default: {DEFAULT_TOKEN_ENV}"
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Run choreops.reset_transactional_data before loading",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate scenario and print planned actions without API calls",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Delay in seconds between entity submissions. Default: {DEFAULT_DELAY_SECONDS}",
    )
    parser.add_argument(
        "--seed-states",
        action="store_true",
        help="Apply optional scenario state seed actions after entity load",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(load_scenario_to_live_instance(args))


if __name__ == "__main__":
    main()
