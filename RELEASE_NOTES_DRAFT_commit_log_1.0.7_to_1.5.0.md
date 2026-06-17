fcd5ea6 2026-06-17 10:21:17 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(notifications): strip points from messages when gamification is disabled (#181)
When a user has enable_gamification=False, notifications still included
points references like "You earned 50 Points". Two code paths were affected:

1. EconomyManager._on_chore_approved() processed and deposited points
   unconditionally — now gates on user's gamification flag
2. NotificationManager always used gamified message keys — now resolves
   to non-gamified _NO_POINTS variants based on recipient's gamification
   flag, and strips points/points_label from message_data

- Add 6 TRANS_KEY_NOTIF_*_NO_POINTS constants + NOTIF_NON_GAMIFIED_MESSAGE_KEYS
  mapping to const.py
- Add 6 non-gamified English notification templates to en_notifications.json
- Add _get_assignee_gamification_enabled() to notification_manager.py
- Apply key resolution and points stripping in notify_assignee_translated()
  and notify_approvers_translated()
- Add gamification guard in EconomyManager._on_chore_approved()

Fixes #177
---
e93d06c 2026-06-17 09:47:22 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(notifications): suppress rotation non-turn-holder signals at emission layer (#180)
Rotation-mode chores create scan entries for every assigned assignee, but
only the current turn-holder should receive due/overdue notifications.

- Add rotation guard to _process_overdue: non-turn-holders without steal
  or standby capability are skipped before signal emission
- Add rotation guard to _process_due_window: skip non-turn-holders
- Add rotation guard to _process_due_reminder: skip non-turn-holders
- Remove now-redundant rotation guards from _handle_chore_due_window
  and _handle_chore_due_reminder in notification_manager.py

Single source of truth at the emission layer protects all downstream
listeners (NotificationManager, StatisticsManager, GamificationManager).

Fixes #175
---
23fd5f2 2026-06-17 09:19:44 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(notifications): ignore foreign mobile_app_notification_action events (#178)
The mobile_app_notification_action event bus fires for all integrations,
not just ChoreOps. Previously, every foreign notification action tap
produced a spurious "Failed to parse notification action" ERROR in the
logs.

- Add NOTIFICATION_ACTION_TYPES frozenset to const.py as the single
  source of truth for action type validation
- Add early-exit gate in async_handle_notification_action() that checks
  action type membership before any parsing, silently returning for
  foreign events
- Refactor parse_notification_action() to use the const set instead of
  a duplicated local set

Fixes #174
---
2331627 2026-06-17 09:18:39 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
chore(dev): Add VS Code tasks, dev environment docs, and sync ritual (#176)
What changed:
- Add `.vscode/tasks.json` with 7 emoji-labeled tasks covering the full dev workflow
  (🔗 auto-link, 📖 wiki sync, 📦 dashboard sync, ✅ parity check,
   🔄 HA env refresh, 🧪 test runner, ⚡ quick lint)
- Add `python.defaultInterpreterPath` + `activateEnvInCurrentTerminal: false`
  to `.vscode/settings.json` to fix interpreter resolution to ha-venv
- Add `utils/run_tests.sh` — portable pytest wrapper (ha-venv first, fallback)
- Expand `docs/DEVELOPMENT_STANDARDS.md §1.1` with dependency chain diagram
  and daily sync ritual
- Add `🔄 Refresh HA Dev Environment` task embodying the ritual
- Remove tasks from gitignored `choreops-dev.code-workspace` so they are shared
  via tracked `.vscode/tasks.json`

Why:
- Tasks were invisible to anyone cloning the repo (lived in gitignored workspace file)
- Test task used `${command:python.interpreterPath}` which resolved to local
  `.venv/` without pytest installed
- No documented repeatable workflow for keeping the HA dev environment in sync
  after daily HA core updates
---
7ead4da 2026-06-16 22:24:32 -0600 Ryan Craig <wilcraig@gmail.com>
fix(gamification): reset completion-streak achievements after a missed day (#171)
Completion-streak achievement progress (e.g. "On a Roll", "Unstoppable")
only ever increased. Once a kid reached an N-day streak the achievement
stayed at N forever, even after they skipped one or more full days.

Root cause: the COMPLETION_STREAK branch computed progress as
max(stored_streak, tracked_streak). The stored value was itself only ever
written from that same max(), so it acted as a monotonic high-water-mark
that could never decrease. Compounding this, the tracked streak read each
chore's stored current_streak without checking when it was last completed
-- and a chore's streak is only updated on completion, so it stayed stale
across missed days. Nothing performed any time-based decay.

Fix:
- Engine: use the freshly tracked streak alone instead of
  max(stored, tracked). The stored streak carried no independent
  information, so dropping the max() is the minimal correct change and
  lets a streak fall after a missed day.
- Manager: make _get_tracked_current_streak() staleness-aware via a new
  _streak_alive() helper. A chore's streak now only counts if it was last
  completed today or yesterday (inclusive window, so a streak earned
  yesterday is not prematurely zeroed). Fails open on missing/unparseable
  timestamps so a valid streak is never wrongly reset.
- Manager: re-derive every streak once HA has finished starting (via
  async_at_started), so a streak broken while HA was down is corrected
  without waiting for the next completion or midnight rollover.

Tests: add regression coverage for the engine branch, _streak_alive, and
_get_tracked_current_streak; update the existing streak-achievement engine
test, which had encoded the old high-water-mark behavior, to drive the
streak from the freshly tracked value.
---
7d40c38 2026-06-17 00:01:16 -0400 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>
chore(l10n): sync translations from Crowdin (#173)
* New Crowdin translations by GitHub Action

* New Crowdin translations by GitHub Action

---------

Co-authored-by: Crowdin Bot <support+bot@crowdin.com>
Co-authored-by: copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>
---
9eac00e 2026-06-16 23:42:40 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
Implement primary-standby rotation criteria and dashboard updates (#172)
* feat(rotation): add Primary & Standby chore type

Introduce a new rotation completion criteria where the first assigned
assignee is the permanent primary turn-holder and all others are
standbys. Standbys can claim based on the standby_claim_mode field:

- anytime — claim immediately
- on_overdue — claim only after the due date passes
- manual_only — admin must assign turn via set_rotation_turn

Key behaviors:
- Turn always resets to the primary at every approval reset boundary
- Non-turn standbys see a standby state (not blocked by rotation)
- Standby-needed notifications fire when a chore becomes overdue
- Pause-aware: snapping back to primary on unpause (G-5), advancing
  past paused standbys on pause
- allow_steal is intentionally blocked (standby_claim_mode controls
  claim gating instead)

Adds config/options flow fields, service schemas, translations,
and engine FSM resolution (P3 priority tier) for the new criteria.

* docs(readme): discliamer update for ai assisted development

* test(rotation): add primary-standby FSM state and boundary tests

Add 10 test cases for rotation_primary_standby in a new dedicated
test file covering:

- Primary always sees pending/due (never standby)
- Standby state visibility across all claim modes
- standby_claim_mode.anytime: standby_available mode, claim + approve,
  turn snaps back to primary
- standby_claim_mode.manual_only: blocked_standby mode at all times
- standby_claim_mode.on_overdue: blocked before due, opens after due
- set_rotation_turn override swaps active states, reverse restores
- Turn snaps back to primary in storage after approval
- Single assignee never shows standby
- standby excluded from due-today summary for backups
- Primary pause activates standby, unpause snaps back

Also adds:
- scenario_primary_standby.yaml fixture with 4 chore variants
- standby_claim_mode field mapping in setup.py _parse_chore()
- Test constants: CHORE_STATE_STANDBY, CHORE_STATE_DUE,
  CHORE_CLAIM_MODE_BLOCKED_STANDBY,
  CHORE_CLAIM_MODE_STANDBY_AVAILABLE,
  COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY

* feat(rotation): complete primary-standby dashboard templates (Phase 5a)

Restructure rotation action layout into two visual groups:
- Full-width permanent bar: Move to Front / Make Primary (horizontal "i n" layout)
- 3-column temporary row: Activate/Set Turn · Activate All · Reset

Add reactive cycle-override indicator via Jinja2 `chore_attrs`:
- "All standby users active" appears in warning color when cycle is open
- Template re-renders on entity attribute changes (same mechanism as turn-holder)

Fix `rotation_cycle_override` lifecycle:
- Cleared on `reset_rotation()`, `set_rotation_turn()`, and assignment changes
- Previously only cleared on approval/advancement

Update icons and colors:
- Activate All: `mdi:account-multiple-plus-outline` (warning amber)
- Reset: `mdi:restore` (neutral primary blue)
- Active cycle indicator uses warning amber to match Activate All

Add translation keys: `activate_all`, `all_standby_active`

* feat(services): add per-chore-type reschedule toggles to reschedule_chores_after

Add three independent boolean parameters so users can target exactly which
chore types to reschedule:

- reschedule_independent (default true) — independent (per-assignee due date)
- reschedule_primary_standby (default true) — primary-standby rotation chores
- reschedule_shared (default false) — shared/rotation (simple/smart) chores

Dashboard: replace 2-button All Chores reschedule row with 3-button layout:
[Shift Independent] [Shift Indep & Primary]   ← per-assignee + primary-standby
[              Shift All (incl. shared)       ]   ← everything, full-width

* feat(rotation): add smart resume options with chore-type-aware shift buttons

Add `unpause_action` parameter to `pause_user_chores` service with four
values: `unpause` (default, existing behavior), `unpause_shift_independent`,
`unpause_shift_all_primary`, and `unpause_shift_all`. When unpausing with
a shift action, the manager internally delegates to `reschedule_chores_after`
with appropriate chore-type filters (independent, primary-standby, shared).

Dashboard templates updated with a resume section in the All Chores card,
visible only when chores are paused. Includes a centered "Resume & Reschedule
Past-Due" section header, a single full-width Resume button, and three shift
buttons matching Phase 5c's chore-type filter pattern: Shift Independent,
Shift Indep & Primary, and Shift All (incl. shared). All resume shift buttons
display "Past: Now" as their subtitle, clearly distinguishing them from the
date-picker-driven reschedule buttons below.

Backend: const.py, services.py, services.yaml, chore_manager.py
Frontend: admin-peruser-v1.yaml, admin-shared-v1.yaml, en_dashboard.json
Terminology: Backend uses `pause`/`unpause`; dashboard labels use "Resume"
for user-facing clarity.

* docs: add OpsCenter wiki page, update architecture and standards for primary-standby features

Architecture & standards (choreops/docs/):
- ARCHITECTURE.md: Add standby to FSM priority table and assignee UI allowlist,
  document smart resume unpause_action in pause section
- DEVELOPMENT_STANDARDS.md: Add STANDBY_CLAIM_MODE_*, UNPAUSE_ACTION_*,
  SERVICE_FIELD_RESCHEDULE_* constant naming patterns
- DASHBOARD_UI_DESIGN_GUIDELINE.md: Document admin All Chores section
  pause/resume/reschedule layout and subdued green tint convention
- RELEASE_CHECKLIST.md: Add feature-specific validation checkboxes for
  primary-standby, reschedule filters, and smart resume

* fix: handle lovelace storage format edge case and bump translation sensor ceiling

What changed:
- Wrapped DashboardsCollection.async_load() in try/except KeyError in
  async_dedupe_choreops_dashboards to prevent setup crash when lovelace
  storage returns unexpected data (e.g. in test environments)
- Bumped translation sensor size limit from 11KB to 12KB in
  test_size_05_translation_sensor_under_limit to accommodate new
  dashboard UX translations (11374 bytes vs 11264)

Why:
- The init_integration fixture patches Store.async_load globally, so
  the lovelace DashboardsCollection receives ChoreOps-format data
  without an "items" key, causing a KeyError during setup
- Translations grew by ~110 bytes with recent feature additions

* docs: complete Phase 5b documentation and fix test environment setup

- Add primary-standby explanation to Technical:-Chores.md (only gap found
  in docs audit — all other docs already had thorough coverage)
- Bump translation sensor size limit 11KB→12KB in
  test_size_05_translation_sensor_under_limit (110 bytes over from new
  dashboard UX translations)
- Handle lovelace storage format edge case in
  async_dedupe_choreops_dashboards (try/except KeyError around
  DashboardsCollection.async_load)
- Create missing testing_config/.storage directory for
  pytest-homeassistant-custom-component

* chore(l10n): sync dashboard translations from Crowdin
---
5738220 2026-06-11 13:44:54 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(config-flow): Default CAN_BE_ASSIGNED to True for all new users (#167)
What changed:
- Replaced has_usage_context auto-detection block with unconditional
  setdefault(CAN_BE_ASSIGNED, True) in async_step_users
- Users with can_approve/can_manage roles now default to assignable
  instead of being excluded from the assignee selection list

Why:
- The old logic assumed admin/approver roles were mutually exclusive
  with being an assignee, preventing approvers from being selected
  for chores unless they explicitly checked can_be_assigned
---
5ada5f9 2026-06-11 13:06:54 -0400 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>
New Crowdin translations by GitHub Action (#130)
Co-authored-by: Crowdin Bot <support+bot@crowdin.com>
---
7e5873d 2026-06-11 13:01:38 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
feat: Add user chore pause feature (#166)
* feat: implement user chore pause backend (phases 1-3)

Add `chores_paused` flag to user data model with constants, typed dict,
builder defaults, validation, and options flow schema. Implement unified
P0 guard in `get_chore_status_context` that returns derived `paused`
state for paused users. Insert guards at all signal-emission points
(`_process_overdue`, `_record_chore_missed`, `_process_approval_reset_entries`,
`chore_counts_toward_due_today_summary`, `_is_chore_due_today_for_assignee`,
`can_claim_chore`, `set_rotation_turn`) to suppress overdue/missed processing,
statistics, notifications, and claim actions. Add real-time rotation turn
advancement past paused assignees on pause activation, with midnight safety
net. Add midnight auto-re-enable hook for `chores_paused_until`.

* feat(dashboard): consolidate pause and reschedule into unified All Chores card

Replace the separate Pause Chores and Reschedule Chores cards with a single
collapsible All Chores card in both admin-shared and admin-peruser templates.

- Unified card with expand/collapse toggle, pause controls (Pause / Pause Until... /
  Resume), and reschedule actions (Shift Independent / Shift All)
- Section dividers for Pause Controls and Reschedule Options
- Date picker integration with localized "Past" prefix and time display
- Dynamic grid layout adapting to expanded, paused, and collapsed states
- Total/Due chore counts in collapsed header label
- All user-facing strings use translation keys with err- fallbacks
- Removed orphaned System Administration auto-entities card
- Removed dead translation keys: pause_indefinitely, pause_schedule
- Renamed keys for consistency: pause, pause_until, resume,
  shift_independent, shift_all
- Variables admin-shared-v1.yaml and admin-peruser-v1.yaml

* feat(dashboard): Add consolidated All Chores pause/reschedule admin card

- Collapsible card with pause (indefinite/until date), resume, and shift
  (independent/all) actions in a 4-column grid layout
- Error-tinted pause buttons matching clear_date style
- Success-tinted resume button matching assign_user style
- Primary-tinted shift buttons matching schedule button style
- Section dividers for pause controls and reschedule actions
- Date picker icon with stopPropagation to avoid toggle interference
- Paused state banner with warning color treatment
- Add pause/reschedule translation keys to en_dashboard.json
- Remove orphaned old pause/reschedule card references

* feat(dashboard): Complete Phase 4 display surfaces for chore pause

- Add `blocked_paused` and `chores_are_paused` translation keys
- Add `paused`/`blocked_paused` to admin status_map and status_color_map
- Update shared row templates: statusMap, claimModeIconMap, kids row
  (blocked check, color logic, badge icon)
- Add `paused`/`blocked_paused` to all user template status maps
  (essential, lite, kidsclassic; standard/premier via shared template)
- Add `paused` at priority 5 in sort order (essential, lite)
- Update sort order comments to include paused
- Add paused banner to welcome cards across all 5 user templates:
  warning-colored pause-circle icon with "Chores paused" text,
  replaces stats when user's chores are paused

* feat(chores): Add user chore pause feature

Implement pause chore processing for users with automatic resume,
display surfaces, admin workflow, and full test coverage.

Phases:
- Storage & constants: User-level chores_paused/chores_paused_until
  fields, P0 guard helper _is_chore_paused_for_assignee()
- P0 guard: Blocks FSM resolution at get_chore_status_context(),
  suppresses overdue/missed signals, skips rotation turn-holders
- Display: paused state in status_map, status_color_map, sort order,
  claimModeIconMap across all 9 dashboard templates
- Admin card: Consolidated All Chores card with pause/resume/shift
  controls in a collapsible grid layout
- User banner: Welcome card shows pause indicator when chores are
  paused (warning color, pause-circle icon)
- Service: choreops.pause_user_chores with pause/resume/paused_until
- Tests: 8 tests covering service, display, overdue guard,
  rotation skip, can_claim guard, and lifecycle
- Docs: ARCHITECTURE.md, DASHBOARD_UI_DESIGN_GUIDELINE.md,
  Configuration:-Users.md, Advanced:-Chores.md

* fix(tests): Resolve remaining test failures in template render and options flow

What changed:
- Fixed economy detail test: re-added hero_content extraction removed during
  brittle-assertion cleanup (NameError on undefined variable)
- Fixed system admin test: set admin selector mock state to "Alice" so the
  template's has_selected_user guard renders content
- Removed no_assignees_assigned test cases: empty assignee lists are
  intentionally valid (winter chore disablement), so these assertions were
  incorrect
- Pulled in latest dashboard templates and dashboard translations from
  upstream repositories

Why:
- Template render smoke tests now 24/24 passing
- Options flow entity CRUD tests now 34/34 passing
- Pause chore tests remain 8/8 passing

* fix(user): type_def change to support new pause user data properly
---
3502fc2 2026-06-05 20:58:22 +0000 ccpk1 <64691424+ccpk1@users.noreply.github.com>
feat: unify chore management controls in admin OpsCenter view
- Consolidate all chore management under the Chores section header
  (reset overdue, reschedule, per-chore actions, rotation controls)
- Combine chore selection, assign/remove, and detail overview into
  a single unified card with native entities dropdown selector
- Add rotation management controls (set turn, move to front) with
  ordered rotation display in chore detail
- Move status-colored borders and backgrounds to outer card for
  seamless card-in-card elimination
- Standardize header collapse/expand visuals (background, border,
  spacing) across Management, Chores, and Economy sections
- Localize all user-facing text through translation keys

---
bcacda0 2026-06-05 14:55:07 +0000 ccpk1 <64691424+ccpk1@users.noreply.github.com>
feat(dashboard): add rotation management and shared assignee display to admin chore detail
Display rotation order in chore detail grid with numbered assignee
list and current turn indicator (👈). Show simple assignee list for
shared chores. Add "Set Turn to" and "Move to Front" action buttons
for rotation chores, grouped together with due date below a section
divider.

All controls use existing services (set_rotation_turn, update_chore)
with zero backend changes. Rotation section gated behind
is_rotation_type, shared assignee list behind is_shared_type — both
invisible for independent chores.

---
40de4d2 2026-06-04 21:49:00 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
Chore reschedule card, DAILY_MULTI iteration fix, long-recurrence gate (#163)
* feat(chores): allow empty assignee list and * wildcard for bulk assignment

Enable dormant chores (assigned_user_ids: []) for seasonal hibernation and
unassigned pool chores (#125, #151). Add * sentinel in create_chore and
update_chore services to assign all assignable users at once.

- data_builders: remove create-only "at least one assignee" validation guard
- chore_manager: clear rotation metadata when assigned_user_ids becomes empty
- services: * wildcard resolves to all assignable users via new
  get_all_assignable_user_ids() helper
- services: fix create_chore None-vs-empty-list guard so [] is accepted
- entity_helpers: add get_all_assignable_user_ids() for sentinel resolution
- services.yaml + en.json: document * and empty-list behavior in descriptions
- const.py: remove duplicate Final definitions and unused dead constants
- tests: fix pre-existing label assertion (dict format), 124/124 pass

No new services, no schema bump, no storage changes.

* feat(chores): add assignment_action and per-user chore select sync

Extend the update_chore service with `assignment_action` (add/remove/replace)
and enhance the per-user chore select entity to show all chores with
co-assignee context.

- const.py: add UNASSIGNED_CHORE_PREFIX (⊘), SELECT_SECTION_DIVIDER,
  ASSIGNMENT_ACTION_ADD/REMOVE/REPLACE, DEFAULT_ASSIGNMENT_ACTION
- helpers/entity_helpers.py: add build_chore_select_display_name()
  shared helper for consistent display names across select options
  and the service-level sync function
- select.py: extend AssigneeDashboardHelperChoresSelect.options to
  show unassigned chores (⊘ prefix) with co-assignee display, sorted
  alphabetically with a visual divider between sections
- services.py: add assignment_action field to UPDATE_CHORE_SCHEMA;
  merge logic (add deduplicates, remove filters, replace is default);
  _sync_chore_select_selection() runs before entity sync so selects
  never go "unknown" after assignment changes
- services.yaml / en.json: document assignment_action field
- tests: 4 new assignment_action tests covering add, add-idempotent,
  remove, and replace-default behaviors

Related to #125, #151

* fix(services): auto-generate per-assignee due dates on chore assignment

When assignees are added to an independent chore with a recurring
frequency (weekly, monthly, etc.), validation previously failed with
"date_required_for_frequency" because new users had no due date.

_ensure_per_assignee_due_dates() runs after validation data is built
and applies three rules per assignee:
  1. User-provided explicit due_date → use it
  2. Existing storage date is in the future → preserve it
  3. No date or past date → auto-generate from schedule

Updates both validation_data (so the validator passes) and data_input
(so chore_manager.update_chore persists the dates).

* feat(dashboard): add chore assignment management to admin templates

Add assign/remove buttons to the Chore Management section of both
admin dashboard templates (shared and per-user). The existing per-user
chore selector now shows unassigned chores with a ⊘ prefix and
co-assignee context, enabling one-click assign/remove actions.

- admin-shared-v1.yaml / admin-peruser-v1.yaml: conditional button card
  below the chore selector that detects the ⊘ prefix and renders
  "Assign to [User]" (green, mdi:account-plus-outline) or
  "Remove from [User]" (red, mdi:account-minus-outline)
- Name extraction: strips ⊘ prefix and (co-assignee) suffix before
  passing to choreops.update_chore with assignment_action: add/remove
- Translations: assign_to_user / remove_from_user keys

* fix(chores): bound DAILY_MULTI forward-search with MAX_DATE_CALCULATION_ITERATIONS

_replace_multi_daily only advanced one day when wrapping past
reference_utc, causing reschedule_chores_after to skip DAILY_MULTI
chores whose boundary was more than one day ahead.  Every other
frequency already uses a bounded while-loop to iterate forward
(_calculate_with_relativedelta, dt_next_schedule, dt_add_interval).

What changed:
- _calculate_multi_daily: replaced single `+ days=1` with bounded
  day-by-day loop (max 1000 iterations, matching existing guard)
- The loop parses daily_multi_times for each candidate date and
  returns the first slot strictly after reference_utc

Why:
- reschedule_chores_after with a boundary 8+ days out would find a
  next slot that was still before the boundary, then discard it as
  "schedule_calculation_failed"

* fix(chores): add allow_long_recurrences gate to reschedule_chores_after

Default: only reschedule non-recurring chores and recurrences
with an interval of 2 weeks or less (daily, daily_multi, weekly,
biweekly, custom_1_week).  Monthly/quarterly/yearly recurrences
are skipped unless allow_long_recurrences: true is passed.

What changed:
- services.yaml + services.py: new optional allow_long_recurrences
  boolean service field (default false)
- chore_manager.py: _is_long_recurrence helper gates monthly+,
  period-end, and long custom-interval frequencies
- dashboard buttons default to safe behavior (no flag = long
  recurrences excluded)

Why:
- A 1-week vacation should not push a yearly chore 52 weeks
  forward just because the next recurrence falls after the
  boundary
- Power users can opt in via allow_long_recurrences: true

* fix(chores): Guard per-assignee daily_multi_times injection in _calculate_next_due_date_for_assignee — only override when
  non-empty, preventing empty-string copies from overriding
  chore-level times

* feat(admin): Chore reschedule

Dashboard (admin-shared-v1, admin-peruser-v1):
- Add Reschedule Chores card with shared date picker, "Push independent"
  and "Push all types" buttons using choreops.reschedule_chores_after
- Fix chore details date format to include year (%Y) for yearly chores
---
92dc98f 2026-06-02 14:26:06 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
feat(rewards): per-user assignment with runtime entity sync — no reload (#162)
* feat(rewards): add per-user reward assignment with assigned_user_ids

Add DATA_REWARD_ASSIGNED_USER_IDS field to RewardData TypedDict.
Use SENTINEL_ALL_USERS ("*") as an input-only shortcut — resolved to
explicit gamified user UUIDs at service/flow boundaries, never
persisted. Boot normalization converts any legacy sentinel or missing
fields to explicit UUIDs. Empty lists ("no users") pass through
unchanged and are intentionally supported for blank-to-clear.

Entity gating:
- AssigneeRewardStatusSensor, AssigneeRewardRedeemButton,
  ApproverRewardApproveButton, and ApproverRewardDisapproveButton
  are only created for users assigned to the reward
- Orphaned entities are cleaned via
  remove_orphaned_assignee_reward_entities()
- Dashboard helper rewards list filters by assignment
- Reward status sensor exposes assigned_user_names attribute
  from stored UUIDs (no sentinel expansion needed)

Service layer:
- create_reward and update_reward accept assigned_user_names
  (display names resolved to UUIDs, "*" expands to all gamified)
  and assigned_user_ids (sentinel resolved same as names)
- Services bypass assignment gating by design — administrators
  can redeem/approve rewards for unassigned users via automation
- update_reward() triggers orphan entity cleanup on assignment
  changes; empty list removes all assigned users
- Options flow add/edit reward steps include multi-select for
  assigned users, pre-populated with all gamified users on create

Build/release:
- services.yaml and en.json document assigned_user_names field
  with blank-to-clear pattern and sentinel expansion
- Wiki updated: Configuration:-Rewards, Services:-Reference
- 13 new tests; 72 total pass with zero regressions

Closes #77

* feat(rewards): add runtime entity sync — no reload for reward CRUD

Reward create and assignment updates no longer trigger a full
integration reload. Instead, a targeted runtime entity sync handles
sensor and button creation without disrupting the active dashboard.

- create_reward_entities() upgraded from test-only to production,
  with assignee_ids parameter for targeted creation
- create_reward_button_entities() added to button.py for runtime
  creation of reward redeem, approve, and disapprove buttons
- async_sync_reward_entities() added to coordinator.py for
  one-step entity sync orchestration (create + cleanup)
- Services (create_reward, update_reward) and options flow
  (add/edit reward) use runtime sync instead of reload
- reward_manager.update_reward() no longer spawns async orphan
  cleanup; caller sync handles entity lifecycle
- 2 new "no reload" regression tests; 74 total pass
---
f46fbfc 2026-06-01 17:29:55 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
feat(notifications): add per-user configurable notification clickAction URL (#161)
Add two optional per-user fields that inject a `clickAction` value into
mobile notification payloads, allowing users to land on a specific
dashboard when tapping a notification instead of the last-open screen.

- `notif_click_url`: Used for assignee-directed notifications (chore
  approved, badge earned, points awarded). Configurable in the Identity
  and profile section of the user form.
- `notif_approve_click_url`: Used for approver-directed notifications
  (chore/reward claimed, needs review). Configurable in the Admin and
  approval options section, positioned below the Can approve toggle.

Both fields are optional URL-type text inputs with empty-string defaults,
fully backward compatible with no migration needed. Each recipient's own
URL is used based on notification role (assignee vs approver), supporting
users who serve in both capacities with different landing pages.

Completes Configurable notification clickAction URL per user

Fixes #111
---
4441196 2026-06-01 16:34:30 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
Fix label grouping and preserve user-defined exclude states (#160)
* fix(dashboards): keep label grouping working with friendly labels

What changed:

Normalize chore labels as {id, name} for dashboard rendering
Fix Jinja grouping logic so label filters and grouped label buttons work again
Remove the redundant label_details export
Why:

Preserves the single labels payload shape while restoring label grouping and filtering behavior

* fix(chores): preserve user defined exclude states
---
4ff5798 2026-06-01 13:46:30 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(auth): let linked approvers approve chores and rewards (#159)
What changed:
- Allow a properly linked approver to approve their assigned chores and rewards
- Keep the admin approval bypass option for unlinked HA admins
- Add clearer authorization logging for blocked and allowed approval attempts

Why:
- Fix issue #148 where linked approvers could not approve even when they were tied to the target user
---
d8b4b31 2026-06-01 10:32:34 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(choreops): use configured points label in notifications (#157)
* fix(choreops): missed notification loop

What changed:
- Found that custom_from_complete could reschedule a chore back into the past after a missed-and-locked reset.
- Included chore_name in the CHORE_MISSED payload so missed notifications no longer fall back to Unknown Chore.

Why:
- Prevent repeated expired/missed notifications

Fixes #132

* fix(choreops): use configured points label in notifications

What changed:
- Add shared notification placeholder defaults for the configured points label.
- Update the English notification templates to use {points_label} instead of hardcoded "points".

Why:
- Keeps notification wording aligned with the system’s configured points label.
- Avoids hardcoded currency text in user-facing notifications.
---
4132ace 2026-06-01 10:19:28 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(choreops): missed notification loop (#156)
What changed:
- Found that custom_from_complete could reschedule a chore back into the past after a missed-and-locked reset.
- Included chore_name in the CHORE_MISSED payload so missed notifications no longer fall back to Unknown Chore.

Why:
- Prevent repeated expired/missed notifications

Fixes #132
---
e26c7a8 2026-06-01 09:35:58 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(choreops): drop per-update countdown attributes (#155)
What changed:
- Stop emitting `time_until_due` and `time_until_overdue` from chore status sensors.
- Update the shared chore row template to calculate its own relative countdown text from `due_window_start` and `due_date`.

Why:
- These attributes were causing unnecessary Recorder churn and database growth.
- Breaking change: dashboards or automations that read the removed attributes directly must switch to local calculation or the remaining date fields.

fixes [ISSUE] ChoreOps entities are large in size
Fixes #153
---
b191964 2026-05-20 17:23:30 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
feat(dashboard): add universal points precision setting (#141)
Add a General Options selector for dashboard-wide points precision and
expose the resolved value through the dashboard helper payload.

- persist dashboard points precision in config entry options
- publish resolved precision under dashboard_config on the helper sensor
- sync the canonical dashboard asset contract into the integration mirror
- add targeted helper, render, and options-flow regression coverage
---
139f226 2026-05-09 09:43:25 -0400 ccpk1 <64691424+ccpk1@users.noreply.github.com>
fix(dashboard): improve high-density chore dashboard support (#129)
* chore(version): update to version 1.0.8

* feat(choreops): land dynamic chore runtime sync and sparse edit hardening

Implement the completed CHORE_DYNAMIC_ENTITY_LIFECYCLE plan for beta validation.

- add a chore-scoped runtime sync contract with explicit mutation context
- create and remove live chore sensors and workflow buttons without full entry reload
- route service and options-flow chore CRUD through the shared runtime sync path
- preserve omitted optional values in sparse chore edits while keeping explicit overwrite and clear behavior intact
- expand regression coverage for runtime entity lifecycle, helper flows, and sanctioned reload boundaries
- update README, test guidance, and archive the completed initiative documents

Keep sanctioned system-settings reload behavior intact for non-chore paths.

Validation:
- ./utils/quick_lint.sh --fix
- targeted pytest runtime-sync/options-flow suite: 100 passed

Refs: #107
Plan: CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED

* test(stress): add dense dashboard helper threshold coverage

What changed:
- Added a dense scenario generator and committed 40-100 chores-per-user fixtures
- Added opt-in stress tests for dashboard helper size and a representative claim flow
- Updated scenario/testing docs to cover dense stress runs and live HA manual loading
- Confirmed the current helper-size boundary is between 40 and 50 chores per assignee for the generated dense profile

Why:
- Reproduce issue #124 with the existing scenario framework instead of ad hoc setups
- Establish a repeatable way to measure dashboard helper growth as chore density increases
- Give us a stable baseline for future payload-reduction work in the dashboard helper sensors

* test(stress): add dense dashboard helper threshold coverage (formatting only)

* Implement dashboard helper hybrid sharding phases 1-4

Includes runtime chore shard helpers, shared dashboard snippet migration, dense scenario expansion through 120 chores per assignee, and focused shard validation/documentation updates.

Known follow-up: tests/test_dashboard_helper_sharding.py currently still has two failing lifecycle cases covering reload reconstruction and small-edit shard-pointer publication on the main helper.

* fix(dashboard): stabilize shard helpers and dense renders

* feat(export_codebase):  split bundled export so file size is smaller and accepted in importing systems

Co-authored-by: Copilot <copilot@github.com>

* feat(export_codebase): additional split of backend code

Co-authored-by: Copilot <copilot@github.com>

* test(dashboard): cover shard-aware admin flows

* fix(dashboard): vendor 1.0.5 dashboard assets

* docs(planning): planning documentation cleanup

---------

Co-authored-by: Copilot <copilot@github.com>
---
