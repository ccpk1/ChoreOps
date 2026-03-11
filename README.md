[![Quality Scale: Platinum](https://img.shields.io/badge/Quality%20Scale-platinum-platinum.svg)](https://github.com/ccpk1/choreops)
[![Quality Gates](https://img.shields.io/github/actions/workflow/status/ccpk1/choreops/lint-validation.yaml?branch=main&label=Quality%20Gates)](https://github.com/ccpk1/choreops/actions/workflows/lint-validation.yaml)
[![Crowdin](https://badges.crowdin.net/choreops-translations/localized.svg)](https://crowdin.com/project/choreops-translations)
[![License](https://img.shields.io/static/v1?label=License&message=GPL-3.0&color=1E88E5&labelColor=555)](https://github.com/ccpk1/choreops/blob/main/LICENSE) [![HACS Custom](https://img.shields.io/static/v1?label=HACS&message=custom&color=1E88E5&labelColor=555)](https://github.com/custom-components/hacs) <br>
[![Version](https://img.shields.io/github/v/release/ccpk1/choreops?include_prereleases&label=Version&color=1E88E5)](https://github.com/ccpk1/choreops/releases)
[![Latest DL](https://img.shields.io/github/downloads-pre/ccpk1/choreops/latest/total?label=Latest%20DL&color=1E88E5)](https://github.com/ccpk1/choreops/releases)
[![Total DL](https://img.shields.io/github/downloads-pre/ccpk1/choreops/total?label=Total%20DL&color=1E88E5)](https://github.com/ccpk1/choreops/releases)<br>

<p align="center">
  <img src="https://raw.githubusercontent.com/ccpk1/choreops/main/custom_components/choreops/brand/logo.png" alt="ChoreOps - Level Up your Household Tasks" width="500">
</p>

---

### ChoreOps helps keep your home running smoothly... _Level Up your Household Tasks_

Whether you are staying on top of a busy lifestyle, sharing duties with a housemate, or trying to motivate your kids, ChoreOps fills a gap in the ecosystem. Users often need something more powerful than a simple to-do list, but more integrated and private than external cloud services.

Born from the popular _KidsChores_ integration, ChoreOps evolves that foundation into a sophisticated **Household Operations Platform**. It recognizes that while the high-quality gamification at its core is a powerful motivator for many, others just want the trash taken out on time.

---

### ❤️ Support the Project

If ChoreOps helps keep your household running smoothly, consider fueling its development! Your support is a token of appreciation that keeps the fire burning and prevents open-source burnout.

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/ccpk1)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/ccpk1)

---

### Run It Your Way

**Whether you need a full XP/Reward economy for the kids, or a silent "Operations Center" for housemates, ChoreOps adapts to you.**

#### **🎮 The Gamified Home**

- Lean into the native **XP, Badges, Achievements, and Streaks**. Turn household participation into an engaging loop that motivates everyone to chase high scores, level up through **Ranks** (cumulative badges), and complete **Quests** (periodic badges).

#### **⚙️ The Utility Home**

- Strip away the game layer entirely. Use the **Advanced Scheduling** and **Rotation Logic** to automate the mental load of household maintenance. Get actionable notifications for the trash, filters, and bills—without a single point or badge involved.

#### **⚖️ The Hybrid Home**

- **The best of both worlds.** Configure some profiles with full gamification to drive engagement, while keeping other profiles strictly utilitarian.<br><br>

---

> [!NOTE]
> **Attribution & Legacy**<br>
> ChoreOps is the official evolution of the **KidsChores** integration. While the original project is now deprecated, its foundation lives on in ChoreOps, designed to serve the entire Home Assistant community by expanding the scope from just "kids" to the whole household.
>
> The original creator, **@ad-ha**, remains involved with this progression and continues to inspire the project's direction. <br>
> 🔄 **Coming from KidsChores?** We have a direct migration path to move your data over. **[View the Migration Guide →](https://github.com/ccpk1/choreops/wiki/Migration)**

---

### Key capabilities

- ⚡ **Native data access**: rich state is exposed as Home Assistant sensors and actions are exposed as button entities, so you can build automations, scripts, and dashboards with standard HA tools—no lock-in custom app UI
- 🧠 **Intelligent logic**: sophisticated recurring schedules, first-come-first-served pools, per-assignee schedules, and complex rotation algorithms
- 🎨 **Easy Dashboards:** Quickly set up full featured dashboards for any user easily-no YAML required
- 🔔 **Advanced notifications**: actionable alerts with approval workflows and reminder controls
- 🎮 **Optional gamification**: robust progression systems you can enable or minimize as needed
- ⚡ **Open control**: tasks, statistics, and actions exposed as Home Assistant entities and services for full automation control
- 🌍 **Global ready**: multilingual support with 13+ languages

### Core philosophy

- **Native by Design:** No Docker, no external database, no cloud dependency—all built directly within Home Assistant.
- **Platinum Quality:** Built to Home Assistant Platinum quality standards prioritizing long-term stability and scale.
- **First-Class Application:** More than a collection of entities, it delivers the feature-rich app experience of a standalone app.
- **Gamification with Purpose:** Progression systems built as first-class capabilities, not tacked-on extras.
- **Privacy First:** Your household data remains 100% on your local instance. No external data sharing.
- **Open by Default:** Data rich entities + Service-level APIs for dashboards, scripts, and Node-RED.

### What ChoreOps can manage

- **Profiles**: flexible roles for every approver and doer in your household
- **Chores**: individual, shared, first-complete, and rotation models with advanced recurrence and overdue handling
- **Points/XP**: use any home assistant icon and any term to configure the currency in your household
- **Rewards**: claim-and-approve redemption workflows with automatic point accounting
- **Badges**: cumulative rank-style systems and periodic quest-style systems with streaks and multipliers
- **Bonuses and penalties**: transparent manual or automated adjustments
- **Challenges and achievements**: time-bound goals and milestone tracking
- **Calendar visibility**: scheduled chores and challenge windows in Home Assistant calendar contexts
- **Statistics**: daily/weekly/monthly/yearly/all-time period tracking and analytics sensors
- **Weekly activity reports**: generate detailed 7-day progress reports via service, copy as markdown, or deliver through Home Assistant notify/email services

> [!NOTE]
> In kid-facing dashboard language, ChoreOps may refer to badge families as **Ranks** and **Quests**. In Home Assistant configuration screens and technical docs, the underlying setup terms remain **Cumulative Badges** and **Periodic Badges**.

### For power users

ChoreOps ships with a functional dashboard starter experience, but it is designed to be open and extensible.

- **Rich sensor data**: granular attributes for dashboards and analytics
- **Service-level control**: automate create/claim/approve/redeem/adjust actions
- **Automation-first architecture**: integrate with scripts, automations, dashboards, voice, and Node-RED
- **Multi-instance support**: run multiple ChoreOps entries in the same Home Assistant instance

---

### Reference Documentation

- 📚 Wiki Home: [ChoreOps Wiki](https://github.com/ccpk1/choreops/wiki)
- 🚀 Getting Started: [Installation](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Installation) · [Quick Start](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Quick-Start) · [Scenarios](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Scenarios) · [Migration from KidsChores](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Migration-from-KidsChores)
- ⚙️ Configuration: [Users](https://github.com/ccpk1/choreops/wiki/Configuration:-Users) · [Chores](https://github.com/ccpk1/choreops/wiki/Configuration:-Chores)
- 🏅 Gamification: [Points](https://github.com/ccpk1/choreops/wiki/Configuration:-Points) · [Rewards](https://github.com/ccpk1/choreops/wiki/Configuration:-Rewards) · [Badges Overview](https://github.com/ccpk1/choreops/wiki/Configuration:-Badges-Overview) · [Achievements](https://github.com/ccpk1/choreops/wiki/Configuration:-Achievements) · [Challenges](https://github.com/ccpk1/choreops/wiki/Configuration:-Challenges)
- 🔧 Operations: [Services Reference](https://github.com/ccpk1/choreops/wiki/Services:-Reference) · [Weekly Activity Reports](https://github.com/ccpk1/choreops/wiki/Technical:-Weekly-Activity-Reports) · [Advanced Dashboard](https://github.com/ccpk1/choreops/wiki/Advanced:-Dashboard) · [Advanced Access Control](https://github.com/ccpk1/choreops/wiki/Advanced:-Access-Control)
- 🧪 Technical: [Entities & States](https://github.com/ccpk1/choreops/wiki/Technical:-Entities-States) · [Dashboard Generation](https://github.com/ccpk1/choreops/wiki/Technical:-Dashboard-Generation) · [Troubleshooting](https://github.com/ccpk1/choreops/wiki/Technical:-Troubleshooting) · [FAQ](<https://github.com/ccpk1/choreops/wiki/Frequently-Asked-Questions-(FAQ)>)

---

### Quick installation

#### One-click HACS install (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ccpk1&repository=choreops&category=integration)

Prefer the guided steps? See the full [Wiki installation guide](https://github.com/ccpk1/choreops/wiki/Getting-Started:-Installation).

#### Manual HACS setup

1. Ensure HACS is installed ([HACS setup guide](https://hacs.xyz/docs/installation/manual)).
2. In Home Assistant, open **HACS → Integrations → Custom repositories**.
3. Add `https://github.com/ccpk1/choreops` as an **Integration** repository.
4. Search for **ChoreOps**, install it, then restart Home Assistant.
5. Open **Settings → Devices & Services → Add Integration**, then configure **ChoreOps**.

---

### Community and contribution

- 💬 Community discussion: [GitHub Discussions](https://github.com/ccpk1/choreops/discussions)
- 🛠️ Issues and feature requests: [GitHub Issues](https://github.com/ccpk1/choreops/issues)
- 🔀 Contribute: [Pull requests](https://github.com/ccpk1/choreops/pulls)

---

### Companion repository

- Dashboard templates and registry assets are maintained in [ChoreOps Dashboards](https://github.com/ccpk1/choreops-dashboards).
- The integration repository remains the primary product repository for installation, runtime behavior, and user support.

---

### Use issues vs discussions

- Use **Issues** for confirmed bugs, actionable feature requests, and tracked implementation work.
- Use **Discussions** for setup help, usage questions, idea exploration, and general feedback.
- If a discussion identifies a reproducible bug or concrete feature request, open a linked issue.

---

### Credits & Contributors

- [@ccpk1](https://github.com/ccpk1) — Project Lead & Developer
- [@ad-ha](https://github.com/ad-ha) — Original Creator of KidsChores

---

### License

This project is licensed under the [GPL-3.0 license](LICENSE).
See [NOTICE](NOTICE) for project attribution and fork/modification notice.

---

### Disclaimer

This project is not affiliated with or endorsed by any official entity. Use at your own risk.

---
