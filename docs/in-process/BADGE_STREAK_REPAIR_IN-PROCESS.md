# Initiative Plan — Badge Streak Repair Service

## Initiative snapshot

- **Name / Code**: Badge Streak Repair — `BADGE_STREAK_REPAIR`
- **Origin**: issue #290 (which proposes a `repair_streak` service). Scoped down from the original
  request — see
  "Scope decisions" below for what was deliberately excluded and why.
- **Target release / milestone**: next release, alongside the streak work from PRs #296 and #297.
- **Owner / driver(s)**: ChoreOps maintainer + ChoreOps Builder
- **Status**: ✅ **Ready to implement** — all decisions settled (2026-09-15), no open questions.
- **Branch / delivery**: `ccpk1/badge-streak-repair`, off `main` after #297 merged (`7520470`,
  2026-09-15). Single PR; the change is self-contained.

## Summary & immediate steps

| Phase | Description | % | Quick notes |
| --- | --- | --- | --- |
| 1 – Data layer | Per-day streak history on badge progress, pruned to 5 days; schema bump + migration | 100% | ✅ Constants, helpers, write wiring, migration; mypy required a TypedDict key too |
| 2 – Service | `repair_badge_streak` service + manager method, response-first, fires an event | 0% | Mirrors `get_ledger` response pattern |
| 3 – Tests | New suite covering history, pruning, repair, response, auth | 0% | ~11 tests |
| 4 – Docs | `services.yaml`, wiki, release note | 0% | `en.json` is the translation master |
| 5 – Sensor | Expose the retained history as an attribute | 0% | Reuses an existing constant |

1. **Objective** – give an admin a supported way to undo a broken badge streak, using a short
   retained history of the streak's own values rather than manual `.storage` editing.

2. **Why this shape.** The streak count is destroyed on a break, and badges keep no high-water mark.
   A small per-day history of recent counts both **retains the pre-break value** and **self-describes
   when the break happened**, so the service can auto-fill the correct value and the lookback needs no
   companion date field. This replaced an earlier single-scalar design that could not answer
   "how many days ago was that".

3. **Scope decisions (confirmed with the maintainer, 2026-09-15)**
   - **Badges only.** Achievements derive their streak from the chore streak, and repairing a chore
     streak would mean falsifying `DATA_USER_CHORE_DATA_LAST_COMPLETED`, which five call sites read.
     Out of scope.
   - **No ledger entry.** The points ledger is economy-shaped (`amount`, `balance_after`,
     `POINTS_SOURCE_*`); a streak repair has no balance. Log + event are the audit surface instead.
   - **No caps and no guards.** No maximum on a supplied value, no repair-count budget, and no
     "streak must currently be broken" check. Admins decide how to use the service.
     **Accepted consequence, recorded deliberately:** with no guard the service can also raise a
     *live* streak, so it is a bounded setter in addition to a repair. This is intentional, not an
     oversight.
   - **No configurable window.** The history's own depth is the window: it holds the last 5 days, and a
     break older than that has nothing to restore from. This removes the general-options setting, its
     validation, and the config plumbing entirely.
     ⚠️ **Do not confuse this with the existing `retention_daily` setting.** `CONF_RETENTION_DAILY`
     (`const.py:820`, default 14, **max 90**) governs daily *period buckets* — the history behind
     stats and charts. It is unrelated to this history and must not be wired to it: at 90 days the
     repair lookback would be far longer than intended, and the two serve different purposes.
   - **History is NOT cleared on cycle rollover (confirmed 2026-09-15).** The retained entries simply
     age out on their own. The service reports the retained values, and the caller decides whether
     they are still meaningful for the current cycle — the same "let admins decide" principle applied
     to the missing guards. **Accepted consequence:** a repair *can* restore a pre-rollover value into
     a fresh cycle. That is the caller's call, not something the code second-guesses.
   - **No derived restore-value attribute (confirmed 2026-09-15).** The sensor exposes the retained
     history and nothing more; a caller wanting the maximum reads it themselves. Avoids inventing a
     derived field whose meaning could drift from the storage it summarises.

## Naming principle for this initiative

**The domain is badges. Every name is anchored on it, with the streak as the qualifier.**

