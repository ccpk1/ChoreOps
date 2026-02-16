#!/usr/bin/env python3
"""Convert legacy scenario_stress.yaml to modern format.

Uses scenario_full.yaml as the definitive template for all structures.
Only copies fields that exist in the modern format.
"""

from pathlib import Path

import yaml

# Valid fields per entity type (from scenario_full.yaml template)
VALID_KID_FIELDS = {
    "name",
    "ha_user",
    "dashboard_language",
    "enable_mobile_notifications",
    "mobile_notify_service",
    "enable_persistent_notifications",
}

VALID_PARENT_FIELDS = {
    "name",
    "ha_user",
    "kids",
    "enable_mobile_notifications",
    "mobile_notify_service",
    "enable_persistent_notifications",
}

VALID_CHORE_FIELDS = {
    "name",
    "assigned_to",
    "points",
    "description",
    "icon",
    "completion_criteria",
    "recurring_frequency",
    "auto_approve",
    "show_on_calendar",
    "labels",
    "applicable_days",
    "notifications",
    "due_date",
    "custom_interval",
    "custom_interval_unit",
    "approval_reset_type",
    "approval_reset_pending_claim_action",
    "overdue_handling_type",
}

VALID_BADGE_FIELDS = {
    "name",
    "type",
    "assigned_to",
    "award_points",
    "target_type",
    "target_threshold_value",
    "icon",
    "start_date",
    "end_date",
}

VALID_REWARD_FIELDS = {"name", "cost", "icon", "description"}

VALID_PENALTY_FIELDS = {"name", "points", "icon", "description"}

VALID_BONUS_FIELDS = {"name", "points", "icon", "description"}

VALID_ACHIEVEMENT_FIELDS = {
    "name",
    "type",
    "assigned_to",
    "target_value",
    "reward_points",
    "icon",
    "description",
}

VALID_CHALLENGE_FIELDS = {
    "name",
    "type",
    "assigned_to",
    "target_value",
    "reward_points",
    "start_date",
    "end_date",
    "icon",
    "description",
}

# Field mappings: legacy key -> modern key
FIELD_MAPPINGS = {
    "ha_user_name": "ha_user",
    "points_value": "points",
}


def convert_entity(
    entity: dict, valid_fields: set, field_mappings: dict | None = None
) -> dict:
    """Convert a single entity, only keeping valid fields."""
    if field_mappings is None:
        field_mappings = FIELD_MAPPINGS

    result = {}
    for key, value in entity.items():
        # Apply field mapping
        mapped_key = field_mappings.get(key, key)

        # Only include valid fields
        if mapped_key in valid_fields:
            result[mapped_key] = value

    return result


def convert_chore(chore: dict, all_kid_names: list[str]) -> dict:
    """Convert a chore with special handling for legacy structures."""
    result = {}

    # Required fields
    result["name"] = chore.get("name", "Unnamed Chore")
    result["assigned_to"] = chore.get("assigned_to", all_kid_names[:1])

    # Points: legacy uses points_value, modern uses points
    if "points_value" in chore:
        result["points"] = float(chore["points_value"])
    elif "points" in chore:
        result["points"] = float(chore["points"])
    else:
        result["points"] = 10.0

    # Icon
    if "icon" in chore:
        result["icon"] = chore["icon"]

    # Completion criteria
    result["completion_criteria"] = chore.get("completion_criteria", "independent")

    # Recurring frequency - handle legacy recurrence structure
    if "recurrence" in chore:
        recurrence = chore["recurrence"]
        freq = recurrence.get("frequency", "daily")
        result["recurring_frequency"] = freq

        # Custom interval handling
        if freq == "custom" and "interval" in recurrence:
            result["custom_interval"] = recurrence["interval"]
            result["custom_interval_unit"] = recurrence.get("interval_unit", "days")
    elif "recurring_frequency" in chore:
        result["recurring_frequency"] = chore["recurring_frequency"]
    else:
        result["recurring_frequency"] = "daily"

    # Auto approve: legacy uses requires_approval (inverse logic)
    if "requires_approval" in chore:
        result["auto_approve"] = not chore["requires_approval"]
    elif "auto_approve" in chore:
        result["auto_approve"] = chore["auto_approve"]
    else:
        result["auto_approve"] = False

    # Copy other optional valid fields directly
    for field in [
        "description",
        "show_on_calendar",
        "labels",
        "applicable_days",
        "notifications",
        "due_date",
        "approval_reset_type",
        "approval_reset_pending_claim_action",
        "overdue_handling_type",
    ]:
        if field in chore:
            result[field] = chore[field]

    return result


