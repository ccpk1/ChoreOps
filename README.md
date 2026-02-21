![Status](https://img.shields.io/badge/Status-Pre--Alpha-red)
![Build](https://img.shields.io/badge/Build-Unstable-orange)

<br><br><br><br><br><br>

> [!WARNING]
> **UNDER ACTIVE DEVELOPMENT**
> This repository is currently in a pre-alpha state and is being refactored from the original [KidsChores] integration.
> Breaking changes are pushed directly to `main` without notice. Please do not install this in a production Home Assistant environment yet.

## <br><br><br><br><br><br>

TODO: All links need updated and confirmed, as well as consider any additional logos etc.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Quality Scale: Platinum](https://img.shields.io/badge/Quality%20Scale-Platinum-platinum.svg)](https://github.com/ccpk1/choreops)
![GitHub Release](https://img.shields.io/github/v/release/ccpk1/choreops?include_prereleases)
![GitHub Downloads (latest)](https://img.shields.io/github/downloads/ccpk1/choreops/latest/total)

[![Validate](https://github.com/ccpk1/choreops/actions/workflows/validate.yaml/badge.svg)](https://github.com/ccpk1/choreops/actions/workflows/validate.yaml)

<p align="center">
  <img src="logo.png" alt="ChoreOps - Level Up your Household Tasks" width="640">
</p>

<p align="center">
  <a href="https://buymeacoffee.com/ccpk1" target="_blank">
    <img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174">
  </a>
</p>

**ChoreOps helps keep your home running smoothly... _Level Up your Household Tasks_**

Whether you are staying on top of a busy lifestyle, sharing duties with a housemate, or trying to motivate your kids, ChoreOps fills a gap in the ecosystem. Users needed something more powerful than a simple to-do list, but more integrated and private than external cloud services.

Born from the popular _KidsChores_ integration, ChoreOps evolves that foundation into a sophisticated **Household Operations Platform**. It recognizes that while the high-quality gamification at its core is a powerful motivator for many, others just want the trash taken out on time.

## Run It Your Way

**Whether you need a full XP/Reward economy for the kids, or a silent "Operations Center" for housemates, ChoreOps adapts to you.**

### 🎮 The Gamified Home

Lean into the native **XP, Badges, Achievements, and Streaks**. Turn household participation into an engaging loop that motivates everyone to chase high scores and earn rewards.

### ⚙️ The Utility Home

Strip away the game layer entirely. Use the **Enterprise-Grade Scheduling** and **Rotation Logic** to automate the mental load of household maintenance. Get actionable notifications for the trash, filters, and bills—without a single point or badge involved.

### ⚖️ The Hybrid Home

**The best of both worlds.** Configure some profiles with full gamification to drive engagement, while keeping other profiles strictly utilitarian.

---

> **Attribution & Legacy**<br>
> **Intentional terminology exception:** This README intentionally retains select `KidsChores` references for migration guidance and legacy attribution under the rebrand policy.
>
> ChoreOps is the official evolution of the **KidsChores** integration. While the original project is now deprecated, its concepts and features grew into this new system to better serve the entire Home Assistant community—expanding the scope beyond just "kids" to the whole household.
>
> The original creator, **@ad-ha**, remains involved with this progression and continues to inspire the project's direction.<br>
> 🔄 **Coming from KidsChores?** We have a direct migration path to move your data over. **[View the Migration Guide →](https://github.com/ccpk1/choreops/wiki/Migration)**

---

## Key capabilities

- ⚡ **Native data access**: rich state is exposed as Home Assistant sensors and actions are exposed as button entities, so you can build automations, scripts, and dashboards with standard HA tools—no lock-in custom app UI
- 🧠 **Intelligent logic**: sophisticated recurring schedules, first-come-first-served pools, per-assignee schedules, and complex rotation algorithms
- 🎨 **Easy Dashboards:** Quickly set up full featured dashboards for any user easily-no YAML required
- 🔔 **Advanced notifications**: actionable alerts with approval workflows and reminder controls
- 🎮 **Optional gamification**: robust progression systems you can enable or minimize as needed
- ⚡ **Open control**: tasks and members exposed as Home Assistant entities and services for full automation control
- 🌍 **Global ready**: multilingual support with 13+ language packs out of the box

## Core philosophy

- **Native by Design:** No Docker sidecar, no external database, no cloud dependency.
- **Gamification with Purpose:** Progression systems built as first-class capabilities, not tacked-on extras.
- **Privacy First:** Your household data remains 100% on your local instance. No external data sharing.
- **Open by Default:** Rich entities + Service-level APIs for dashboards, scripts, and Node-RED.

## What ChoreOps can manage

- **Profiles**: flexible roles for every approver and doer in your household
- **Chores**: individual, shared, first-complete, and rotation models with advanced recurrence and overdue handling
- **Points/XP**: use any home assistant icon and any term to configure the currency in your household
- **Rewards**: claim-and-approve redemption workflows with automatic point accounting
- **Badges**: cumulative and periodic systems with streaks and multipliers
- **Bonuses and penalties**: transparent manual or automated adjustments
- **Challenges and achievements**: time-bound goals and milestone tracking
- **Calendar visibility**: scheduled chores and challenge windows in Home Assistant calendar contexts
- **Statistics**: daily/weekly/monthly/yearly/all-time period tracking and analytics sensors

## For power users

ChoreOps ships with a functional dashboard starter experience, but it is designed to be open and extensible.

- **Rich sensor data**: granular attributes for dashboards and analytics
- **Service-level control**: automate create/claim/approve/redeem/adjust actions
- **Automation-first architecture**: integrate with scripts, automations, dashboards, voice, and Node-RED

## Hard-fork service field migration

ChoreOps hard-fork runtime contracts use role-based request fields in services and
automation payloads.

- `kid_name` → `assignee_name`
- `parent_name` → `approver_name`

Runtime compatibility aliases are not supported for these fields.

Before:

```yaml
action: choreops.approve_chore
data:
  parent_name: "Mom"
  kid_name: "Henry"
  chore_name: "Brush teeth PM"
```

After:

```yaml
action: choreops.approve_chore
data:
  approver_name: "Mom"
  assignee_name: "Henry"
  chore_name: "Brush teeth PM"
```

## Migration verification checklist (release hardening)

For upgrade validation and rollback confidence:

- Confirm migration summary logs include structured counts for users, linked merges,
  standalone parent creations, collisions, and remap totals/additions.
- Run migration-path tests before release sign-off:
  - `python -m pytest tests/test_migration_hardening.py tests/test_config_flow_use_existing.py -v --tb=line`
- Validate rollback by creating a backup before upgrade and restoring it after test migration.

## Reference Documentation

TODO: Add Wiki once live

## Quick installation

### Via HACS (recommended)

1. Ensure HACS is installed ([HACS setup guide](https://hacs.xyz/docs/installation/manual)).
2. In Home Assistant, open **HACS → Integrations → Custom repositories**.
3. Add `https://github.com/ccpk1/choreops` as an **Integration** repository.
4. Search for **ChoreOps**, install it, then restart Home Assistant.
5. Open **Settings → Devices & Services → Add Integration**, then configure **ChoreOps**.

## Community and contribution

- 💬 Community discussion (legacy thread during transition): [Home Assistant forum thread](https://community.home-assistant.io/t/kidschores-family-chore-management-integration)
- 🛠️ Issues and feature requests: [GitHub Issues](https://github.com/ccpk1/choreops/issues)
- 🔀 Contribute: [Pull requests](https://github.com/ccpk1/choreops/pulls)

## Credits & Contributors

- [@ccpk1](https://github.com/ccpk1) — Project Lead & Developer
- [@ad-ha](https://github.com/ad-ha) — Original Creator (KidsChores)

## License

This project is licensed under the [GPL-3.0 license](LICENSE).

## Disclaimer

This project is not affiliated with or endorsed by any official entity. Use at your own risk.