This was corrected twice during review, from `SERVICE_FIELD_REPAIR_COUNT` (named the *action*) to
`SERVICE_FIELD_STREAK_COUNT` (named the *feature*), before landing on
`SERVICE_FIELD_BADGE_STREAK_COUNT` (names the *domain*). Both wrong versions were plausible, which is
exactly why the rule is written down: reach for the domain first, and treat the mechanism as the
qualifier.

| Surface | Name | Domain anchor |
| --- | --- | --- |
| Service action | `SERVICE_REPAIR_BADGE_STREAK` | badge |
| Service field | `SERVICE_FIELD_BADGE_STREAK_COUNT` | badge |
| Storage field | `DATA_USER_BADGE_PROGRESS_STREAK_HISTORY` | badge (existing namespace) |
| Lookback constant | `DEFAULT_BADGE_STREAK_HISTORY_DAYS` | badge |
| Event | `EVENT_BADGE_STREAK_REPAIRED` | badge |
| Manager method | `repair_badge_streak()` | badge |
| Initiative / file / branch | `BADGE_STREAK_REPAIR` | badge |

The existing codebase follows this already — `SERVICE_FIELD_BADGE_NAME`, and
`SERVICE_REMOVE_AWARDED_BADGES` where the object names the domain.

## Phase 1 – Data layer

- **Goal**: retain the last 5 days of each badge's streak count, and bump the schema.
- **Status**: ✅ **Complete** (2026-09-15). Gates green, no regressions.
- **Key facts established**: `SCHEMA_VERSION_CURRENT = SCHEMA_VERSION_1_5_0` (`const.py:354-355`);
  badge progress keys live at `const.py:1057-1068`; every existing badge-progress field is a scalar,
  so this is the first collection-valued one.
