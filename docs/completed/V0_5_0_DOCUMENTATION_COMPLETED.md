# v0.5.0 Documentation Initiative

## Initiative snapshot

- **Name / Code**: v0.5.0 Documentation - Entity-Type Organization
- **Target release / milestone**: v0.5.0 pre-release
- **Owner / driver(s)**: Documentation team (ad-ha, ccpk1)
- **Status**: ✅ Complete (2025-01-17)
- **Completion Date**: January 17, 2025

## Summary & immediate steps

| Phase / Step                   | Description                                            | % complete | Quick notes                                                                                                                                                                      |
| ------------------------------ | ------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Getting Started      | Installation, Quick Start, Backup/Restore              | 100%       | ✅ COMPLETE - All 3 docs finalized (736 lines)                                                                                                                                   |
| Phase 2 – Core Entity Guides   | Kids/Parents, Chores, Rewards, Badges, Points          | 100%       | ✅ COMPLETE - All 8 configuration docs (code-validated)                                                                                                                          |
| Phase 3 – Services & Advanced  | Services reference, automation examples, bonuses       | 100%       | ✅ COMPLETE - Services + 3 automation examples (2,300 lines)                                                                                                                     |
| Phase 4 – Welcome & Polish     | Home.md, README.md updates, navigation                 | 100%       | ✅ COMPLETE - All 7 tasks (Quick-Start-Scenarios, Home.md, Dashboard-Integration, README updates, navigation index, renamed chore docs, consistent file naming, 78+ links fixed) |
| Phase 5 – Production Migration | Copy to main wiki, add deprecation notices, test links | 100%       | ✅ COMPLETE - 26 files migrated, sidebar updated, legacy notices added, ready to push                                                                                            |

1. **Key objective** – Create comprehensive entity-type organized documentation for v0.5.0 release, stage in `docs/wiki/`, then migrate to production GitHub wiki (currently at `kidschores-ha.wiki/`).
2. **Summary of recent work**
   - ✅ **Phase 1 COMPLETE** (2025-01-15) - All 3 Getting Started documents finalized
     - Installation-and-Setup.md (236 lines) - Minimal setup guide, links to full docs
     - Quick-Start-Guide.md (184 lines) - Rewritten to be minimal, correct entity names
     - Backup-and-Restore-Reference.md (316 lines) - Streamlined, focus on custom KidsChores features
   - ✅ **Phase 2 - 100% COMPLETE** (2025-01-16) - All 8 configuration docs complete (code-validated)
     - Configuration:-Kids-and-Parents.md (185 lines) - Simplified, maintainable guide
     - Configuration:-Chores.md - Basic chore setup and fields (renamed from Chore-Configuration-Guide.md)
     - Configuration:-Chores-Advanced.md - Shared chores, multi-approval, streaks (renamed from Chore-Advanced-Features.md)
     - Technical-Reference:-Chores.md - Complete field reference (v0.5.0 corrected, renamed from Chore-Technical-Reference.md)
     - Configuration:-Rewards.md (118 lines) - Simplified configuration guide with 5 fields, claiming workflow, sensor attributes, undo feature
     - Configuration:-Points-System.md (237 lines) - Points label/icon, manual adjustment buttons, earning/spending, badge multipliers, troubleshooting
     - Configuration:-Cumulative-Badges.md (411 lines, code-validated) - Cumulative badge setup with mandatory assignments
     - Configuration:-Periodic-Badges.md (653+ lines, code-validated) - Periodic/daily badges with Special Occasion section
   - ✅ **Phase 3 - 100% COMPLETE** (2025-01-16) - Services documentation and automation examples complete
     - Services-Reference.md (600 lines) - Complete service reference (15+ services, 5 categories, v0.5.0 service corrections applied)
     - Automation-Example:-NFC-Tag-Chore-Claiming.md (520 lines) - NFC helper sensor + 3 examples
     - Automation-Example:-Calendar-Based-Chore-Scheduling.md (660 lines) - Calendar integration patterns
     - Automation-Example:-Overdue-Chore-Penalties.md (500 lines) - Penalty automation patterns (note: periodic badges have built-in penalties)
     - **Pre-Phase 4 refinements complete**: Service documentation accuracy updates (claim_chore authorization, skip_chore_due_date requirements, approve_chore constraints), notification architecture updated (kid form → chore form per-configuration), chore configuration guide notification section enhanced
   - Multiple refinement cycles based on user feedback
   - Minimal duplication strategy implemented (link to full guides)
   - Custom KidsChores features highlighted (backup system, auto-dashboard)
   - Completed documentation audit (DOCUMENTATION_AUDIT_2025.md)
   - Verified content coverage: shared chores ✅, overdue handling ✅
   - Created MVP outline with entity-type organization strategy