def convert_badge(badge: dict, all_kid_names: list[str]) -> dict:
    """Convert a badge with special handling for legacy structures."""
    result = {}

    result["name"] = badge.get("name", "Unnamed Badge")
    result["type"] = badge.get("type", "cumulative")
    result["assigned_to"] = badge.get("assigned_to", all_kid_names[:1])

    # Award points
    if "award_points" in badge:
        result["award_points"] = badge["award_points"]
    elif "points" in badge:
        result["award_points"] = badge["points"]
    else:
        result["award_points"] = 0

    # Target type and threshold
    if "target_type" in badge:
        result["target_type"] = badge["target_type"]
    if "target_threshold_value" in badge:
        result["target_threshold_value"] = badge["target_threshold_value"]
    elif "threshold" in badge:
        result["target_threshold_value"] = badge["threshold"]

    # Optional fields
    for field in ["icon", "start_date", "end_date"]:
        if field in badge:
            result[field] = badge[field]

    return result


def write_yaml_with_proper_indent(data: dict, filepath: Path):
    """Write YAML with proper 2-space indentation matching scenario_full.yaml style."""

    with open(filepath, "w", encoding="utf-8") as f:
        # Write header
        f.write("# Test Scenario: STRESS (Modern Config-Flow Format)\n")
        f.write("# " + "=" * 77 + "\n")
        f.write("# Converted from legacy format for modern setup_from_yaml() loader\n")
        f.write("#\n")
        f.write(
            "# Scale: 100 kids, 25 parents, 55 chores, 18 badges, ~1500+ entities\n"
        )
        f.write("# Use case: Performance testing and stress testing\n")
        f.write("# " + "=" * 77 + "\n\n")

        # Write system section
        f.write("system:\n")
        f.write('  points_label: "Star Points"\n')
        f.write('  points_icon: "mdi:star"\n\n')

        # Write kids section
        f.write("kids:\n")
        for kid in data.get("kids", []):
            f.write(f'  - name: "{kid["name"]}"\n')
            f.write(f'    ha_user: "{kid["ha_user"]}"\n')
            if kid.get("dashboard_language"):
                f.write(f'    dashboard_language: "{kid["dashboard_language"]}"\n')
            f.write("\n")

        # Write parents section
        f.write("parents:\n")
        for parent in data.get("parents", []):
            f.write(f'  - name: "{parent["name"]}"\n')
            f.write(f'    ha_user: "{parent["ha_user"]}"\n')
            if "kids" in parent:
                kids_str = ", ".join(f'"{k}"' for k in parent["kids"])
                f.write(f"    kids: [{kids_str}]\n")
            f.write("\n")

        # Write chores section
        f.write("chores:\n")
        for chore in data.get("chores", []):
            f.write(f'  - name: "{chore["name"]}"\n')
            assigned = ", ".join(f'"{a}"' for a in chore["assigned_to"])
            f.write(f"    assigned_to: [{assigned}]\n")
            f.write(f"    points: {chore['points']}\n")
            if chore.get("icon"):
                f.write(f'    icon: "{chore["icon"]}"\n')
            f.write(
                f'    completion_criteria: "{chore.get("completion_criteria", "independent")}"\n'
            )
            f.write(
                f'    recurring_frequency: "{chore.get("recurring_frequency", "daily")}"\n'
            )
            if chore.get("auto_approve"):
                f.write("    auto_approve: true\n")
            if chore.get("custom_interval"):
                f.write(f"    custom_interval: {chore['custom_interval']}\n")
                f.write(
                    f'    custom_interval_unit: "{chore.get("custom_interval_unit", "days")}"\n'
                )
            f.write("\n")

        # Write badges section
        f.write("badges:\n")
        for badge in data.get("badges", []):
            f.write(f'  - name: "{badge["name"]}"\n')
            f.write(f'    type: "{badge.get("type", "cumulative")}"\n')
            assigned = ", ".join(f'"{a}"' for a in badge.get("assigned_to", []))
            f.write(f"    assigned_to: [{assigned}]\n")
            f.write(f"    award_points: {badge.get('award_points', 0)}\n")
            if badge.get("target_type"):
                f.write(f'    target_type: "{badge["target_type"]}"\n')
            if badge.get("target_threshold_value"):
                f.write(
                    f"    target_threshold_value: {badge['target_threshold_value']}\n"
                )
            if badge.get("icon"):
                f.write(f'    icon: "{badge["icon"]}"\n')
            f.write("\n")

        # Write rewards section
        f.write("rewards:\n")
        for reward in data.get("rewards", []):
            f.write(f'  - name: "{reward["name"]}"\n')
            f.write(f"    cost: {reward.get('cost', reward.get('points', 10))}\n")
            if reward.get("icon"):
                f.write(f'    icon: "{reward["icon"]}"\n')
            if reward.get("description"):
                f.write(f'    description: "{reward["description"]}"\n')
            f.write("\n")

        # Write penalties section
        f.write("penalties:\n")
        for penalty in data.get("penalties", []):
            f.write(f'  - name: "{penalty["name"]}"\n')
            f.write(f"    points: {penalty.get('points', 10)}\n")
            if penalty.get("icon"):
                f.write(f'    icon: "{penalty["icon"]}"\n')
            if penalty.get("description"):
                f.write(f'    description: "{penalty["description"]}"\n')
            f.write("\n")

        # Write bonuses section
        f.write("bonuses:\n")
        for bonus in data.get("bonuses", []):
            f.write(f'  - name: "{bonus["name"]}"\n')
            f.write(f"    points: {bonus.get('points', 10)}\n")
            if bonus.get("icon"):
                f.write(f'    icon: "{bonus["icon"]}"\n')
            if bonus.get("description"):
                f.write(f'    description: "{bonus["description"]}"\n')
            f.write("\n")