- **Steps**
  1. ✅ Add `DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: Final = "streak_history"` to `const.py`, with a
     comment stating the shape: `dict[str, int]` of **local** date key → streak count for that day.
     ✅ **Name validated** — matches the existing `DATA_USER_BADGE_PROGRESS_<NAME>` family with a
     `snake_case` value, and `DATA_*` is documented as singular storage keys (`const.py:1057-1068`).
     Place it in the existing alphabetical run, after `START_DATE` and before `STATUS`.
  2. ✅ Add `DEFAULT_BADGE_STREAK_HISTORY_DAYS: Final = 5`, following the `CONF_*` +
     `DEFAULT_*` pairing the codebase already uses for exactly this purpose
     (`CONF_RETENTION_DAILY` + `DEFAULT_RETENTION_DAILY`, `const.py:820` / `:1846`).
     - Use **`DEFAULT_*`, not a bare noun**, precisely because this value may become user-configurable
       later. The standards describe `DEFAULT_*` as "Default configuration values", which is exactly
       the intent here and signals the value is overridable rather than fixed behaviour.
     - When it does become configurable, the change is adding `CONF_BADGE_STREAK_HISTORY_DAYS` and a
       read of `options.get(CONF_..., DEFAULT_...)` at the one read site. **A pure addition — no
       rename.**
     - Deliberately not `..._RETENTION_DAYS`, so it cannot be confused with the unrelated
       `CONF_RETENTION_DAILY` (different subsystem, max 90).
     - Add a comment recording that it is simultaneously the storage window and the repair lookback.
  2b. ✅ **Keep the number out of identifier names.** The value governs how much history is kept, but it
     must not be embedded in logic or function names — otherwise changing 5 to 7 becomes a rename
     cascade. Required names:
     - `record_badge_streak_history(progress, count, today_iso)`
     - `prune_badge_streak_history(progress, max_days)`
     - `get_badge_streak_history(progress)`
     - ❌ Avoid `prune_five_day_history`, `lookback_5`, `MAX_5_DAYS`, or anything else encoding the
       current value.

  3. ✅ **Record the day's value** in the `days_cycle` branch of the badge persistence path
     (`managers/gamification_manager.py:2006-2029`) — recorded on **every** evaluation, including the
     break, because recording only on advance would leave nothing to restore from.
     - ✅ **Mechanism verified from code.** The pre-break value is recoverable at break time: the
       branch reads `previous_days` before overwriting, then sees `days_count = 0` differ, so the
       count that existed *before* zeroing is in scope exactly when the break is written.
     - ⚠️ **Trap: do not gate recording on the existing change check.** That branch writes only when
       `previous_days != days_count`. A **neutral day** leaves the count unchanged, so the guard
       would skip it — but the day still needs its own date key, or the history has gaps and the
       "days ago" arithmetic silently misleads. Compare against **the stored value for `today_iso`**
       (absent, or different) rather than against `previous_days`.
     - Reference `dt_today_iso()` (`utils/dt_utils.py:149`) for the key. **Local date, never raw
       `datetime`** — same convention as the period buckets.
  4. ✅ **Prune** to the most recent 5 date keys on write, sorted by key (ISO dates sort correctly as
     strings).
  5. ✅ **Read defensively.** A missing, non-dict, or partially malformed history must degrade to an
     empty history rather than raising, so a corrupt value cannot break badge evaluation.
  6. ✅ **Schema bump — CORRECTED 2026-09-15 after standards review.** Add
     `SCHEMA_VERSION_1_5_3: Final = 153` and point `SCHEMA_VERSION_CURRENT` at it. The convention
     is `major*100 + minor*10 + patch` (`const.py:353-355`: 1.0.0 → 100, 1.5.0 → 150), and the
     shipping release is 1.5.3.
     ⚠️ **An explicit migration step IS required — the earlier "non-destructive, no step needed"
     wording was wrong.** `DEVELOPMENT_STANDARDS.md` §3 states that a change introducing a new
     durable storage contract with a schema bump belongs in `migrations/`, and
     `migrations/modern.py` says outright: *"The first post-1.0.0 schema bump should add explicit
     ordered steps here."* This **is** that first bump.
     - Add an **idempotent, re-runnable** step to `run_modern_schema_migrations`
       (`migrations/modern.py:16`) that initialises `streak_history` to `{}` on every badge
       progress entry lacking it. Idempotency is a stated requirement of that function, so
       re-running must be safe.
     - It is dispatched from `SystemManager` (`managers/system_manager.py:262`) and gated on
       `schema_version < SCHEMA_VERSION_CURRENT` (`coordinator.py:364`).
     - The `integrity/` lane does **not** apply: that lane is for impossible runtime states on an
       already-current schema, not for introducing a new key.
     - No backfill of values — a history cannot be invented for days that were never recorded.
  7. ✅ Confirm the write path: badge progress is persisted via
     `coordinator._persist_and_update()` from `GamificationManager` (see existing calls at
     `managers/gamification_manager.py:487`, `:1125`).
- **Key issues**
  - **Buffer depth is the only thing bounding the lookback.** It is a hardcoded constant, independent
    of `CONF_RETENTION_DAILY`, and changing it later silently changes the repair window — so it is a
    behaviour-affecting constant and should be treated as such.
  - Forward-only: the history accrues from install. A break that happens before the feature ships has
    nothing to restore from, which the service must report clearly rather than failing obscurely.