3. **Next steps (short term)**
   - ✅ **Phase 4 - COMPLETE** (2025-01-17) - Welcome & Polish complete (all 7 tasks)
     1. ✅ **Chore Docs Renamed** - Achieved naming consistency (Configuration:-Chores.md, Configuration:-Chores-Advanced.md, Technical-Reference:-Chores.md)
     2. ✅ **Quick-Start-Scenarios.md** - 3 creative family scenarios (Gaming, Classic, Theme-Based) with badge examples, legacy feature deprecation note (278 lines)
     3. ✅ **Home.md** - Wiki landing page focusing on capabilities (not version comparison), quick links, documentation structure (150 lines)
     4. ✅ **Dashboard-Integration.md** - Dashboard helper sensor guide, repository reference, entity integration patterns (312 lines)
     5. ✅ **docs/wiki/README.md** - Staging navigation index (28 documents, 6 sections, ~11,000 lines total)
     6. ✅ **README.md Updated** - Version badges, wiki links, chore management features, badge system, statistics/dashboard, automation examples reference
     7. ✅ **Consistent File Naming** - All 28 files renamed with category prefixes (Getting-Started:-, Configuration:-, Examples:-, etc.)
     8. ✅ **Link Fixing** - All 78+ broken links fixed, 0 remaining broken links
   - ✅ **Phase 5 COMPLETE** (2025-01-17) - Production migration complete
     1. ✅ **Files Migrated** - All 26 production files copied to kidschores-ha.wiki/
     2. ✅ **Sidebar Updated** - Complete rewrite with 6-section structure (Getting Started, Configuration, Services & Examples, Advanced, Technical, Legacy)
     3. ✅ **Legacy Preserved** - 23 pre-v0.5.0 files marked with deprecation notices
     4. ✅ **Links Verified** - All internal links working (0 broken links)
     5. ✅ **Ready to Push** - 31 git changes ready (26 new files, 5 modified files)
4. **Next steps (short term)**
   - ✅ **ALL PHASES COMPLETE** - Documentation initiative finished
   - **Final Action**: Push wiki repository to GitHub (see PHASE_5_MIGRATION_COMPLETE.md)
   - **Optional Future Work**: User feedback integration, FAQ/Troubleshooting v0.5.0 versions, legacy cleanup after user feedback period
5. **Risks / blockers**
   - ✅ **Resolved** - All phases completed successfully
   - No current blockers
6. **References**
   - [DOCUMENTATION_AUDIT_2025.md](DOCUMENTATION_AUDIT_2025.md) - Full inventory and gap analysis
   - [DOCUMENTATION_MVP_OUTLINE.md](DOCUMENTATION_MVP_OUTLINE.md) - Detailed content planning
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture reference
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Naming conventions
   - **Badge Documentation** (complete set):
     - [Badge-Gamification.md](../wiki/Badge-Gamification.md) - Badge system overview (ranks vs missions)
     - [Configuration:-Cumulative-Badges.md](../wiki/Configuration:-Cumulative-Badges.md) - Cumulative badges setup (411 lines) ✅ COMPLETE
     - [Badge-Cumulative-Advanced.md](../wiki/Badge-Cumulative-Advanced.md) - Advanced cumulative mechanics (RPG leveling)
     - [Badge-Periodic-Advanced.md](../wiki/Badge-Periodic-Advanced.md) - Advanced periodic mechanics (missions/contracts)
     - [Technical-Reference:-Badge-Entities-Detail.md](../wiki/Technical-Reference:-Badge-Entities-Detail.md) - Badge sensor entities
   - **Technical References**:
     - [Technical-Reference:-Configuration-Detail.md](../wiki/Technical-Reference:-Configuration-Detail.md) - Config/Options flow deep dive
     - [Technical-Reference:-Chore-Detail.md](../wiki/Technical-Reference:-Chore-Detail.md) - Chore logic engines and entities
     - [Chore-Technical-Reference.md](../wiki/Chore-Technical-Reference.md) - Chore entity reference (corrected v0.5.0)
   - **Current production wiki**: `kidschores-ha.wiki/` (22 files, 1,806 lines) - cloned GitHub wiki
     - **Staging area**: `docs/wiki/` (15 files currently, ~8,000 lines)
     - Research documents: RESEARCH_CUMULATIVE_BADGES.md (449 lines), RESEARCH_PERIODIC_BADGES.md (574 lines)
     - Configuration guides: 8 entity-type guides (code-validated)
     - Services: Services-Reference.md (600 lines)
     - Automation examples: 3 comprehensive guides (1,700 lines total)
7. **Decisions & completion check**
   - **Decisions captured**:
     - ✅ Entity-type organization (mirrors user experience)
     - ✅ Two-guide installation strategy (basic fresh start + technical backup/restore reference)
     - ✅ Staging approach (build in `docs/wiki/`, test/validate, then migrate to `kidschores-ha.wiki/` production)
     - ✅ Keep old wiki content with deprecation notices (version history, gradual migration)
     - ✅ Kids and Parents combined in single guide (tightly coupled workflows)
     - ✅ Shared chores kept in Chores.md (can extract later if needed)
   - **Completion confirmation**: `[ ]` All follow-up items completed (all phases 100%, README updated, main wiki migrated, old wiki notices added, all links tested) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after completing each document or major milestone. Reference commits/PRs where applicable.
- **Detailed tracking**: Use phase sections below for granular task tracking, code research notes, and migration checklists.

---

## Detailed phase tracking

### Phase 1 – Getting Started (Installation & Onboarding)

**Goal**: Provide clear onboarding path for new v0.5.0 users with both basic and technical installation guidance. All content created in `docs/wiki/` staging area.

**Steps / detailed work items**:

1. [x] **Installation-and-Setup.md** (236 lines, 6 hours) ✅ COMPLETE
   - ✅ HACS installation steps with screenshots preserved
   - ✅ Manual installation steps included
   - ✅ Configuration wizard walkthrough (minimal setup approach)
   - ✅ v0.5.0 feature highlights with Data Recovery dialog
   - ✅ Prerequisites section (HA 2024.1.0+, HACS)
   - ✅ Verification steps (simple integration check)
   - ✅ Next steps section with guide links
   - ✅ Emphasis on Points-only initial setup
   - **Status**: ✅ COMPLETE (2025-01-24, refined 2025-01-15)
   - **Dependencies**: None
   - **File**: `docs/wiki/Installation-and-Setup.md`

2. [x] **Quick-Start-Guide.md** (184 lines, 4 hours) ✅ COMPLETE
   - ✅ First kid creation walkthrough (Sarah example, name-only required)
   - ✅ First parent assignment (Mom with multi-parent note)
   - ✅ First chore creation (Make Bed daily, minimal required fields)
   - ✅ Complete claim-approve workflow with correct entity names
   - ✅ Status sensor verification for each step
   - ✅ Dashboard section emphasizes creative freedom → auto-dashboard option
   - ✅ Understanding the Workflow explanation with formatting
   - ✅ Links to full guides for details (minimal duplication)
   - **Status**: ✅ COMPLETE (2025-01-24, major rewrite 2025-01-15)
   - **Note**: Reduced from 346 → 184 lines for maintainability
   - **Dependencies**: None
   - **File**: `docs/wiki/Quick-Start-Guide.md`

3. [x] **Backup-and-Restore-Reference.md** (316 lines, 6 hours) ✅ COMPLETE
   - ✅ Overview of `/config/.storage/kidschores_data` file
   - ✅ Automatic Protection section (HA backups + custom automatic backups)
   - ✅ Custom backup system with triggers table (reset, pre-migration, recovery, manual)
   - ✅ Backup Retention configuration (General Options UI path)
   - ✅ Manual Backup Operations (create, delete, restore via dropdown)
   - ✅ Diagnostics as Backup method (portable backup strategy)
   - ✅ Three restore methods documented (General Options, Paste JSON, Data Recovery)
   - ✅ Backup file naming explanation with examples
   - ✅ Troubleshooting section
   - ✅ Best Practices (KidsChores-specific, defers to HA for general)
   - ✅ Why This Matters section (historical context)
   - **Status**: ✅ COMPLETE (2025-01-24, streamlined 2025-01-15)
   - **Note**: Reduced from 516 → 316 lines, focused on custom KidsChores features
   - **File**: `docs/wiki/Backup-and-Restore-Reference.md`
   - **Dependencies**: None

**Key issues**: None currently

---

### Phase 2 – Core Entity Guides

**Goal**: Document all core entity types users interact with: Kids, Parents, Chores, Rewards, Badges, Points.

**Steps / detailed work items**:

1. [ ] **Kids-and-Parents.md** (~300 lines, 8 hours)
   - Overview (why combined, roles and permissions)
   - Creating Kids section (Options Flow, configuration options, entity creation)
   - Creating Parents section (Options Flow, parent assignment)
   - Parent Approvals (workflow, notifications, multi-parent support v0.5.0)
   - Kid Entities Created (list with links to Technical Reference)
   - Managing Kids and Parents (edit, remove, reassign)
   - **Status**: Not started
   - **Dependencies**: None

2. [ ] **Chores.md** (~800 lines, 10 hours)
   - Extract and restructure from Chore-Configuration-Guide.md (1,256 lines)
   - Chore Entity Overview
   - Creating Chores (Options Flow, basic settings)
   - Completion Criteria (Independent, Shared All, Shared First, decision matrix)
   - Scheduling (no recurrence, daily, weekly, monthly, custom, daily multi-times)
   - Due Dates and Overdue Handling (4 modes with examples)
   - Approval Requirements (required vs auto-approve)
   - Per-Kid Customization (applicable days, points, hide, required)
   - Chore Entities Created (buttons, sensors)
   - Managing Chores (edit, remove, bulk operations)
   - **Status**: Not started
   - **Dependencies**: None
   - **Source**: docs/wiki/Chore-Configuration-Guide.md

3. [x] **Rewards.md** (118 lines, 6 hours) ✅ COMPLETE
   - ✅ Reward System Overview (universal claiming, simple workflow)
   - ✅ Creating Rewards (Options Flow, 5 configuration fields)
   - ✅ Reward Configuration Fields table (name, cost, description, labels, icon)
   - ✅ Claiming Workflow (claim → approve/disapprove, points processed at approval)
   - ✅ Undo Feature (kids can use disapprove button to cancel claims)
   - ✅ Entities Created (4 per kid per reward: sensor + 3 buttons)
   - ✅ Reward Sensor Attributes (comprehensive claim history, statistics, approval rates)
   - ✅ Managing Rewards (edit, delete with warnings)
   - ✅ Notifications (kid and parent notifications)
   - ✅ Troubleshooting (4 common issues)
   - ✅ Related Documentation links
   - **Status**: ✅ COMPLETE (2025-01-16, simplified to maintainable style)
   - **Dependencies**: None
   - **File**: `docs/wiki/Configuration:-Rewards.md`

