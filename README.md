![Status](https://img.shields.io/badge/Status-Pre--Alpha-red)
![Build](https://img.shields.io/badge/Build-Unstable-orange)

<br><br><br><br><br><br>

> [!WARNING]
> **UNDER ACTIVE DEVELOPMENT**
> This repository is currently in a pre-alpha state and is being refactored from the original [KidsChores] integration.
> Breaking changes are pushed directly to `main` without notice. Please do not install this in a production Home Assistant environment yet.

## <br><br><br><br><br><br>

[![Quality Scale: Platinum](https://img.shields.io/badge/Quality%20Scale-Platinum-platinum.svg)](https://github.com/ccpk1/choreops)
[![Crowdin](https://badges.crowdin.net/choreops-translations/localized.svg)](https://crowdin.com/project/choreops-translations)
[![License](https://img.shields.io/github/license/ccpk1/choreops)](https://github.com/ccpk1/choreops/blob/main/LICENSE)<br>
[![HACS Custom](https://img.shields.io/badge/HACS%20Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Validate](https://github.com/ccpk1/choreops/actions/workflows/validate.yaml/badge.svg)](https://github.com/ccpk1/choreops/actions/workflows/validate.yaml)
[![Hassfest](https://github.com/ccpk1/choreops/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/ccpk1/choreops/actions/workflows/hassfest.yaml)
[![Lint Validation](https://github.com/ccpk1/choreops/actions/workflows/lint-validation.yaml/badge.svg)](https://github.com/ccpk1/choreops/actions/workflows/lint-validation.yaml)<br>
[![GitHub Release](https://img.shields.io/github/v/release/ccpk1/choreops?include_prereleases)](https://github.com/ccpk1/choreops/releases)
[![Latest Release Downloads](https://img.shields.io/github/downloads/ccpk1/choreops/latest/total?label=Latest%20Release%20Downloads)](https://github.com/ccpk1/choreops/releases)
[![All Release Downloads](https://img.shields.io/github/downloads/ccpk1/choreops/total?label=All%20Release%20Downloads)](https://github.com/ccpk1/choreops/releases)<br>
[![GitHub Stars](https://img.shields.io/github/stars/ccpk1/choreops?style=social)](https://github.com/ccpk1/choreops/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/ccpk1/choreops)](https://github.com/ccpk1/choreops/issues)

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

> [!NOTE]
> **Attribution & Legacy**<br>
> ChoreOps is the official evolution of the **KidsChores** integration. While the original project is now deprecated, its foundation lives on in ChoreOps, designed to serve the entire Home Assistant community by expanding the scope from just "kids" to the whole household.
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
- **Multi-instance support**: run multiple ChoreOps entries in the same Home Assistant instance

## Reference Documentation

- 📚 Wiki Home: [ChoreOps Wiki](https://github.com/ccpk1/choreops/wiki)
- 🚀 Getting Started: [Installation](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Installation) · [Quick Start](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Quick-Start) · [Scenarios](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Scenarios) · [Migration from KidsChores](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Migration-from-KidsChores)
- ⚙️ Configuration: [Users](https://github.com/ccpk1/choreops/wiki/Configuration:-Users) · [Chores](https://github.com/ccpk1/choreops/wiki/Configuration:-Chores)
- 🏅 Gamification: [Points](https://github.com/ccpk1/choreops/wiki/Configuration:-Points) · [Rewards](https://github.com/ccpk1/choreops/wiki/Configuration:-Rewards) · [Badges Overview](https://github.com/ccpk1/choreops/wiki/Configuration:-Badges-Overview) · [Achievements](https://github.com/ccpk1/choreops/wiki/Configuration:-Achievements) · [Challenges](https://github.com/ccpk1/choreops/wiki/Configuration:-Challenges)
- 🔧 Operations: [Services Reference](https://github.com/ccpk1/choreops/wiki/Services:-Reference) · [Advanced Dashboard](https://github.com/ccpk1/choreops/wiki/Advanced:-Dashboard) · [Advanced Access Control](https://github.com/ccpk1/choreops/wiki/Advanced:-Access-Control)
- 🧪 Technical: [Entities & States](https://github.com/ccpk1/choreops/wiki/Technical:-Entities-States) · [Dashboard Generation](https://github.com/ccpk1/choreops/wiki/Technical:-Dashboard-Generation) · [Troubleshooting](https://github.com/ccpk1/choreops/wiki/Technical:-Troubleshooting) · [FAQ](<https://github.com/ccpk1/choreops/wiki/Frequently-Asked-Questions-(FAQ)>)

## Quick installation

### One-click HACS install (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ccpk1&repository=choreops&category=integration)

Prefer the guided steps? See the full [Wiki installation guide](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Installation).

### Manual HACS setup

1. Ensure HACS is installed ([HACS setup guide](https://hacs.xyz/docs/installation/manual)).
2. In Home Assistant, open **HACS → Integrations → Custom repositories**.
3. Add `https://github.com/ccpk1/choreops` as an **Integration** repository.
4. Search for **ChoreOps**, install it, then restart Home Assistant.
5. Open **Settings → Devices & Services → Add Integration**, then configure **ChoreOps**.

## Community and contribution

- 💬 Community discussion: [GitHub Discussions](https://github.com/ccpk1/choreops/discussions)
- 🛠️ Issues and feature requests: [GitHub Issues](https://github.com/ccpk1/choreops/issues)
- 🔀 Contribute: [Pull requests](https://github.com/ccpk1/choreops/pulls)

### Use issues vs discussions

- Use **Issues** for confirmed bugs, actionable feature requests, and tracked implementation work.
- Use **Discussions** for setup help, usage questions, idea exploration, and general feedback.
- If a discussion identifies a reproducible bug or concrete feature request, open a linked issue.

## Credits & Contributors

- [@ccpk1](https://github.com/ccpk1) — Project Lead & Developer
- [@ad-ha](https://github.com/ad-ha) — Original Creator of KidsChores

## License

This project is licensed under the [GPL-3.0 license](LICENSE).
See [NOTICE](NOTICE) for project attribution and fork/modification notice.

## Disclaimer

This project is not affiliated with or endorsed by any official entity. Use at your own risk.