def convert_scenario_stress():
    """Convert legacy stress scenario to modern format."""

    legacy_path = Path(
        "/workspaces/kidschores-ha/tests/legacy/testdata_scenario_performance_stress.yaml"
    )
    output_path = Path("/workspaces/kidschores-ha/tests/scenarios/scenario_stress.yaml")

    with open(legacy_path, encoding="utf-8") as f:
        legacy_data = yaml.safe_load(f)


    modern_data = {}
    all_kid_names = []

    # Convert kids
    if "family" in legacy_data and "kids" in legacy_data["family"]:
        modern_kids = []
        for kid in legacy_data["family"]["kids"]:
            modern_kid = convert_entity(kid, VALID_KID_FIELDS)
            if "name" in modern_kid:
                all_kid_names.append(modern_kid["name"])
            modern_kids.append(modern_kid)
        modern_data["kids"] = modern_kids

    # Convert parents
    if "family" in legacy_data and "parents" in legacy_data["family"]:
        modern_parents = []
        for parent in legacy_data["family"]["parents"]:
            modern_parent = convert_entity(parent, VALID_PARENT_FIELDS)
            # If no kids specified, assign all kids
            if "kids" not in modern_parent:
                modern_parent["kids"] = all_kid_names
            modern_parents.append(modern_parent)
        modern_data["parents"] = modern_parents

    # Convert chores with special handling
    if "chores" in legacy_data:
        modern_chores = []
        for chore in legacy_data["chores"]:
            modern_chore = convert_chore(chore, all_kid_names)
            modern_chores.append(modern_chore)
        modern_data["chores"] = modern_chores

    # Convert badges with special handling
    if "badges" in legacy_data:
        modern_badges = []
        for badge in legacy_data["badges"]:
            modern_badge = convert_badge(badge, all_kid_names)
            modern_badges.append(modern_badge)
        modern_data["badges"] = modern_badges

    # Convert rewards
    if "rewards" in legacy_data:
        modern_rewards = []
        for reward in legacy_data["rewards"]:
            modern_reward = convert_entity(reward, VALID_REWARD_FIELDS)
            modern_rewards.append(modern_reward)
        modern_data["rewards"] = modern_rewards

    # Convert penalties
    if "penalties" in legacy_data:
        modern_penalties = []
        for penalty in legacy_data["penalties"]:
            modern_penalty = convert_entity(penalty, VALID_PENALTY_FIELDS)
            modern_penalties.append(modern_penalty)
        modern_data["penalties"] = modern_penalties

    # Convert bonuses
    if "bonuses" in legacy_data:
        modern_bonuses = []
        for bonus in legacy_data["bonuses"]:
            modern_bonus = convert_entity(bonus, VALID_BONUS_FIELDS)
            modern_bonuses.append(modern_bonus)
        modern_data["bonuses"] = modern_bonuses

    # Write output with proper formatting
    write_yaml_with_proper_indent(modern_data, output_path)



if __name__ == "__main__":
    convert_scenario_stress()
