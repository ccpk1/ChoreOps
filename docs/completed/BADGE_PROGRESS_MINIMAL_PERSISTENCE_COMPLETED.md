# Initiative Plan

## Initiative snapshot

- **Name / Code**: Badge progress minimal persistence cleanup
- **Target release / milestone**: `release/0.5.0-beta.5-prep` follow-up hardening
- **Owner / driver(s)**: ChoreOps maintainers + Builder execution handoff
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                         | Description                                                   | % complete | Quick notes                                                                 |
| ------------------------------------ | ------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------- |
| Phase 1 – Contract + field policy    | Define required vs denormalized `badge_progress` fields       | 100%       | Contract, constants, and typed shape locked; `name` retained                |
| Phase 2 – Manager + sensor alignment | Move active cycle dates to badge-level source and align reads | 100%       | Canonical schedule authority and midnight catch-up path aligned             |
| Phase 3 – Migration + tests          | Strip legacy user fields safely and update tests              | 100%       | Schema45 cleanup covers retired fields; targeted regression coverage passed |
| Phase 4 – Docs + validation          | Update architecture/developer docs and run quality gates      | 100%       | Owner-approved complete; remaining suite issues tracked outside badge scope |

1. **Key objective** – Reduce assignee `badge_progress` to required runtime fields only (plus `name`) while making badge-level schedule dates the single persisted source of truth.
2. **Summary of recent work**
   - Analysis confirmed per-user schedule fields (`start_date`, `end_date`, `recurring_frequency`) are written in `sync_badge_progress_for_assignee` and used in rollover.
   - Analysis confirmed assignee badge-progress sensor currently falls back to badge reset schedule when user fields are missing.
   - Analysis confirmed user reset clears badge runtime fields and can expose sparse progress creation paths.

- Analysis confirmed the existing midnight rollover signal and startup recovery signal path are the intended orchestration points for stale schedule catch-up.
- Detailed Builder blueprints now define the exact current-cycle sensor contract: inactive-window badges render `0%` progress while historical earned metadata remains visible.

3. **Next steps (short term)**

- No additional work is required for this initiative scope.
- Broader full-suite chore/rotation follow-ups remain tracked separately outside this archive.

4. **Risks / blockers**

- Badge-level date ownership requires clear rules for reschedule/schedule-edit behavior to avoid unintended jumps in active cycle windows.
- Midnight/startup recovery handling must persist cycle rollover promptly enough that first-morning dashboard views do not show stale prior-day windows.
- Existing tests currently assert user `start_date`/`end_date`; those must be intentionally rewritten, not patched ad hoc.
- Dashboard and troubleshooting flows may rely on denormalized fields in unexpected places.

5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`

- `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
- `tests/AGENT_TESTING_USAGE_GUIDE.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/PLAN_TEMPLATE.md`

6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep `badge_progress.name` as a persisted troubleshooting field.
     - Directionally remove user-level schedule date persistence from `badge_progress`.
     - Active periodic cycle dates (`start_date`, `end_date`) are persisted on the badge record and treated as canonical source for all users assigned to that badge.
     - Any no-longer-required badge-progress constants are moved out of active runtime constants and into `migration_pre_v50_constants.py` with `_LEGACY` suffix.
   - Use the existing midnight rollover signal, plus its built-in startup recovery emission, as the sole orchestration path for schedule catch-up; do not add a separate signal model.
   - Existing badge earned history storage is sufficient as the historical record; no new historical badge storage model is planned.
   - Assignee badge-progress sensor must represent current-cycle activity, not historical earned state: inactive-window badges report `0%` progress, while historical earn count remains separately visible for troubleshooting/reporting.

- **Completion confirmation**: `[x]` Owner-approved complete for badge-progress persistence scope.

## Detailed phase tracking

### Phase 1 – Contract + field policy

- **Goal**: Define a strict minimal `AssigneeBadgeProgress` contract and authoritative source rules.
- **Steps / detailed work items**
  - [x] Create explicit “required runtime fields” list in planning notes and map each to writer/reader paths using `custom_components/choreops/managers/gamification_manager.py` (~1363-1765, ~4120-4645).
  - [x] Classify all current persisted badge-progress keys into: keep, remove, derived-from-badge, derived-from-runtime-eval (anchor in `custom_components/choreops/type_defs.py` ~481-540).
  - [x] Define source-of-truth matrix for schedule values used by rollover/evaluation/sensor output with badge-level canonical ownership (anchor in `custom_components/choreops/managers/gamification_manager.py` ~1421-1530 and `custom_components/choreops/sensor.py` ~2187-2208).
  - [x] Decide and document exact keep-set for this initiative: include `name`; include only user runtime counters/status needed for evaluation.
  - [x] Document current-cycle vs historical-earned semantics: use existing badge earned history as secondary informational data, while cycle state is driven by current evaluation/status and inactive windows render `0%` progress.
  - [x] Record non-goals for this phase: no separate runtime badge-cycle container; use badge `reset_schedule` dates as persisted cycle source.
