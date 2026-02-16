# Initiative Plan

## Initiative snapshot

- **Name / Code**: Async listener migration for thread-safe signal handling (`ASYNC_LISTENER_MIGRATION`)
- **Target release / milestone**: `release/v0.5.0-beta4` hardening window
- **Owner / driver(s)**: KidsChores integration maintainers (manager-layer owners)
- **Status**: Completed
- **Overall progress**: 100% (Phases 1-4 complete)

## Summary & immediate steps

| Phase / Step                                      | Description                                                    | % complete | Quick notes                                                            |
| ------------------------------------------------- | -------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------- |
| Phase 1 – Baseline & policy                       | Define migration guardrails and listener inventory             | 100%       | Baseline, inventory matrix, policy, and schema guard documented        |
| Phase 2 – StatisticsManager migration             | Convert write-path listeners to async-first pattern            | 100%       | Write-path listeners migrated to async with targeted validation        |
| Phase 3 – Notification & Economy/Reward migration | Remove manual thread marshaling and unsafe task creation paths | 100%       | Notification/Economy/Reward listeners migrated to async-safe flow      |
| Phase 4 – Validation & closure                    | Execute full quality gates and runtime thread-safety audit     | 100%       | Gates complete; no new thread-safety warnings in latest runtime window |

1. **Key objective** – Eliminate thread-context violations in signal listeners by migrating state-modifying handlers to `async def` so Home Assistant dispatcher schedules them on the event loop safely.
2. **Summary of recent work**
   - Event/listener architecture and standards reviewed (`BaseManager.listen`, signal-first rules).
   - Hotspots identified in `StatisticsManager`, `NotificationManager`, `EconomyManager`, and `RewardManager`.
   - Full regression suite baseline already confirmed green (`1261 passed, 2 skipped, 2 deselected`).
   - Phase 1 completed with implementation inventory artifact: `docs/in-process/ASYNC_LISTENER_MIGRATION_SUP_IMPLEMENTATION_MATRIX.md`.
3. **Next steps (short term)**
  - Completed and archived.
4. **Risks / blockers**
   - Handler signature drift can break dispatcher payload compatibility if callback parameters change.
   - Changing fire-and-forget notification behavior to awaited flows may alter timing/order.
   - Mixed sync/async listeners can temporarily mask race paths until all write-path handlers are migrated.