- **Implementation notes (Phase 2 deviations)**
  1. **`examples` in `en.json` must be strings.** Adding `"example": 42` for the numeric count
     field broke **33 tests across four suites** with `TypeError: expected str, got int` — an error
     that pointed nowhere near the cause. Every other service example in that file is a string, and
     this was the only non-string one. Converted to `"42"`. **Worth remembering: the type of a
     translation `example` is load-bearing, and a wrong one fails indirectly.** Integers are fine in
     `services.yaml` (precedented by `create_reward`'s `cost: 50`).
  2. **The assignee resolver was reused, not renamed.** `_resolve_manual_adjust_assignee_id` handles
     the generic "exactly one of user_id / user_name, validated against assignees_data" case. It has
     a single caller and a name tied to that caller, so it is now used by two services while keeping
     the old name. Left as-is rather than renamed mid-feature; a rename to something
     caller-agnostic would be a tidy-up worth doing separately.
  3. **`get_item_id_by_name` was imported rather than `get_item_id_or_raise`.** The raising variant
     produces an untranslated `HomeAssistantError`, whereas this service raises with the proper
     `TRANS_KEY_ERROR_NOT_FOUND` plus the badge label, so the user sees a translated message.

- **Implementation notes (Phase 1 deviations, for reference)**
  1. **The helpers are static methods on `GamificationManager`, not module-level functions.** The plan
     implied free functions, but that module contains no module-level functions — everything is a
     method — and `data_builders.py` is scoped to entity lifecycle/build rather than runtime progress.
     Static methods keep them colocated with `_persist_periodic_badge_progress` while staying pure and
     directly testable. Same names as planned.
  2. **`record_badge_streak_history` returns `bool`.** Not in the plan, but needed so the caller can
     set the `changed` flag that drives persistence.
  3. **What gets recorded is the day's *actual* count, including `0` on a break** — not the pre-break
     value. The plan's phrasing ("the count that existed before zeroing is in scope") was imprecise.
     The pre-break value survives because *the previous day's entry is still there* and ages out on its
     own, which is exactly what bounds the lookback. Verified by tracing: a streak of 100 recorded over
     four days, then a break recorded as `0`, yields `max = 100`; four restart days later the 100 has
     rolled off and `max = 4`. Recording the pre-break value under today's key would misrepresent the
     day and break the natural expiry.
  4. **Mypy required a `type_defs.py` change the plan missed.** `AssigneeBadgeProgress` is a TypedDict
     and rejected the new key: *"has no key `streak_history`"*. That contract is precisely why the
     project uses TypedDicts, so the field was added there with its shape documented. **Worth noting
     the plan did not anticipate this file.**
## Phase 2 – Service

- **Goal**: an admin-callable `choreops.repair_badge_streak` that restores a badge streak,
  auto-filling
  from the retained history, and returns that history for reference.
- **Status**: ✅ **Complete** (2026-09-15). Gates green, 357 targeted tests pass.
- **Steps**
  1. ✅ **Constants** — VALIDATED against `DEVELOPMENT_STANDARDS.md` §3 and existing patterns
     (2026-09-15). Most of the fields this service needs **already exist**, so the new-constant
     surface is far smaller than first assumed:
     - ✅ **Already exist, reuse — do not create:** `SERVICE_FIELD_USER_ID` / `SERVICE_FIELD_USER_NAME`
       (`const.py:3064-3065`), `SERVICE_FIELD_BADGE_NAME` (`:3186`), `SERVICE_FIELD_REASON`,
       `SERVICE_FIELD_APPROVER_NAME`. These match the documented `SERVICE_FIELD_*`"Service input
       field names" pattern, and `manual_adjust_points` uses the same set.
     - **Create:** `SERVICE_REPAIR_BADGE_STREAK: Final = "repair_badge_streak"` — the established
       service pattern is `<VERB>_<OBJECT>`, with the object naming the **domain**
       (`SERVICE_REMOVE_AWARDED_BADGES = "remove_awarded_badges"`). The domain here is badges, and the
       streak is the qualifier, so `repair_streak` would name the feature instead of the domain.
     - **Create:** `SERVICE_FIELD_BADGE_STREAK_COUNT: Final = "badge_streak_count"` — the pattern is
       `SERVICE_FIELD_<DOMAIN>_<SEMANTIC>` (`SERVICE_FIELD_BADGE_NAME = "badge_name"`,
       `SERVICE_FIELD_POINTS_AMOUNT`, `SERVICE_FIELD_CHORE_NAME`), so the domain leads and `_COUNT`
       disambiguates that it is a number rather than the streak itself.
       **Corrected twice:** first from `SERVICE_FIELD_REPAIR_COUNT` (named the action) and then from
       `SERVICE_FIELD_STREAK_COUNT` (named the feature). Both mistakes came from reaching for the
       mechanism instead of the domain.
     - `TRANS_KEY_*` for the service name, field labels and errors.
  2. ✅ **Payload validator** in `services.py`, mirroring `_validate_manual_adjust_points_payload`
     (`services.py:129`): require exactly one of `user_id` / `user_name`; require `badge_name`.
     `count` is optional.
  3. ✅ **Manager method** on `GamificationManager` (only managers write), named
     `repair_badge_streak(...)` to stay anchored on the badge domain like the rest of the surface. It
     owns the write and returns a plain dict for the response:
     - **Naming note:** the method takes `assignee_id`, matching its neighbours in that manager
       (`get_badge_scoped_today_stats`, `_get_tracked_current_streak`) and the mutation pattern in
       `economy_manager.deposit(assignee_id=...)`. `DEVELOPMENT_STANDARDS.md` reserves `user` naming
       for *lifecycle records*; badge progress is per-user data like points, and the service
       boundary already uses `user_name` / `user_id`. Flagged because the standard and the
       surrounding code differ, and following the neighbours is the consistent choice.
     - resolve the badge by name for the assignee; return a clear error if unknown or if the badge
       has no streak-carrying progress
     - `count` supplied → use it verbatim (no cap, per the scope decision)
     - `count` omitted → use the **highest value** in the retained history; if the history is empty,
       return an error explaining there is nothing to restore from
     - write `DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT = count`
     - **write `last_update_day = yesterday`** — ✅ **mechanism verified from code.**
       `already_counted_today = (last_update_day == today_iso)` (`gamification_engine.py:1309`), and
       when it is False the satisfied day takes `cycle_count + 1` (`:1171`). So yesterday makes today
       **advance**; today would make it **hold** at the restored value, which is the bug this avoids.
       Yesterday also retroactively clears the miss, because `has_missed_occurrence_since_advance`
       anchors on this field, leaving an empty `[yesterday, today)` window.
       - The persist path then re-stamps `last_update_day = today_iso` on the advance
         (`gamification_manager.py:2023-2027`), so the anchor moves forward normally afterwards.
     - persist via `coordinator._persist_and_update()`
     - return a dict following the `get_ledger` response convention (`services.py:3712-3728`):
       `assignee_id` / `assignee_name` naming, plus `restored_count`, `source`
       (`"manual"|"history"`) and `history` — a list of date/value pairs. Reuse existing `DATA_*`
       constants for keys (as `get_ledger` does with `DATA_USER_INTERNAL_ID` / `DATA_USER_NAME`)
       rather than inventing bare string keys.
  4. ✅ **Handler** in `services.py`, registered with `supports_response=SupportsResponse.OPTIONAL`
     (pattern already used at `services.py:1542`, `:3733`):
     - resolve entry id and assignee
     - **auth**: copy the real pattern —
       `await is_user_authorized_for_action(hass, user_id, AUTH_ACTION_MANAGEMENT)`, raising
       `HomeAssistantError` with a translation key on failure.
       ⚠️ **Do not use `async_register_admin_service`** — it is referenced in `AGENTS.md` but does
       not exist in this codebase.
     - call the manager, log at info with `reason` and actor, fire the event, request a refresh
     - return the dict
  5. ✅ **Event** — `hass.bus.async_fire(const.EVENT_BADGE_STREAK_REPAIRED, {...})`.
     - **Not a new pattern.** An earlier revision called this "the integration's first HA event needing
       its own convention", which overstated it. Firing a bus event is entirely standard Home
       Assistant; this integration simply has not needed one yet. Verified the split:
       `async_dispatcher_send` is used 4 times with 68 `SIGNAL_SUFFIX_*` constants for **internal**
       component communication, while `async_fire` is used 0 times. No project standard documents
       events either, so there is no convention to invent — HA's own `<domain>_<event_name>` applies,
       giving `EVENT_BADGE_STREAK_REPAIRED = "choreops_badge_streak_repaired"`.
     - The only genuine consideration is the usual one for any public API: once households build
       automations on it, the name and payload become a contract. That is a reason to get the payload
       right, not a reason to avoid it.
     - Carries user, badge, count, source and reason, so the "earn back your streak" automation works.
  6. ✅ **Log line** with reason and actor, as the audit surface in place of a ledger entry.
  7. ✅ **`services.yaml`**: document the service with field descriptions and selectors, and state that
     it returns JSON when called with `return_response: true` — copy the wording style from
     `get_ledger` (`services.yaml:506`).
  8. ✅ **Translations**: add service and field labels to
     `custom_components/choreops/translations/en.json`. **There is no `strings.json` in this repo**,
     so `en.json` is the master and no regeneration step applies.
  9. (Phase 5) **Expose the retained history on the badge progress sensor** — add
     `DATA_USER_BADGE_PROGRESS_STREAK_HISTORY` to the attributes dict in
     `AssigneeBadgeProgressSensor.extra_state_attributes` (`sensor.py:2369`). No new constant: this
     sensor already exposes stored fields under their `DATA_*` keys (see decision 3 in the open
     questions).
- **Key issues**
  - **`criteria_met` side effect.** Restoring above the threshold re-awards the badge on the next
    evaluation. Expected, but note it in the wiki so it is not reported as a bug.
  - **Achievement divergence is the accepted price.** A repaired badge streak will outpace an
    achievement or chore streak over the same chore. Documented, not fixed — repairing those is out
    of scope.
  - **`max()` across tracked chores** means a badge's streak need not match any single chore's, so
    the retained values are badge-level only.

## Phase 3 – Tests

- **Goal**: pin the history and the service contract, including the response.
- **Steps**
  1. New `tests/test_repair_badge_streak.py`:
     - history records the day's count, keyed by local date
     - history prunes to 5 entries, dropping the oldest
     - the **pre-break value is retained** after a break (the core reason for this design)
     - repair with no `count` restores the highest retained value
     - repair with an explicit `count` uses it verbatim (including a value above the retained max,
       proving no cap)
     - repair sets `last_update_day` to yesterday, and today's evaluation then **advances**
     - empty history returns the "nothing to restore" error
     - unknown badge / unknown user refused
     - unauthorized caller refused
     - response contains `history` with date and value pairs
     - corrupt history (string, list, mixed types) degrades to empty and does not raise
  2. Confirm no regression in `test_badge_progress_persistence.py`,
     `test_badge_streak_schedule_awareness.py`, `test_gamification_engine.py`,
     `test_badge_target_types.py`.
- **Key issues**
  - Timezone: pin the default timezone with a `try/finally` restore (the established convention in
    `test_badge_period_end_cycles.py`), since history keys are local dates.
  - Any test asserting "2 days ago" must derive its keys from `dt_today_iso()` rather than hardcoding
    dates, or it will be weekday/clock dependent.
  - Verify non-vacuity for the pruning assertion: a history that never prunes must fail it.

## Phase 4 – Docs

- **Goal**: make the service discoverable and the consequences explicit.
- **Steps**
  1. Wiki `Configuration:-Badges-Periodic.md`: a "Repairing a broken streak" section — what the
     service does, that it auto-fills from the last 5 days when `count` is omitted, that it can also
     set any value (no cap), that it needs an admin, and that restoring above the threshold re-awards
     the badge.
  2. Note the two accepted limitations: it is **badges only**, so achievements and chore streaks over
     the same chore are not affected; and a break older than the history's 5-day depth has nothing to
     restore from.
  2b. Document the `choreops_badge_streak_repaired` event and its payload, so the "earn back your
     streak" automation pattern is reproducible, and mention the `streak_history` sensor attribute
     as where to read the retained values.
  3. Refresh that page's `Last Updated` footer.
  4. Release note: one entry.
  5. PR description: record why the ledger was not used, why there are no guards, and why the
     scalar-plus-date alternative was rejected (it needs two fields and an invariant to answer
     "how long ago").

## Settled decisions

All decisions are closed as of 2026-09-15. Nothing blocks implementation.

### Scope

| Decision | Settled as | Rationale |
| --- | --- | --- |
| Coverage | **Badges only** | Achievements derive from the chore streak; repairing a chore streak means falsifying `last_completed`, which five call sites read |
| Caps / guards / budget | **None** | Admins decide how to use it. The service can therefore also raise a live streak — intentional, documented |
| Lookback window | **5 days**, `DEFAULT_BADGE_STREAK_HISTORY_DAYS` | Buffer depth *is* the window; named `DEFAULT_` so promoting it to user-configurable is a pure addition |
| Ledger entry | **No** | The points ledger is economy-shaped and would not fit; log + event are the audit surface |
| Event | **Yes**, `EVENT_BADGE_STREAK_REPAIRED` | Standard HA feature, not a new pattern; the "earn back your streak" automation needs it |
| Cycle rollover | **Leave history alone** | Entries age out on their own; the service reports them and the caller decides. A repair *can* restore a pre-rollover value — accepted as the caller's call |
| Sensor attribute | **`DATA_USER_BADGE_PROGRESS_STREAK_HISTORY`**, existing constant | This sensor already exposes stored fields under their `DATA_*` keys; no new constant needed |
| Derived restore value | **Not added** | Sensor reports stored data; a caller wanting the max reads it, keeping the two from drifting |
| Cycle-rollover clearing | **None** | See above |

### Implementation choices

| Question | Settled as |
| --- | --- |
| Manager method owner | `GamificationManager`, named `repair_badge_streak(...)` — it owns badge progress, so it owns the write. Service stays a thin delegate |
| Response includes retention depth? | **Yes** — cheap, and it keeps consumers off the constant |
| Non-streak badge | **Refuse** with a clear behavioural error ("this badge does not track a streak"), not a target-type constant |
| `criteria_met` on restore above threshold | **No special-casing** — the badge re-awards on the next evaluation. Documented in the wiki so it is not reported as a bug |
| `changed` semantics for the history write | Set only when `today_iso` is absent from the history or its value differs — **not** inherited from the `previous_days != days_count` check, which would skip neutral days (Phase 1 step 3) |

### Verified, not assumed

- **`last_update_day = yesterday` advances today** — `already_counted_today = (last_update_day == today_iso)` (`gamification_engine.py:1309`); a satisfied day then takes `cycle_count + 1` (`:1171`). Today would *hold* instead.
- **The pre-break value is in scope at break time** — the `days_cycle` persist branch reads `previous_days` before overwriting (`gamification_manager.py:2006-2029`).
- **Naming and migration** — see the naming principle and Phase 1 step 6.
- **Auth pattern** — `is_user_authorized_for_action(..., AUTH_ACTION_MANAGEMENT)`. `async_register_admin_service` does **not** exist in this repo despite `AGENTS.md` referencing it.

## Implementation sequence

Ordered so each commit is independently reviewable and revertable. Phase 1 must land before Phase 2, since the service reads the history.

| Commit | Scope | Files |
| --- | --- | --- |
| 1 | Data layer — constants, record/prune/read helpers, wiring into the persist branch | `const.py`, `gamification_manager.py`, `migrations/modern.py` |
| 2 | Service — constants, validator, manager method, handler, event, `services.yaml`, translations | `const.py`, `services.py`, `gamification_manager.py`, `services.yaml`, `translations/en.json` |
| 3 | Sensor attribute | `sensor.py` |
| 4 | Tests — new suite plus the regression set | `tests/test_repair_badge_streak.py` |
| 5 | Docs — wiki, release note | `choreops-wiki` (direct push) |

**Definition of done**: `quick_lint.sh --fix` green (ruff + mypy 0 errors + boundary checks), new suite passing, prior badge/gamification suites unregressed, and the **full suite** run before the PR — the schema bump and a new write on the evaluation path justify it.

## Testing & validation

- **Targeted**: `python -m pytest tests/test_repair_badge_streak.py tests/test_badge_progress_persistence.py tests/test_badge_streak_schedule_awareness.py tests/test_gamification_engine.py tests/test_badge_target_types.py -q --tb=line`
- **Release gates**: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, then the full
  suite — the schema bump and a new write on the evaluation path justify a full run.
- **Outstanding tests**: none yet; Phase 3 defines them.

## Notes & follow-up

- **Explicitly out of scope**, recorded so the decisions are not relitigated:
  - pause preserving a streak (separate product question; the docs currently contradict each other
    on it — a cheap standalone fix)
  - repairing chore streaks or achievements
  - a badge high-water mark ("best ever")
  - any ledger or break-log surface
- **Cheap follow-up identified during analysis**: expose the retained value as an attribute on
  `AssigneeBadgeProgressSensor` (`sensor.py:2205`). Retained state is *current* state, so it is
  readable on the entity without depending on recorder history — unlike the existing
  `overall_progress` state, which saturates at 100% and is therefore uninformative for exactly the
  long streaks this feature targets.