- **Key issues**
  - Open-ended periodic windows currently rely on persisted per-user dates; replacement logic must safely transition to badge-level persisted dates.

### Phase 2 – Manager + sensor alignment

- **Goal**: Plan code-path changes so schedule reads use badge-level persisted dates and user progress remains minimal.
- **Steps / detailed work items**
  - [x] Update sync plan to stop writing denormalized schedule/config fields to user progress in `custom_components/choreops/managers/gamification_manager.py` (~4302-4645), except `name` and required runtime metrics.
  - [x] Add/adjust manager logic so cycle `start_date` and `end_date` are written and updated in `badges[*].reset_schedule` during initial scheduling, rollover, and reschedule flows in `custom_components/choreops/managers/gamification_manager.py` (~1421-1530, ~4302-4645, ~4690-4830).
  - [x] Update `custom_components/choreops/managers/gamification_manager.py` midnight rollover handling so the existing midnight signal path performs persisted non-cumulative cycle catch-up before stale dashboard reads can occur.
  - [x] Confirm startup recovery, which already re-emits the missed midnight signal, exercises the same catch-up path without duplicated logic.
  - [x] Ensure badge schedule edit/reschedule operations update canonical badge-level dates and trigger consistent recomputation for assigned users.
  - [x] Update sensor plan in `custom_components/choreops/sensor.py` (~2187-2278) to expose schedule from a single authoritative source, avoid mixed fallback semantics, and clamp inactive-window progress to `0%` even when earned history exists.
  - [x] Review reset impact in `custom_components/choreops/managers/gamification_manager.py` (~5205-5272) to ensure first-write behavior is valid with stripped user fields.
  - [x] Identify and update any helper/debug endpoints that assume denormalized user schedule fields (search in manager/sensor/tests).
- **Key issues**
  - Existing rollover helper reads user `recurring_frequency`/`end_date`; prerequisite logic must be safely relocated to badge-level schedule reads.
  - Existing dashboard/helper outputs may still show historical earned data even when the current cycle has rolled; this must be made explicit and tested.

### Phase 3 – Migration + tests

- **Goal**: Plan safe data cleanup and regression coverage for existing installs.
- **Steps / detailed work items**
  - [x] Add migration checklist for stripping deprecated user badge-progress fields via idempotent schema45 contract hook in `custom_components/choreops/migration_pre_v50.py` (~473-760).
  - [x] Move any no-longer-required active badge-progress constants from runtime constants to `custom_components/choreops/migration_pre_v50_constants.py`, rename with `_LEGACY`, and update all migration references.
  - [x] Extend schema45 cleanup routine to remove those retired badge-progress keys from `users[*].badge_progress[*]` in one pass (same process pattern as prior legacy key cleanup).
  - [x] Update type contract tests and schema45 migration tests in `tests/test_schema45_user_migration.py` (extend existing legacy-field cleanup pattern).
  - [x] Update behavioral tests in `tests/test_badge_target_types.py` (~448-1320) to assert minimal persisted user keys and badge-level authoritative schedule rendering.
  - [x] Add explicit reset-path test coverage for removed legacy fields by asserting first periodic evaluation no longer persists deprecated fields.
  - [x] Add sensor attribute test coverage for assignee badge-progress schedule attributes coming from badge-level canonical dates rather than user `start_date`/`end_date`.
  - [x] Archive the removal of retired progress fields `assigned_user_ids`, `chores_completed`, and `days_completed` in schema45 cleanup and targeted tests.
  - [x] Add midnight-rollover test coverage through the pending queue catch-up path.
  - [x] Add startup-recovery test coverage through the same catch-up path.
- **Key issues**
  - **Schema version note**: prefer schema45 hook extension with marker (no version bump) if shape change remains backward-compatible; escalate to schema bump only if migration semantics require a hard version checkpoint.

### Phase 4 – Docs + validation

- **Goal**: Ensure maintainability, release safety, and explicit operator guidance.
- **Steps / detailed work items**
  - [ ] Update `docs/ARCHITECTURE.md` with final source-of-truth: badge-level `reset_schedule.start_date/end_date` as canonical persisted cycle window; user progress keeps runtime metrics + `name` only.
  - [ ] Update `docs/DEVELOPMENT_STANDARDS.md` with persistence policy for denormalized badge fields and troubleshooting exception (`name`).
  - [ ] Add release note/checklist entry in `docs/RELEASE_CHECKLIST.md` describing migration behavior and expected post-upgrade state.
  - [ ] Run and document validation commands:
    - [x] `./utils/quick_lint.sh --fix`
    - [x] `mypy custom_components/choreops/`
    - [x] `python -m pytest tests/test_badge_target_types.py tests/test_schema45_user_migration.py -v --tb=line`
    - [ ] `python -m pytest tests/ -v --tb=line` (final confidence run)