5. **References** –
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `docs/QUALITY_REFERENCE.md`
  - `docs/completed/ASYNC_LISTENER_MIGRATION_SUP_IMPLEMENTATION_MATRIX_COMPLETED.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `tests/AGENT_TESTING_USAGE_GUIDE.md`
   - `docs/RELEASE_CHECKLIST.md`
   6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep `BaseManager.listen` as-is; leverage HA dispatcher coroutine scheduling behavior.
     - Convert state-modifying listeners to `async def`; keep read-only/log-only listeners sync where appropriate.
     - Prefer direct `await` in async listeners over manual `call_soon_threadsafe(...async_create_task...)` wrappers.
     - No storage schema changes planned; `meta.schema_version` remains unchanged.
   - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Baseline & async policy

- **Goal**: Establish a consistent migration policy and verified inventory before editing manager code.
- **Steps / detailed work items**
  1. - [x] Confirm listener registration baseline and callback type expectations
     - File: `custom_components/kidschores/managers/base_manager.py` (lines ~82-106)
     - Validate `listen()` callback contract remains compatible with both sync and async handlers.
  2. - [x] Build listener inventory for all target managers (sync vs async, write-path vs read-path)
     - Files: `managers/statistics_manager.py` (setup lines ~119-163), `managers/notification_manager.py` (setup lines ~150-190), `managers/economy_manager.py` (setup lines ~92-126), `managers/reward_manager.py` (setup lines ~81-84)
     - Output artifact: migration checklist table (handler name, current type, target type, state-touching yes/no).
  3. - [x] Define thread policy for this initiative in plan notes and implementation PR description
     - Reference: `docs/DEVELOPMENT_STANDARDS.md` § Data Write Standards and § Event Architecture (~158, ~696+)
     - Rule: any listener calling `async_set_updated_data`, registry/state APIs, notification send methods, or persistence+update sequences must be async.
  4. - [x] Establish no-schema-change assertion and regression guard
     - Reference: `docs/ARCHITECTURE.md` schema sections (~456+)
     - Confirm no migration function or `SCHEMA_VERSION` changes are required for this initiative.
- **Phase completion evidence**
  - Listener baseline and callback compatibility confirmed in `BaseManager.listen`.
  - Handler inventory and migration batching documented in `ASYNC_LISTENER_MIGRATION_SUP_IMPLEMENTATION_MATRIX.md`.
  - Async policy and guardrails captured in both this plan and support matrix.
  - Schema guard set: no storage/schema migration scope included for this initiative.
- **Key issues**
  - Inventory must be complete before conversion to avoid partial-thread-safety regressions.
  - Existing inline comments may describe sync assumptions that must be updated during migration.

### Phase 2 – StatisticsManager async migration (blueprint)

- **Goal**: Convert high-frequency statistics listeners to async-safe handlers and remove sync-thread update hazards.
- **Steps / detailed work items**
  1.  - [x] Migrate write-path listener methods from `@callback def` to `async def`
  - File: `custom_components/kidschores/managers/statistics_manager.py`
  - Priority handlers (line hints): `_on_points_changed` (~212), `_on_chore_approved` (~384), `_on_chore_completed` (~413), `_on_reward_approved` (~794), `_on_badge_earned` (~982), `_on_bonus_applied` (~1068), `_on_penalty_applied` (~1161), `_on_data_reset_complete` (~1254).
  2.  - [x] Keep read-only/cache-only handlers sync where safe, or convert if they chain to write/update APIs
  - Candidate review: `_on_midnight_rollover` (~198), `_on_chore_status_reset` (~733), `_on_chore_undone` (~762).
  3.  - [x] Replace direct state refresh patterns with awaited async update calls where supported
  - Verify all `async_set_updated_data`/listener refresh points in this manager run on loop and are awaited when coroutine-based.
  4.  - [x] Re-check startup cascade correctness after conversion
  - Validate `CHORES_READY -> _on_chores_ready` (~361) and subsequent `STATS_READY` behavior remain deterministic.
  5.  - [x] Add/adjust manager-focused tests for async callback behavior if coverage gaps appear
  - Tests: `tests/test_workflow_chores.py`, `tests/test_workflow_gaps.py`, `tests/test_coordinator.py` (if present/affected), `tests/test_workflow_notifications.py` for downstream event effects.
- **Key issues**
  - This manager touches many period buckets; preserve exact counter semantics while changing callback type.
  - Avoid broad refactors beyond callback type and thread-safety paths.
- **Phase completion evidence**
  - Converted all targeted `StatisticsManager` signal handlers from sync `@callback def` to `async def`, including P0/P1 plus reviewed reset/status handlers.
  - Kept startup cascade intact (`_on_chores_ready` remained async; signal subscription wiring unchanged).
  - Verified update calls remain loop-safe after migration; no additional await conversion required for coordinator update method usage.

### Phase 3 – Notification + Economy/Reward migration

- **Goal**: Eliminate manual thread marshaling and unsafe task scheduling in remaining state/notification handlers.
- **Steps / detailed work items**
  1. - [x] Convert notification event handlers to async and remove direct sync-thread `async_create_task` patterns
     - File: `custom_components/kidschores/managers/notification_manager.py`
     - High-volume handlers (line hints): `_handle_badge_earned` (~1667), `_handle_achievement_earned` (~1723), `_handle_challenge_completed` (~1785), `_handle_chore_claimed` (~1841), `_handle_reward_claimed` (~1966), `_handle_chore_due_window` (~2288), `_handle_chore_due_reminder` (~2359), `_handle_chore_overdue` (~2428), `_handle_chore_missed` (~2591).
  2. - [x] Convert `EconomyManager` remaining sync listeners that schedule async work
     - File: `custom_components/kidschores/managers/economy_manager.py`
     - Target handlers: `_on_badge_earned` (~163), `_on_achievement_earned` (~190), `_on_challenge_completed` (~246), plus any callback invoking `call_soon_threadsafe` (~182, ~202, ~215, ~263, ~284).
  3. - [x] Convert `RewardManager` badge listener and state-update write paths to loop-safe async handling
     - File: `custom_components/kidschores/managers/reward_manager.py`
     - Target handler: `_on_badge_earned` (~86); verify `async_set_updated_data` usage around ~125, ~659, ~752, ~977 remains on loop-safe paths.
  4. - [x] Remove obsolete thread-marshaling wrappers once async listener migration is complete
     - Files: `economy_manager.py`, `notification_manager.py`, any helper wrappers introduced only for cross-thread scheduling.
  5. - [x] Update docstrings to reflect async execution guarantees and error handling strategy
     - Files: all touched manager modules.
- **Key issues**
  - Notification ordering and dedupe behavior must not regress when switching from fire-and-forget style to awaited execution.
  - Potential temporary performance variance during migration; validate with existing workflow and notification tests.
- **Phase completion evidence**
  - `NotificationManager` event handlers are now async and execute notification/cleanup operations with direct `await` paths.
  - `EconomyManager` award listeners (`badge`, `achievement`, `challenge`) migrated to async and no longer depend on cross-thread `call_soon_threadsafe` wrappers.
  - `RewardManager._on_badge_earned` migrated to async for loop-safe persist/update execution.
  - Targeted regression checks passed for chores and notifications after migration.

### Phase 4 – Validation, audit, and release readiness

- **Goal**: Verify no thread-safety regressions remain and close the initiative with objective evidence.
- **Steps / detailed work items**
  1. - [x] Run mandatory lint/quality gate
     - Command: `./utils/quick_lint.sh --fix`
  2. - [x] Run strict typing for integration code
     - Command: `mypy custom_components/kidschores/`
  3. - [x] Run targeted async/listener regression tests first
     - Commands:
       - `python -m pytest tests/test_workflow_chores.py -v --tb=line`
       - `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
       - `python -m pytest tests/test_workflow_gaps.py -v --tb=line`
  4. - [x] Run full regression suite (mandatory)
     - Command: `python -m pytest tests/ -v --tb=line`
  5. - [x] Audit logs for thread-safety/runtime warnings after event-heavy workflows
     - Verify no `RuntimeError` signatures related to thread misuse (`async_create_task`, `async_write_ha_state`, registry/state operations from worker thread).
  6. - [x] Update initiative summary percentages and complete decisions/completion check section
     - File: this plan document before handoff/closure.
