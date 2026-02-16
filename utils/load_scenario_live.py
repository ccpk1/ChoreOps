#!/usr/bin/env python3
"""Load test scenario data into a running Home Assistant instance via API."""

# pylint: disable=protected-access  # Utility script accesses coordinator internals for testing
# pylint: disable=invalid-name  # DOMAIN constant follows HA convention
# pylint: disable=wrong-import-position  # sys.path modification required before HA imports

import asyncio
from pathlib import Path
import sys
import uuid

import yaml

# Add the HA paths
sys.path.insert(0, "/workspaces/core")
# Add kidschores path for data_builders import
sys.path.insert(0, "/workspaces/kidschores-ha")

# pylint: disable=no-name-in-module,import-error  # Legacy/dev script - may use deprecated imports
from homeassistant.bootstrap import async_setup_hass
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.runner import RuntimeConfig

# Import data_builders for build_chore
from custom_components.kidschores import data_builders as eh


async def load_scenario_to_running_instance():  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Load scenario data into running Home Assistant instance."""

    # Load the full scenario file
    scenario_file = Path("/workspaces/kidschores-ha/tests/testdata_scenario_full.yaml")
    with open(scenario_file, encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    print("🏠 Starting/Connecting to Home Assistant instance...")  # noqa: T201

    # Get/start the HA instance using RuntimeConfig
    config_dir = "/workspaces/core/config"
    runtime_config = RuntimeConfig(
        config_dir=config_dir,
        verbose=False,
        log_rotate_days=None,
        log_file="",
        log_no_color=False,
        skip_pip=True,
        skip_pip_packages=[],
        safe_mode=False,
        debug=False,
        open_ui=False,
        recovery_mode=False,
    )
    hass = await async_setup_hass(runtime_config)

    if hass is None:
        print("❌ Failed to create Home Assistant instance")  # noqa: T201
        return

    # Start Home Assistant if not running
    if hass.state.name != "running":
        print("⏳ Starting Home Assistant...")  # noqa: T201
        start_event = asyncio.Event()

        def on_started(event):  # pylint: disable=unused-argument
            start_event.set()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, on_started)

        # Start HA
        await hass.async_start()

        # Wait for it to finish starting
        await start_event.wait()
        print("✅ Home Assistant started successfully")  # noqa: T201
    else:
        print("✅ Connected to running Home Assistant")  # noqa: T201

    # Get the KidsChores coordinator
    DOMAIN = "kidschores"

    # Check if integration needs to be set up
    entries = hass.config_entries.async_entries(DOMAIN)

    if not entries:
        print("🔧 No KidsChores config entry found, creating one...")  # noqa: T201

        # Start the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        # If it's a form, submit it (assuming default setup)
        if result.get("type") == "form":
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )

        # Get the created entry
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            print("❌ Failed to create config entry")  # noqa: T201
            return

        print("✅ Created KidsChores config entry")  # noqa: T201

    entry = entries[0]

    # Wait for the integration to be loaded
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        print("⏳ Waiting for integration to load...")  # noqa: T201
        await asyncio.sleep(2)

    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        print("❌ KidsChores integration failed to load")  # noqa: T201
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    print(f"✅ Found KidsChores coordinator for entry: {entry.title}")  # noqa: T201

    # Track IDs for relationships
    kid_name_to_id = {}
    badge_name_to_id = {}

    # Clear existing data
    print("\n🗑️  Clearing existing data...")  # noqa: T201
    coordinator.kids_data.clear()
    coordinator.parents_data.clear()
    coordinator.chores_data.clear()
    coordinator.badges_data.clear()
    coordinator.rewards_data.clear()
    coordinator.bonuses_data.clear()
    coordinator.penalties_data.clear()

    # Create kids
    print("\n👶 Loading kids...")  # noqa: T201
    for kid_info in scenario["family"]["kids"]:
        kid_id = str(uuid.uuid4())
        kid_name = kid_info["name"]
        kid_name_to_id[kid_name] = kid_id

        progress = scenario.get("progress", {}).get(kid_name, {})

        kid_data = {
            "internal_id": kid_id,
            "name": kid_name,
            "points": float(progress.get("points", 0.0)),
            "ha_user_id": "",
            "enable_notifications": True,
            "mobile_notify_service": "",
            "use_persistent_notifications": True,
            "dashboard_language": "en",
            "chore_states": {},
            "badges_earned": {},
            "claimed_chores": [],
            "approved_chores": [],
            "reward_claims": {},
            "bonus_applies": {},
            "penalty_applies": {},
            "point_stats": {
                "points_net_all_time": float(
                    progress.get("point_stats", {}).get(
                        "points_net_all_time", progress.get("lifetime_points", 0.0)
                    )  # Fallback for old format
                )
            },
        }

        # Direct storage write (modern pattern)
        coordinator._data["kids"][kid_id] = kid_data
        print(f"  ✓ {kid_name}: {kid_data['points']} points")  # noqa: T201

    # Create parents
    print("\n👨 Loading parents...")  # noqa: T201
    for parent_info in scenario["family"]["parents"]:
        parent_id = str(uuid.uuid4())
        parent_data = {
            "internal_id": parent_id,
            "name": parent_info["name"],
            "ha_user_id": "",
            "enable_notifications": True,
            "mobile_notify_service": "",
            "use_persistent_notifications": True,
            "dashboard_language": "en",
        }
        # Direct storage write (modern pattern)
        coordinator._data["parents"][parent_id] = parent_data
        print(f"  ✓ {parent_info['name']}")  # noqa: T201

    # Create badges first (needed for kid badge relationships)
    print("\n🏆 Loading badges...")  # noqa: T201
    for badge_info in scenario.get("badges", []):
        badge_id = str(uuid.uuid4())
        badge_name = badge_info["name"]
        badge_name_to_id[badge_name] = badge_id

        maintenance = badge_info.get("maintenance", {})
        badge_data = {
            "internal_id": badge_id,
            "name": badge_name,
            "badge_type": badge_info.get("type", "cumulative"),
            "icon": badge_info.get("icon", "mdi:star"),
            "threshold": badge_info.get("threshold", 100),
            "points_multiplier": badge_info.get("points_multiplier", 1.0),
            "description": badge_info.get("award", ""),
            "maintenance_interval": maintenance.get("interval", ""),
            "maintenance_points_required": maintenance.get("required_points", 0),
            "demote_on_fail": maintenance.get("demote_on_fail", False),
        }
        # Direct storage write (modern pattern)
        coordinator._data.setdefault("badges", {})[badge_id] = badge_data
        print(f"  ✓ {badge_name} ({badge_info.get('type', 'cumulative')})")  # noqa: T201

    # Add earned badges to kids
    for kid_name, progress in scenario.get("progress", {}).items():
        if kid_name in kid_name_to_id:
            kid_id = kid_name_to_id[kid_name]
            for badge_name in progress.get("badges_earned", []):
                if badge_name in badge_name_to_id:
                    badge_id = badge_name_to_id[badge_name]
                    coordinator.kids_data[kid_id]["badges_earned"][badge_id] = {
                        "internal_id": badge_id,
                        "last_awarded_date": None,
                        "multiplier": scenario.get("badges", [{}])[0].get(
                            "points_multiplier", 1.0
                        ),
                    }

    # Create chores
    print("\n🧹 Loading chores...")  # noqa: T201
    for chore_info in scenario["chores"]:
        chore_id = str(uuid.uuid4())
        assigned_kid_ids = [
            kid_name_to_id[name]
            for name in chore_info.get("assigned_to", [])
            if name in kid_name_to_id
        ]

        chore_data = {
            "internal_id": chore_id,
            "name": chore_info["name"],
            "default_points": chore_info.get("points", 10),
            "assigned_kids": assigned_kid_ids,
            "partial_allowed": False,
            "shared_chore": len(assigned_kid_ids) > 1,
            "allow_multiple_claims_per_day": False,
            "description": "",
            "labels": [],
            "icon": chore_info.get("icon", "mdi:broom"),
            "recurring_frequency": chore_info.get("type", ""),
            "custom_interval": None,
            "custom_interval_unit": None,
            "due_date": None,
            "applicable_days": [0, 1, 2, 3, 4, 5, 6],
            "notify_on_claim": True,
            "notify_on_approval": True,
            "notify_on_disapproval": True,
            "state": "pending",
        }
        # Use data_builders.build_chore for consistent field handling
        chore_entity = eh.build_chore(chore_data)
        coordinator._data["chores"][chore_id] = chore_entity
        assigned_names = ", ".join(chore_info.get("assigned_to", []))
        print(f"  ✓ {chore_info['name']} → {assigned_names}")  # noqa: T201

    # Create rewards
    print("\n🎁 Loading rewards...")  # noqa: T201
    for reward_info in scenario.get("rewards", []):
        reward_id = str(uuid.uuid4())
        reward_data = {
            "internal_id": reward_id,
            "name": reward_info["name"],
            "cost": reward_info.get("cost", 50),
            "description": "",
            "labels": [],
            "icon": reward_info.get("icon", "mdi:gift"),
        }
        coordinator._create_reward(reward_id, reward_data)
        print(f"  ✓ {reward_info['name']} ({reward_info.get('cost', 50)} points)")  # noqa: T201

    # Create bonuses
    print("\n✨ Loading bonuses...")  # noqa: T201
    for bonus_info in scenario.get("bonuses", []):
        bonus_id = str(uuid.uuid4())
        bonus_data = {
            "internal_id": bonus_id,
            "name": bonus_info["name"],
            "points": bonus_info.get("points", 10),
            "description": bonus_info.get("description", ""),
            "icon": bonus_info.get("icon", "mdi:plus-circle"),
            "assigned_kids": list(kid_name_to_id.values()),
        }
        coordinator._create_bonus(bonus_id, bonus_data)
        print(f"  ✓ {bonus_info['name']} ({bonus_info.get('points', 10)} points)")  # noqa: T201

    # Create penalties
    print("\n⚠️  Loading penalties...")  # noqa: T201
    for penalty_info in scenario.get("penalties", []):
        penalty_id = str(uuid.uuid4())
        penalty_data = {
            "internal_id": penalty_id,
            "name": penalty_info["name"],
            "points": penalty_info.get("points", -5),
            "description": penalty_info.get("description", ""),
            "icon": penalty_info.get("icon", "mdi:minus-circle"),
            "assigned_kids": list(kid_name_to_id.values()),
        }
        coordinator._create_penalty(penalty_id, penalty_data)
        print(f"  ✓ {penalty_info['name']} ({penalty_info.get('points', -5)} points)")  # noqa: T201

    # Persist the data
    print("\n💾 Persisting data to storage...")  # noqa: T201
    await coordinator._persist()

    # Trigger coordinator update to refresh entities
    print("🔄 Refreshing coordinator...")  # noqa: T201
    await coordinator.async_refresh()

    print("\n✅ Successfully loaded scenario data!")  # noqa: T201
    print("\n📊 Summary:")  # noqa: T201
    print(f"  👶 {len(coordinator.kids_data)} kids")  # noqa: T201
    print(f"  👨 {len(coordinator.parents_data)} parents")  # noqa: T201
    print(f"  🧹 {len(coordinator.chores_data)} chores")  # noqa: T201
    print(f"  🏆 {len(coordinator.badges_data)} badges")  # noqa: T201
    print(f"  🎁 {len(coordinator.rewards_data)} rewards")  # noqa: T201
    print(f"  ✨ {len(coordinator.bonuses_data)} bonuses")  # noqa: T201
    print(f"  ⚠️  {len(coordinator.penalties_data)} penalties")  # noqa: T201
    print("\n🎉 Data is now live in Home Assistant!")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(load_scenario_to_running_instance())