- **Key issues**
  - If broader suite reveals unrelated failures, document as external blockers without expanding scope.

## Builder execution blueprint

## Critical - This is a hard fork and complete redesign. there should not be any legacy wrappers or compatibility items left in the production code. The exception to this is that are supporting a migration from the legacy system, so we need to handle any cleanup/conversion for those users, but ONLY in the migration_pre_v50.py and associated constants file.

### Review conclusions

- The current runtime still denormalizes badge schedule into per-user `badge_progress` via `custom_components/choreops/managers/gamification_manager.py` in `sync_badge_progress_for_assignee()` and related rollover helpers.
- The current sensor contract in `custom_components/choreops/sensor.py` still masks missing per-user schedule state by falling back to badge schedule data.
- The current migration path in `custom_components/choreops/migration_pre_v50.py` is already the correct extension point for this cleanup and should be expanded rather than replaced.
- Existing tests in `tests/test_badge_target_types.py` and `tests/test_schema45_user_migration.py` currently encode the legacy contract and must be intentionally rewritten.

### Blueprint A – Minimal assignee badge-progress contract

**Keep in assignee badge progress**

- `name`
- `status`
- `overall_progress`
- `criteria_met`
- `last_update_day`
- `points_cycle_count`
- `chores_cycle_count`
- `days_cycle_count`

**Retire from active assignee persistence**

- `recurring_frequency`
- `start_date`
- `end_date`
- `target_type`
- `threshold_value`
- `badge_type`
- `chores_completed`
- `days_completed`
- `assigned_user_ids`
- `tracked_chores`
- `occasion_type`
- `associated_achievement`
- `associated_challenge`
- other duplicated badge-config fields now derivable from badge data

**Reference methods / files**

- `custom_components/choreops/type_defs.py` → `AssigneeBadgeProgress`
- `custom_components/choreops/managers/gamification_manager.py` → `sync_badge_progress_for_assignee()`
- `custom_components/choreops/data_builders.py` → badge runtime preserve/reset helpers

### Blueprint B – Badge schedule authority

**Canonical schedule fields**

- `badges[*].reset_schedule.recurring_frequency`
- `badges[*].reset_schedule.start_date`
- `badges[*].reset_schedule.end_date`
- `badges[*].reset_schedule.custom_interval`
- `badges[*].reset_schedule.custom_interval_unit`

**Reference methods / files**

- `custom_components/choreops/managers/gamification_manager.py` → `_ensure_assignee_periodic_badge_structures()`
- `custom_components/choreops/managers/gamification_manager.py` → `_advance_non_cumulative_badge_cycle_if_needed()`
- `custom_components/choreops/managers/gamification_manager.py` → `_is_periodic_award_recorded_for_current_cycle()`
- `custom_components/choreops/managers/gamification_manager.py` → `create_badge()`
- `custom_components/choreops/managers/gamification_manager.py` → `update_badge()`

### Blueprint C – Midnight and startup recovery

- Midnight rollover must persist non-cumulative cycle catch-up before the first morning dashboard read.
- Startup recovery must reuse the same catch-up path already triggered by the missed-midnight recovery emission.
- Persist first, then emit downstream effects.
- No new signal model is allowed.

**Reference methods / files**

- `custom_components/choreops/managers/gamification_manager.py` → `async_setup()`
- `custom_components/choreops/managers/gamification_manager.py` → `_on_midnight_rollover()`
- `custom_components/choreops/managers/gamification_manager.py` → `_evaluate_pending_assignees()`

### Blueprint D – Sensor current-cycle contract

- If a badge is active, show current-cycle progress.
- If a badge has no active current window, show `0%`. For clarity, badges with no dates are always active and should show current progress
- Keep historical award metadata visible in attributes.
- Historical earned state must not force current-cycle progress to remain `100%`.

**Reference methods / files**

- `custom_components/choreops/sensor.py` → `AssigneeBadgeProgressSensor.native_value`
- `custom_components/choreops/sensor.py` → `AssigneeBadgeProgressSensor.extra_state_attributes`

### Blueprint E – Migration and cleanup contract

- Retired assignee-progress constants move to `custom_components/choreops/migration_pre_v50_constants.py` with `_LEGACY` suffix.
- `custom_components/choreops/migration_pre_v50.py` schema45 cleanup removes the full retired key set in one idempotent pass.
- Migration summaries must remain deterministic and testable.
- Prefer schema45 extension over a schema bump unless implementation proves a hard checkpoint is required.

