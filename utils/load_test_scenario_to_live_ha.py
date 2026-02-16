#!/usr/bin/env python3
"""Development Utility: Load Test Scenario Data into Live Home Assistant Instance.

This script is a MANUAL DEVELOPMENT TOOL (not part of automated tests) that:
1. Connects to a running Home Assistant instance via REST API
2. Uses the KidsChores options flow to programmatically add entities
3. Loads test scenario data from testdata_scenario_full.yaml

USE CASES:
- Quickly populate a dev instance with realistic test data
- Test the dashboard UI with real entities
- Verify options flow works end-to-end
- Reset and reload test data during development

REQUIREMENTS:
- Home Assistant running at http://localhost:8123
- KidsChores integration already added via UI
- Long-lived access token from Profile → Security

USAGE:
    # Load test data into running instance
    python utils/load_test_scenario_to_live_ha.py

    # Reset all data first, then load
    python utils/load_test_scenario_to_live_ha.py --reset

NOT FOR:
- Automated testing (use pytest tests instead)
- Production deployments
- CI/CD pipelines
"""

import argparse
import asyncio
from pathlib import Path

import aiohttp
import yaml


async def load_scenario_to_live_instance(reset_first: bool = False):
    """Load test scenario data into a live Home Assistant instance via REST API."""

    # Load scenario data (use performance_stress for maximum dataset)
    scenario_file = Path(
        "/workspaces/kidschores-ha/tests/testdata_scenario_performance_stress.yaml"
    )
    with open(scenario_file, encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    print("🔌 Connecting to Home Assistant REST API...")  # noqa: T201
    ha_url = "http://localhost:8123"

    # Get access token from user
    print("\n🔑 You need a long-lived access token from Home Assistant.")  # noqa: T201
    print("   Go to: http://localhost:8123/profile/security")  # noqa: T201
    print("   Scroll down and create a 'Long-Lived Access Token'")  # noqa: T201
    token = input("\nPaste your access token here: ").strip()

    if not token:
        print("❌ No token provided")  # noqa: T201
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Test connection
        try:
            async with session.get(f"{ha_url}/api/") as resp:
                if resp.status != 200:
                    print(f"❌ API returned status {resp.status}")  # noqa: T201
                    return
        except aiohttp.ClientError:
            print("❌ Home Assistant not running at http://localhost:8123")  # noqa: T201
            print("   Start it first!")  # noqa: T201
            return

        print("✅ Connected to Home Assistant")  # noqa: T201

        # Find the KidsChores config entry
        print("\n🔍 Finding KidsChores config entry...")  # noqa: T201
        async with session.get(f"{ha_url}/api/config/config_entries/entry") as resp:
            if resp.status != 200:
                print("❌ Could not fetch config entries")  # noqa: T201
                return
            entries = await resp.json()

        kidschores_entry = None
        for entry in entries:
            if entry.get("domain") == "kidschores":
                kidschores_entry = entry
                break

        if not kidschores_entry:
            print("❌ KidsChores integration not found!")  # noqa: T201
            print(  # noqa: T201
                "   Please add it via Settings → Integrations → Add Integration → KidsChores"
            )
            return

        entry_id = kidschores_entry["entry_id"]
        print(f"✅ Found KidsChores entry: {entry_id}")  # noqa: T201

        # Reset all data if requested
        if reset_first:
            print("\n🗑️  Resetting all KidsChores data...")  # noqa: T201
            async with session.post(
                f"{ha_url}/api/services/kidschores/reset_all_data", json={}
            ) as resp:
                if resp.status == 200:
                    print("✅ Reset complete")  # noqa: T201
                    await asyncio.sleep(2)  # Wait for reload to complete
                else:
                    print(f"⚠️  Reset returned status {resp.status}")  # noqa: T201

        # Helper to start and complete options flow steps
        async def add_entity_via_flow(
            menu_selection: str, entity_data: dict, entity_name: str
        ):
            """Add an entity via options flow following the test pattern."""
            # Step 1: Start options flow (goes to init step)
            async with session.post(
                f"{ha_url}/api/config/config_entries/options/flow",
                json={"handler": entry_id},
            ) as resp:
                if resp.status != 200:
                    print(f"   ❌ Failed to start flow for {entity_name}")  # noqa: T201
                    return False
                flow_result = await resp.json()

            flow_id = flow_result["flow_id"]

            # Step 2: From init menu, select entity type (e.g., "manage_kid")
            async with session.post(
                f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
                json={"menu_selection": menu_selection},
            ) as resp:
                if resp.status != 200:
                    print(f"   ❌ Failed menu selection for {entity_name}")  # noqa: T201
                    return False
                flow_result = await resp.json()

            # Step 3: From manage_entity step, select "add" action
            async with session.post(
                f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
                json={"manage_action": "add"},
            ) as resp:
                if resp.status != 200:
                    print(f"   ❌ Failed to select add action for {entity_name}")  # noqa: T201
                    return False
                flow_result = await resp.json()

            # Step 4: Submit entity data to add_<entity> step
            async with session.post(
                f"{ha_url}/api/config/config_entries/options/flow/{flow_id}",
                json=entity_data,
            ) as resp:
                if resp.status != 200:
                    print(f"   ❌ Failed to add {entity_name}")  # noqa: T201
                    return False
                flow_result = await resp.json()

            # After successful add, should return to init menu
            return (
                flow_result.get("type") == "form"
                and flow_result.get("step_id") == "init"
            )

        # Add kids
        print("\n👶 Adding kids...")  # noqa: T201
        for kid_info in scenario["family"]["kids"]:
            kid_name = kid_info["name"]
            kid_data = {
                "kid_name": kid_name,
            }
            if await add_entity_via_flow("manage_kid", kid_data, kid_name):
                print(f"   ✅ {kid_name}")  # noqa: T201
            await asyncio.sleep(0.5)

        # Add parents
        print("\n👨 Adding parents...")  # noqa: T201
        for parent_info in scenario["family"]["parents"]:
            parent_name = parent_info["name"]
            parent_data = {
                "parent_name": parent_name,
            }
            if await add_entity_via_flow("manage_parent", parent_data, parent_name):
                print(f"   ✅ {parent_name}")  # noqa: T201
            await asyncio.sleep(0.5)

        # Add chores
        print("\n🧹 Adding chores...")  # noqa: T201
        for chore_info in scenario["chores"]:
            chore_name = chore_info["name"]
            chore_data = {
                "chore_name": chore_name,
                "default_points": chore_info.get("points", 10),
                "assigned_kids": chore_info.get("assigned_to", []),
                "icon": chore_info.get("icon", "mdi:broom"),
            }
            if await add_entity_via_flow("manage_chore", chore_data, chore_name):
                print(f"   ✅ {chore_name}")  # noqa: T201
            await asyncio.sleep(0.5)

        # Add badges (skip for now - they require badge type selection first)
        print("\n🏆 Skipping badges (requires badge type selection, complex flow)")  # noqa: T201

        # Add rewards
        print("\n🎁 Adding rewards...")  # noqa: T201
        for reward_info in scenario.get("rewards", []):
            reward_name = reward_info["name"]
            reward_data = {
                "reward_name": reward_name,
                "reward_cost": reward_info.get("cost", 50),
                "icon": reward_info.get("icon", "mdi:gift"),
            }
            if await add_entity_via_flow("manage_reward", reward_data, reward_name):
                print(f"   ✅ {reward_name}")  # noqa: T201
            await asyncio.sleep(0.5)

        # Add bonuses
        print("\n✨ Adding bonuses...")  # noqa: T201
        for bonus_info in scenario.get("bonuses", []):
            bonus_name = bonus_info["name"]
            bonus_data = {
                "bonus_name": bonus_name,
                "bonus_points": float(bonus_info.get("points", 10)),
                "bonus_description": bonus_info.get("description", ""),
                "icon": bonus_info.get("icon", "mdi:sparkles"),
            }
            if await add_entity_via_flow("manage_bonus", bonus_data, bonus_name):
                print(f"   ✅ {bonus_name}")  # noqa: T201
            await asyncio.sleep(0.5)

        # Add penalties
        print("\n⚠️  Adding penalties...")  # noqa: T201
        for penalty_info in scenario.get("penalties", []):
            penalty_name = penalty_info["name"]
            # Penalties use positive values in the form (system stores as negative)
            points_value = abs(penalty_info.get("points", -5))
            penalty_data = {
                "penalty_name": penalty_name,
                "penalty_points": float(points_value),
                "penalty_description": penalty_info.get("description", ""),
                "icon": penalty_info.get("icon", "mdi:alert"),
            }
            if await add_entity_via_flow("manage_penalty", penalty_data, penalty_name):
                print(f"   ✅ {penalty_name}")  # noqa: T201
            await asyncio.sleep(0.5)

        print("\n🎉 All entities loaded via options flow!")  # noqa: T201
        print("\n📊 Summary:")  # noqa: T201
        print(f"  👶 {len(scenario['family']['kids'])} kids")  # noqa: T201
        print(f"  👨 {len(scenario['family']['parents'])} parents")  # noqa: T201
        print(f"  🧹 {len(scenario['chores'])} chores")  # noqa: T201
        print(f"  🏆 {len(scenario.get('badges', []))} badges (skipped)")  # noqa: T201
        print(f"  🎁 {len(scenario.get('rewards', []))} rewards")  # noqa: T201
        print(f"  ✨ {len(scenario.get('bonuses', []))} bonuses")  # noqa: T201
        print(f"  ⚠️  {len(scenario.get('penalties', []))} penalties")  # noqa: T201
        print("\n✅ Check Home Assistant - all entities should be visible now!")  # noqa: T201
        print("   View them in Settings → Integrations → KidsChores")  # noqa: T201


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load test scenario data into KidsChores via options flow (dev tool)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all KidsChores data before loading new data",
    )
    args = parser.parse_args()

    asyncio.run(load_scenario_to_live_instance(reset_first=args.reset))
