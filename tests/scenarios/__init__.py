"""Test scenarios for ChoreOps integration.

This package contains YAML scenario files that can be loaded
using the setup_from_yaml() helper function.

Files:
- scenario_full.yaml: Comprehensive test scenario with 3 assignees, 2 approvers, 18 chores
  covering all completion criteria (independent, shared_all, shared_first) and
  various frequencies (daily, weekly, monthly, custom).

Usage:
    from tests.helpers.setup import setup_from_yaml

    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )

    # Access entities:
    assignee_id = result.assignee_ids["Zoë"]
    chore_id = result.chore_ids["Feed the cåts"]
    coordinator = result.coordinator
"""