### Blueprint F – Platinum quality enforcement

- Full typing on changed code
- No avoidable `# type: ignore`
- Lazy logging only
- Manager-owned writes only
- Signal-first orchestration preserved
- `dt_*` helpers for datetime logic
- Public method docstrings updated
- No hardcoded user-facing strings
- No architecture-boundary violations

## Required validation commands

- [x] `./utils/quick_lint.sh --fix`
- [x] `mypy custom_components/choreops/`
- [ ] `mypy tests/`
- [x] `python -m pytest tests/test_badge_target_types.py tests/test_schema45_user_migration.py -v --tb=line`
- [ ] `python -m pytest tests/ -v --tb=line`

## Phase 1 closeout note

- Phase 1 is complete and validated for the badge-progress contract, runtime constant retirement, migration summary expansion, and targeted regression coverage.
- Broad full-suite validation surfaced four unrelated existing failures outside this initiative scope:
  - `tests/test_chore_manager.py::TestCompletionCriteria::test_shared_first_completion`
  - `tests/test_chore_manager.py::TestCompletionCriteria::test_shared_completion_appends_to_list`
  - `tests/test_chore_state_matrix.py::TestGlobalStateConsistency::test_rotation_global_state_tracks_claim_without_losing_single_turn_pending`
  - `tests/test_rotation_services.py::test_open_rotation_cycle_allows_one_claim_then_blocks_others`
- Per plan guardrails, these are recorded as external blockers rather than expanding badge-progress scope during Phase 1 closeout.

## Phase 2 execution note

- Phase 2 core implementation is complete for canonical schedule authority:
  - non-cumulative schedule writes now stay on `badges[*].reset_schedule`
  - per-user `badge_progress` no longer reintroduces `recurring_frequency`, `start_date`, `end_date`, or `cycle_count`
  - sensor schedule attributes now read from the badge record only
- Validation completed for the Phase 2 code path:
  - `./utils/quick_lint.sh --fix`
  - `python -m pytest tests/test_badge_target_types.py -v --tb=line`
  - `python -m pytest tests/test_badge_target_types.py tests/test_badge_periods_initialization.py tests/test_badge_cumulative.py tests/test_badge_helpers.py tests/test_gamification_engine.py tests/test_gamification_shadow_comparison.py tests/test_workflow_gamification_pending_queue.py tests/test_workflow_streak_schedule.py tests/test_schedule_engine_streaks.py -v --tb=line`
- Midnight rollover/startup-recovery hardening remains open for Phase 3.

## Phase 3 execution note

- Midnight rollover now reuses the existing pending-evaluation path but drains it immediately instead of waiting for debounce.
- Startup recovery continues to emit `catch_up=True` on the existing midnight signal, and the gamification manager now executes the same immediate drain path for that payload.
- The last badge-progress `_LEGACY` runtime usage was removed from production code; retired tracked-chores cleanup now lives only in schema45 migration/tests.
- Additional cleanup removed the remaining unused assignee badge-progress fields `assigned_user_ids`, `chores_completed`, and `days_completed` from active runtime persistence while preserving schema45 cleanup coverage for legacy stored data.
- Validation completed for the Phase 3 code path:
  - `./utils/quick_lint.sh --fix`
  - `python -m pytest tests/test_workflow_gamification_pending_queue.py tests/test_migration_hardening.py -k "midnight_catchup or midnight_rollover" -v --tb=line`
  - `python -m pytest tests/test_badge_target_types.py tests/test_workflow_gamification_pending_queue.py -v --tb=line`
  - `python -m pytest tests/test_badge_target_types.py tests/test_schema45_user_migration.py -v --tb=line`

## Phase 4 completion note

- Phase 4 is owner-approved complete for this initiative.
- Validation completed for the badge-progress cleanup scope:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/test_badge_target_types.py tests/test_schema45_user_migration.py -v --tb=line`
- Full-suite validation remains tracked separately in the checklist, but broader suite findings reviewed during closeout were determined to be outside the badge-progress persistence scope, including outdated rotation-state assertions and separate chore-state contract follow-up.

## Builder kickoff summary

1. Remove assignee-level badge schedule persistence and keep only minimal runtime badge-progress fields plus `name`.
2. Make badge `reset_schedule.start_date` / `end_date` the only persisted cycle source.
3. Reuse the existing midnight and startup recovery path to persist cycle catch-up before first reads.
4. Update the badge-progress sensor so inactive windows show `0%`, while historical award metadata stays visible.
5. Extend schema45 cleanup, rewrite the legacy tests to the new contract, and clear all platinum-quality gates.