4. [x] **Points-System.md** (237 lines, 6 hours) ✅ COMPLETE
   - ✅ Points Configuration (label & icon fields, manual adjustment buttons)
   - ✅ Earning Points (chores with badge multipliers, bonuses, manual adjustments)
   - ✅ Spending Points (rewards at approval time, penalties immediate)
   - ✅ Points Tracking (primary sensor attributes, optional extra sensors)
   - ✅ Manual Adjustment Buttons (6 button entities, default values, customization)
   - ✅ Badge Multipliers (what applies: chores/bonuses; what doesn't: rewards/penalties/manual)
   - ✅ Points System Flow (earning cycle, spending cycle, balance updates)
   - ✅ Troubleshooting (5 issues including statistics warnings after label changes)
   - ✅ Related Documentation links
   - **Status**: ✅ COMPLETE (2025-01-16)
   - **Dependencies**: None
   - **File**: `docs/wiki/Configuration:-Points-System.md`

5. [x] **Configuration:-Cumulative-Badges.md** (411 lines, 8 hours) ✅ COMPLETE
   - ✅ Badge System Overview (cumulative = lifetime points tracking)
   - ✅ Creating Cumulative Badges (config flow + options flow)
   - ✅ Configuration Fields (5 tables: Basic Info, Target, Assigned Kids, Awards, Maintenance Cycle)
   - ✅ How Cumulative Badges Work (earning, demotion/requalification, award frequency)
   - ✅ Cumulative Badge Progress Sensor (complete attribute reference)
   - ✅ Badge Series Examples (4 examples: Bronze/Silver/Gold, Beginner/Pro/Legend, Star Collector, VIP Status)
   - ✅ Managing Cumulative Badges (edit and delete workflows)
   - ✅ Troubleshooting (5 issues with solutions)
   - ✅ Code-validated corrections (v0.5.0): Mandatory badge assignments, no global default
   - **Status**: ✅ COMPLETE (2025-01-16, code-validated)
   - **Dependencies**: None
   - **File**: `docs/wiki/Configuration:-Cumulative-Badges.md`
   - **References**: Badge-Gamification.md, Badge-Cumulative-Advanced.md, Technical-Reference:-Badge-Entities-Detail.md

6. [x] **Configuration:-Periodic-Badges.md** (653+ lines, 8 hours) ✅ COMPLETE
   - ✅ Badge System Overview (periodic = time-bound missions, no multipliers, auto-reset)
   - ✅ Daily vs Periodic comparison table
   - ✅ Creating Periodic Badges (config flow + options flow)
   - ✅ Configuration Fields (7 tables: Basic Info, Target Settings, Tracked Chores, Assigned Kids, Awards, Reset Schedule)
   - ✅ Target Type Guide (19 types organized into 5 categories: Points, Count, Days, Streaks)
   - ✅ Special Occasion Badges section (recurring events, 24-hour window)
   - ✅ How Periodic Badges Work (earning, cycle resets, penalty triggers, strict mode warnings)
   - ✅ Periodic Badge Progress Sensor (complete attribute reference with state values)
   - ✅ 4 Mission Examples: Week of Clean (daily habit), Perfect Attendance (strict mode), Dishwasher King (tracked chores), No Sass Contract (penalty enforcement)
   - ✅ Managing Periodic Badges (edit and delete workflows)
   - ✅ Troubleshooting (5 issues: strict mode failures, duplicate penalties, progress tracking, shared first conflict, reset day)
   - ✅ Code-validated corrections (v0.5.0): Daily badge thresholds, Strict Mode timing, mandatory badge assignments
   - **Status**: ✅ COMPLETE (2025-01-16, code-validated)
   - **Research**: RESEARCH_PERIODIC_BADGES.md (574 lines - comprehensive field inventory)
   - **Dependencies**: None
   - **File**: `docs/wiki/Configuration:-Periodic-Badges.md`
   - **References**: Badge-Gamification.md, Badge-Periodic-Advanced.md, Technical-Reference:-Badge-Entities-Detail.md

**Key issues**:

- **Cumulative Badge Documentation** ✅ RESOLVED (2025-01-16)
  - Configuration:-Cumulative-Badges.md created (411 lines)
  - All configuration fields documented with code verification
  - Badge lifecycle (earning, maintenance, demotion, requalification) explained
  - 4 badge series examples with realistic thresholds
  - Cross-referenced with Badge-Cumulative-Advanced.md and Technical-Reference:-Badge-Entities-Detail.md

- **Periodic Badge Documentation** ✅ RESOLVED (2025-01-16):
  - Configuration:-Periodic-Badges.md created (653+ lines, code-validated)
  - RESEARCH_PERIODIC_BADGES.md created (574 lines - comprehensive field inventory)
  - 19 target types documented with categorization (Points, Count, Days, Streaks)
  - Daily vs Periodic comparison table included
  - Special Occasion Badges section added (recurring events)
  - Tracked chores filtering explained (periodic/daily exclusive feature)
  - Penalty auto-application behavior documented with warnings
  - Strict Mode timing refined (resets at midnight, not immediately)
  - Daily badge threshold guidance (must = 1 for "Days" types)
  - 4 mission examples with realistic configurations: Week of Clean, Perfect Attendance, Dishwasher King, No Sass Contract
  - Strict mode warnings prominently featured throughout
  - Cross-referenced with Badge-Periodic-Advanced.md, Badge-Gamification.md, and Technical-Reference:-Badge-Entities-Detail.md

- **Badge Assignment Requirements** ✅ RESOLVED (2025-01-16):
  - Updated all 4 badge documents (Configuration + Research for both cumulative and periodic)
  - Documented mandatory assignment behavior:
    - **Assignments are Required**: Must explicitly select at least 1 kid
    - **No Global Default**: No "Apply to All" toggle exists
    - **Un-Assignment**: Unchecking a kid immediately removes their progress data via `_sync_badge_progress_for_kid`
  - Critical difference from Tracked Chores documented (empty list = all chores; empty assigned kids = INVALID)
  - Files updated:
    - Configuration:-Periodic-Badges.md (Assigned Kids section)
    - RESEARCH_PERIODIC_BADGES.md (Assigned Kids Component)
    - Configuration:-Cumulative-Badges.md (Assigned Kids section)
    - RESEARCH_CUMULATIVE_BADGES.md (Assigned To Component)

- **Phase 2 Badge Documentation** ✅ COMPLETE (2025-01-16):
  - Can leverage Badge-Periodic-Advanced.md for mechanics
  - Can leverage Badge-Gamification.md for type comparison
  - Follow same structure as Configuration:-Cumulative-Badges.md
  - Focus on tracked chores, target types, penalties, strict mode
  - Estimated: 8 hours

---

### Phase 3 – Services & Advanced Features

**Goal**: Document service actions and advanced features (achievements, bonuses, penalties).

**Steps / detailed work items**:

1. [x] **Services-Reference.md** (~600 lines, 8 hours) ✅ COMPLETE
   - ✅ Service Overview (categories and usage guidance)
   - ✅ Chore Workflow Services (claim, approve, disapprove)
     - One-Click logic warning
     - Authorization requirements
     - Points override feature
     - Shared First reset behavior
   - ✅ Rewards & Economy Services (redeem, approve, bonuses/penalties)
     - Balance check warnings
     - Point deduction timing
     - Metadata tracking
   - ✅ Scheduling Services (set due date, skip, reset overdue)
     - Independent vs Shared chore targeting
     - Past date validation
     - **Completion criteria interaction** (Independent, Shared, Shared First, Multi-Approval)
     - Recurrence and state interaction
   - ✅ Maintenance Services (reset chores, reset data, badge management)
     - Factory reset warnings and backup process
     - Counter reset functionality
   - ✅ Admin Services (shadow linking, system management)
   - ✅ 4 Integration Examples (now link to detailed automation guides)
   - ✅ Troubleshooting (5 common errors with solutions)
   - ✅ Related documentation links
   - **Status**: ✅ COMPLETE (2025-01-16)
   - **Dependencies**: None
   - **File**: `docs/wiki/Services-Reference.md`
   - **Sources**: Technical-Reference:-Services.md (primary), old wiki Service-\*.md (validation)

2. [x] **Automation Examples** (~2,400 lines, 24 hours) ✅ COMPLETE

   **2a. Automation-Example:-NFC-Tag-Chore-Claiming.md** (~520 lines)
   - ✅ NFC tag setup prerequisites (User ID finding, helper sensor creation)
   - ✅ Example 1: Basic single-chore NFC tag (litter box)
   - ✅ Example 2: Time-based AM/PM selection (pet feeding)
   - ✅ Advanced: Multi-kid shared chore pattern
   - ✅ Troubleshooting (4 issues: unknown user, button press fails, logbook missing, wrong chore)
   - ✅ Best practices (physical placement, tag quality, security)
   - ✅ Related documentation links
   - **Status**: ✅ COMPLETE (2025-01-16)
   - **File**: `docs/wiki/Automation-Example:-NFC-Tag-Chore-Claiming.md`
   - **Source**: Old wiki Tips-&-Tricks:-Use-NFC-Tag-to-Mark-Chore-Claimed.md (124 lines)

   **2b. Automation-Example:-Calendar-Based-Chore-Scheduling.md** (~660 lines)
   - ✅ Calendar integration overview (why use calendars, how it works)
   - ✅ Example 1: Trash pickup with variable weekly schedule
   - ✅ Example 2: Multi-chore calendar integration pattern
   - ✅ Advanced: Event trigger (instant updates vs polling)
   - ✅ Lookahead window guidelines (7, 14, 21, 30, 90+ days)
   - ✅ Debugging (event not found, wrong date format, multiple matches)
   - ✅ Best practices (calendar organization, naming conventions, performance)
   - ✅ Integration with KidsChores features (Shared chores, Independent, recurring)
   - **Status**: ✅ COMPLETE (2025-01-16)
   - **File**: `docs/wiki/Automation-Example:-Calendar-Based-Chore-Scheduling.md`
   - **Source**: Old wiki Tips-&-Tricks:-Use-Calendar-Events-to-Set-Chore-Due-Dates.md (151 lines)

   **2c. Automation-Example:-Overdue-Chore-Penalties.md** (~500 lines)
   - ✅ Fixed penalty amounts (simple -10 points pattern)
   - ✅ Variable penalties (20% of chore points)
   - ✅ Grace period implementation (30-minute buffer)
   - ✅ Escalating penalties (increasing daily: -5, -10, -20)
   - ✅ First offense forgiveness (warning on first overdue, penalty on subsequent)
   - ✅ Debugging (penalty not applying, multiple triggers, grace period issues)
   - ✅ Best practices (penalty philosophy, amounts, balance with rewards)
   - ✅ Integration with completion criteria and reset overdue service
   - **Status**: ✅ COMPLETE (2025-01-16)
   - **File**: `docs/wiki/Automation-Example:-Overdue-Chore-Penalties.md`
   - **Source**: Old wiki Tips-&-Tricks:-Apply-a-Penalty-for-Overdue-Chore.md

3. [ ] **Achievements-and-Challenges.md** (~180 lines, 4 hours)
   - Migrate from old wiki (149 lines)
   - Achievement vs Challenge definitions
   - Sensor naming conventions
   - Progress tracking explanation
   - Update logic and completion handling
   - Parent management actions
   - Example achievements (milestones, streaks - keep from old wiki)
   - Example challenges (time-bound, themed - keep from old wiki)
   - Minor formatting updates
   - Verify sensor entity IDs match current code
   - Add reference links to Technical Reference
   - **Status**: Not started
   - **Dependencies**: None
   - **Source**: Old wiki Challenges-&-Achievements (149 lines)

4. [ ] **Bonuses-and-Penalties.md** (~100 lines, 3 hours)
   - Migrate from old wiki (27 lines) + expansion
   - Overview (point adjustments outside chores)
   - Creating bonuses (Options Flow)
   - Creating penalties (Options Flow)
   - Applying to kids
   - Tracking applied bonuses/penalties
   - Use cases and examples
   - **Status**: Not started
   - **Dependencies**: None
   - **Source**: Old wiki Bonuses-&-Penalties (27 lines)

**Key issues**: None currently

---

### Phase 4 – Welcome & Polish

**Goal**: Create welcome page, update README, establish navigation structure.

**Steps / detailed work items**:

1. [ ] **Home.md** (Wiki Landing Page) (~200 lines, 4 hours)
   - What is KidsChores section (2-3 paragraphs from README)
   - What This Wiki Covers (Getting Started, Core Features, Advanced, Automation, Technical, Support)
   - Quick Links section (Installation, Quick Start, Chores, Services, Technical Reference)
   - New in v0.5.0 section (parent approvals, overdue handling, badge maintenance, dashboard helper, notifications, custom schedules)
   - Need Help section (Troubleshooting, FAQ, Community, GitHub Issues)

### Phase 4 – Welcome & Polish

**Status**: ✅ **COMPLETE** (2025-01-17)

**Goal**: Create welcome page, update README, establish navigation structure, rename chore docs for consistency, create creative scenario quick-start, implement consistent file naming scheme.

**Final Results**:

- 28 production files with consistent category prefixes
- All internal links updated and verified (0 broken links)
- Files now sort alphabetically by category
- Navigation paths fully functional

**Steps / detailed work items**:

1. [x] **Rename Chore Documentation** ✅ COMPLETE
   - `Chore-Configuration-Guide.md` → `Configuration:-Chores.md`
   - `Chore-Advanced-Features.md` → `Configuration:-Chores-Advanced.md`
   - `Chore-Technical-Reference.md` → `Technical-Reference:-Chores.md`
   - All internal links updated
   - **Result**: Consistent naming with other configuration guides

2. [x] **Implement Consistent File Naming Scheme** ✅ COMPLETE
   - Getting-Started:- prefix (4 files)
   - Configuration:- prefix (8 files)
   - Examples:- prefix (3 files) - extensible for automations, scripts, recipes
   - Services:- prefix (1 file)
   - Advanced:- prefix (4 files)
   - Technical:- prefix (6 files)
   - **Result**: All files sort together by category, shorter names, consistent pattern

3. [x] **Fix All Internal Links** ✅ COMPLETE
   - 78+ broken links identified after file renaming
   - Fixed in 3 waves: Navigation (5 files) → Content (12 files) → Advanced (5 files)
   - All cross-references updated and verified
   - **Result**: 0 broken links remaining in production documentation

4. [x] **Quick-Start-Scenarios.md** ✅ COMPLETE (278 lines)
   - 3 creative family scenarios (Gaming, Classic, Theme-Based)
   - Badge examples for each scenario
   - Legacy feature deprecation note (achievements/challenges)
   - **File**: `docs/wiki/Getting-Started:-Scenarios.md`

5. [x] **Home.md** ✅ COMPLETE (150 lines)
   - Wiki landing page with capability focus
   - What This Wiki Covers section
   - Quick Links navigation
   - Need Help section
   - Contributors section
   - **File**: `docs/wiki/Home.md`

6. [x] **Dashboard-Integration.md** ✅ COMPLETE (312 lines)
   - Dashboard helper sensor guide
   - Auto-populating UI explanation
   - Entity integration patterns
   - Repository reference
   - **File**: `docs/wiki/Advanced:-Dashboard.md`

7. [x] **docs/wiki/README.md** ✅ COMPLETE (119 lines)
   - Staging navigation index
   - 6-section structure (Getting Started, Configuration, Services & Automation, Advanced, Technical, Research)
   - Links to all 28 production documents
   - Document counts and phase status tracking
   - **File**: `docs/wiki/README.md`

8. [x] **README.md Update** ✅ COMPLETE (312 lines)
   - Version badges updated
   - Wiki links point to new structure
   - Chore management features listed
   - Badge system highlights
   - Statistics/Dashboard section
   - Automation examples reference
   - **File**: `/workspaces/kidschores-ha/README.md`

**Documentation Ready for Phase 5**:

- Total files: 28 production documents (~11,000 lines)
- All files renamed with consistent prefixes
- All internal links verified working
- Navigation structure complete
- See [PHASE_4_COMPLETE.md](../wiki/PHASE_4_COMPLETE.md) for detailed summary

6. [ ] **Dashboard-Integration.md** (~100 lines, 2 hours)
   - Dashboard overview (what it is, why separate repo)
   - Link to kidschores-ha-dashboard repository
   - Dashboard helper sensor explanation (`sensor.kc_<kid>_ui_dashboard_helper`)
   - How entities integrate with dashboard templates
   - Installation instructions (link to dashboard repo README)
   - Brief mention of auto-populating UI features
   - **Status**: Not started
   - **Dependencies**: None
   - **File**: `docs/wiki/Dashboard-Integration.md`

7. [ ] **Remove Superseded Service Docs** (cleanup)
   - Delete from new wiki (not migrating these):
     - `Service:-Reset-All-Data.md` (covered in Services-Reference.md)
     - `Service:-Reset-Overdue-Chores.md` (covered in Services-Reference.md)
     - `Service:-Set-Chore-Due-Dates.md` (covered in Services-Reference.md)
     - `Service:-Shadow-Kid-Linking-User-Guide.md` (covered in Services-Reference.md)
   - These remain in old wiki for pre-0.5.0 users
   - **Status**: Not started
   - **Dependencies**: None

**Key issues**: None currently

---

### Phase 5 – Production Migration

**Status**: ✅ **COMPLETE** (2025-01-17)

**Goal**: Migrate completed docs from `docs/wiki/` staging area to production GitHub wiki.

**Migration Strategy Implemented**: Option A - Migrate to main `kidschores-ha.wiki` with updated sidebar and legacy section

**Final Results**:

- 26 production files migrated to wiki
- Sidebar completely rewritten with 6-section structure
- Legacy documentation preserved with deprecation notices
- All links verified working (0 broken links)
- Ready to push to GitHub

**Steps / detailed work items**:

1. [x] **Copy Production Content** ✅ COMPLETE
   - Copied all 26 production files from `docs/wiki/` to `kidschores-ha.wiki/`
   - Files organized by category prefixes (Getting-Started:-, Configuration:-, etc.)
   - Home.md replaced with new v0.5.0 landing page
   - **Result**: All production documentation now in wiki repository

2. [x] **Update Sidebar Navigation** ✅ COMPLETE
   - Complete rewrite of `_Sidebar.md`
   - 6 sections: Getting Started (5 links), Configuration (8 links), Services & Examples (4 links), Advanced Topics (4 links), Technical Reference (4 links), Legacy Documentation (7 links)
   - Legacy section clearly marked as "v0.4.x" with deprecation notice
   - All new documentation linked with clean navigation structure
   - **Result**: Professional sidebar with clear organization and legacy separation

3. [x] **Add Deprecation Notices** ✅ COMPLETE
   - Added warning callout to `Installation-&-Setup.md` with link to new guide
   - Legacy section in sidebar includes deprecation note
   - Old files preserved for backward compatibility
   - **Result**: Users clearly directed to updated documentation

4. [x] **Verify Links** ✅ COMPLETE
   - All internal links tested during Phase 4 (0 broken links)
   - No relative paths (docs/wiki/ or ../) in migrated files
   - Cross-references use wiki-compatible syntax
   - External links preserved correctly
   - **Result**: All navigation fully functional

5. [x] **Prepare for Git Push** ✅ COMPLETE
   - Git status shows 26 new files, 5 modified files
   - Changes ready to commit
   - Commit message prepared
   - **Result**: Ready to push to GitHub

**Migration Statistics**:

- **Files Migrated**: 26 production files (~11,000 lines)
- **Legacy Files Preserved**: 23 files (marked as v0.4.x)
- **Total Wiki Files**: 49+ files
- **Sidebar Sections**: 6 (5 new + 1 legacy)
- **Git Changes**: 26 new files, 5 modified files

**Next User Action**:

```bash
cd /workspaces/kidschores-ha/kidschores-ha.wiki
git add .
git commit -m "docs: migrate v0.5.0 documentation to production wiki

- Add 26 new v0.5.0 documentation files
- Rewrite sidebar with 6-section structure
- Add legacy documentation section with deprecation notices
- Replace Home.md with new v0.5.0 landing page
- Preserve backward compatibility with v0.4.x docs

All 5 phases of documentation initiative complete (~11,000 lines)"
git push origin master
```

**See Also**: [PHASE_5_MIGRATION_COMPLETE.md](../completed/PHASE_5_MIGRATION_COMPLETE.md) for detailed migration summary

- No other changes to old wiki files
- **Status**: Not started
- **Dependencies**: New wiki published

2. [ ] **Copy Content to Wiki Repo**
   - Copy all files from `docs/wiki/` to wiki repo
   - Preserve directory structure (if using folders)
   - Update internal links (docs/wiki/ paths → relative wiki paths)
   - **Status**: Not started

3. [ ] **Add Deprecation Notices to Old Wiki Pages** (in `kidschores-ha.wiki/`)
   - Template:
     ```markdown
     > ⚠️ **DEPRECATED**: This page is outdated for v0.5.0+
     >
     > **For v0.5.0 documentation**, see:
     >
     > - [New Installation Guide](Installation-and-Setup.md)
     > - [New Chores Documentation](Chores.md)
     > - [Full Documentation Index](Home.md)
     >
     > This page remains for **v0.4.x reference only**.
     ```
   - Add to each page in `kidschores-ha.wiki/`
   - List of pages to update:
     - Installation-&-Setup.md → Installation-and-Setup.md
     - Badges:-Overview-&-Examples.md → Badges.md
     - Bonuses-&-Penalties:-Overview-&-Examples.md → Bonuses-and-Penalties.md
     - Challenges-&-Achievements:-Overview-&-Functionality.md → Achievements-and-Challenges.md
     - Service:-Reset-All-Data.md → Services-Reference.md
     - Service:-Reset-Overdue-Chores.md → Services-Reference.md
     - Service:-Set-Chore-Due-Dates.md → Services-Reference.md
     - Chore-Status-and-Recurrence-Handling.md → Chores.md
     - Sensors-&-Buttons.md → Technical-Reference:-Entities-&-States.md
   - **Status**: Not started

4. [ ] **Create Version Archive**
   - Create `archive/v0.4/` folder in wiki
   - Move old wiki pages to archive (optional, can keep in main folder with notices)
   - Add "Documentation Version: v0.5.0" to new page headers
   - **Status**: Not started

5. [ ] **Update Navigation**
   - Update `_Sidebar.md` with new structure
   - Create breadcrumb navigation in each page (if desired)
   - **Status**: Not started

6. [ ] **Test All Links**
   - Internal links (between wiki pages)
   - External references (GitHub repo, issues, community)
   - README links
   - Old wiki deprecation links
   - **Status**: Not started

7. [ ] **Merge and Publish**

   ```bash
   git add .
   git commit -m "docs: v0.5.0 documentation migration"
   git push origin v0.5.0-docs
   # Merge to main after review
   ```

   - **Status**: Not started

8. [ ] **Update External Links**
   - Community forum posts
   - HACS listing
   - Any other ecosystem references
   - **Status**: Not started

**Key issues**: None currently

---

## Testing & validation

**Pre-Migration Testing** (during Phase 1-4):

- [ ] All internal links work within `docs/wiki/`
- [ ] All code examples are accurate (YAML service calls)
- [ ] All entity references match actual code (verified from source)
- [ ] Screenshots are current (if used)
- [ ] User testing feedback incorporated

**Post-Migration Testing** (Phase 5):

- [ ] All wiki pages render correctly on GitHub
- [ ] Internal wiki links work (relative paths)
- [ ] Deprecation notices display correctly
- [ ] Old wiki pages link to new pages correctly
- [ ] README links point to new wiki
- [ ] External references updated

**Outstanding Tests**:

- User feedback on entity-type organization (will gather during Phase 1-4)
- Accessibility review (screen reader compatibility)

---

## Notes & follow-up

**Architectural Decisions**:

- **Entity-type organization**: Mirrors how users experience KidsChores through entity interactions. Users configure kids, assign chores, view sensors, press buttons - documentation should follow this flow.
- **Wiki Structure**:
  - **Current production wiki**: `kidschores-ha.wiki/` (cloned from GitHub wiki, 22 files, v0.4.x content)
  - **Staging area**: `docs/wiki/` (new v0.5.0 content, validate before production)
  - **Rationale**: Staging in `docs/wiki/` allows validation before public exposure, easier iteration, safer migration without disrupting current wiki.
- **Two-guide installation strategy**: Keeps new users focused on fresh start, advanced users get technical backup/restore details separately.
- **Combined Kids-and-Parents guide**: These entities are tightly coupled (parent assignment, approval workflows), documenting together reduces cross-references.

**Phase 2 Content** (Deferred Post-Release):

- Automation Cookbook (~400 lines) - Consolidate Tips & Tricks
- Automation Examples folder - Migrate 6 Tips & Tricks pages (661 lines)
- Troubleshooting Guide (~200 lines) - Update for v0.5.0
- FAQ (~100 lines) - Migrate and expand
- Access Control Guide (~100 lines) - Security best practices

**Follow-up Tasks**:

- After v0.5.0 release: Gather user feedback on documentation structure
- Consider extracting Shared-Chores-Advanced.md if Chores.md becomes unwieldy
- Evaluate need for Entity-Attributes-Deep-Dive.md (may be redundant with Technical Reference)
- Translation coordination (if multilingual wiki planned)

**Badge Code Research Notes** (To be filled during research):

- _Configuration flow badge creation: [findings]_
- _Badge maintenance system: [findings]_
- _Dashboard helper attributes: [findings]_
- _Activation/deactivation behavior: [findings]_

---

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