- **Key issues**
  - If mypy fails repeatedly on callback signatures, pause and resolve typing architecture before widening scope.
  - Full suite runtime is non-trivial; targeted suites should be green first to speed iteration.
- **Phase completion evidence**
  - Lint/quality gate passed with clean boundary checks (`./utils/quick_lint.sh --fix`).
  - MyPy gate passed (`mypy custom_components/kidschores/` -> zero errors).
  - Full suite passed per owner-confirmed run (`1261 passed, 2 skipped, 2 deselected`, 305.69s).
  - Runtime audit identified historical warnings at `17:07:44` pointing to pre-migration `economy_manager.py` line mapping; latest log window through `17:59` shows no new thread-safety warnings.

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- **Planned tests**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/test_workflow_chores.py -v --tb=line`
  - `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
  - `python -m pytest tests/test_workflow_gaps.py -v --tb=line`
  - `python -m pytest tests/ -v --tb=line`
- **Existing baseline**
  - Most recent full suite baseline before this initiative: `1261 passed, 2 skipped, 2 deselected`.
- **Phase 1 validation executed**
  - ✅ `./utils/quick_lint.sh --fix` passed (ruff clean, format no changes, mypy clean, boundary checks all pass)
  - ✅ `mypy custom_components/kidschores/` passed (`Success: no issues found in 48 source files`)
  - ✅ Full test gate satisfied using immediate pre-phase run evidence (`python -m pytest tests/ -v --tb=line` → `1261 passed, 2 skipped, 2 deselected`, 244.36s), accepted by owner without rerun
- **Phase 2 validation executed**
  - ✅ `./utils/quick_lint.sh --fix` passed after `StatisticsManager` migration
  - ✅ `mypy custom_components/kidschores/` passed (`Success: no issues found in 48 source files`)
  - ✅ `python -m pytest tests/test_workflow_chores.py -v --tb=line` passed (`27 passed`)
  - ✅ `python -m pytest tests/test_workflow_notifications.py -v --tb=line` passed (`18 passed`)
  - ⏭️ `tests/test_workflow_gaps.py` not rerun in this phase by owner direction (“enough tests, continue”)
- **Phase 3 validation executed**
  - ✅ `./utils/quick_lint.sh --fix` passed after `Notification/Economy/Reward` migration
  - ✅ `mypy custom_components/kidschores/` passed (`Success: no issues found in 48 source files`)
  - ✅ `python -m pytest tests/test_workflow_notifications.py -v --tb=line` passed (`18 passed`)
  - ✅ `python -m pytest tests/test_workflow_chores.py -v --tb=line` passed (`27 passed`)
  - ⏭️ `tests/test_workflow_gaps.py` not rerun in this phase by owner direction (“enough tests, continue”)
- **Phase 4 validation executed**
  - ✅ `./utils/quick_lint.sh --fix` passed
  - ✅ `mypy custom_components/kidschores/` passed (`Success: no issues found in 48 source files`)
  - ✅ Targeted regression evidence satisfied (Phase 3 targeted suites + no regressions surfaced in full suite)
  - ✅ Full suite passed per owner-confirmed run: `python -m pytest tests/ -v --tb=line` -> `1261 passed, 2 skipped, 2 deselected` (305.69s)
  - ✅ Runtime warning audit completed: no new thread-safety warnings in latest log activity window after migration
- **Outstanding tests**
  - None for implementation completion; optional extra runtime smoke validation can be run before archive if desired.

## Notes & follow-up

- This initiative addresses architectural technical debt for Home Assistant async/thread-safety compliance and Platinum-quality expectations.
- No translation key, config-flow schema, or storage migration work is planned in this initiative.
- Handoff to implementation agent should be blocked until Phase 1 listener inventory and policy checklist are explicitly checked complete.

### Optional hardening pass – remove remaining async task ambiguity

This is an optional post-completion pass to eliminate remaining ambiguity around `async_create_task` usage in sync call paths.

#### Current remaining call sites and effort

1. **`custom_components/kidschores/managers/chore_manager.py`** (medium risk, medium effort)
   - **Locations**: `update_chore()` and `delete_chore()` currently call `hass.async_create_task(...)` for orphan cleanup helpers.
   - **Why ambiguous**: These methods are sync and may be reached from service/options flow paths that are not always obviously loop-bound.
   - **Hardening action**:
     - Replace direct `hass.async_create_task(...)` with `hass.add_job(...)` for cleanup coroutine dispatch, **or** convert these methods to async with awaited cleanup semantics where safe.
     - Keep emit/persist ordering unchanged (persist before lifecycle signal).
   - **Validation focus**: chore CRUD + orphan entity cleanup behavior.

2. **`custom_components/kidschores/sensor.py`** (low risk, low effort)
   - **Location**: `_get_translation_sensor_eid()` schedules translation sensor creation with `hass.async_create_task(...)`.
   - **Why ambiguous**: Called from sync sensor property path.
   - **Hardening action**:
     - Replace with `hass.add_job(self.coordinator.ui_manager.ensure_translation_sensor_exists(...))` to guarantee loop-safe scheduling regardless of caller context.
   - **Validation focus**: language change creates translation sensor without warnings.

3. **`custom_components/kidschores/migration_pre_v50.py`** (deferred by owner direction)
   - **Status**: Explicitly excluded from this pass.
   - **Reason**: Owner requested no changes in this file for current hardening.
   - **Future option**: If revisited, migrate sync-path `async_create_task(...)` calls to loop-safe scheduling.

4. **`custom_components/kidschores/managers/gamification_manager.py`** (already loop-safe; optional polish)
   - **Location**: debounced eval uses `call_soon_threadsafe` and then `loop.call_later(... async_create_task(...))`.
   - **Assessment**: current pattern is explicitly loop-marshaled and acceptable.
   - **Optional polish**:
     - Keep as-is, or switch inner scheduling to `hass.add_job(...)` for consistency with broader hardening pattern.

5. **`custom_components/kidschores/coordinator.py`** (already loop-safe)
   - **Location**: debounced persist task creation.
   - **Assessment**: guarded by `call_soon_threadsafe` entry from non-loop contexts; safe.
   - **Action**: no change required.

#### Estimated implementation size

- **Small**: 2 files with direct edits in this pass (`chore_manager.py`, `sensor.py`).
- **Optional consistency-only**: 1 file (`gamification_manager.py`).
- **Deferred**: `migration_pre_v50.py` excluded by owner direction.
- **Expected code churn**: low-to-moderate (~15-40 lines depending on optional polish).

#### Recommended pattern for this pass

- Use `hass.add_job(coro(...))` in sync methods when you only need to schedule work.
- Keep `async def` + direct `await` when ordering/transaction guarantees are required.
- Avoid introducing new cross-thread wrappers unless absolutely necessary.

#### Validation plan for optional hardening pass

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/kidschores/`
- `python -m pytest tests/test_workflow_chores.py -v --tb=line`
- `python -m pytest tests/test_workflow_notifications.py -v --tb=line`
- `python -m pytest tests/ -v --tb=line` (or owner-approved equivalent)
- Runtime log audit grep for thread-safety warnings in active post-change window

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
