# Initiative Plan — Badge Streak Repair Service

## Initiative snapshot

- **Name / Code**: Badge Streak Repair — `BADGE_STREAK_REPAIR`
- **Origin**: issue #290 (`repair_streak` service). Scoped down from the original request — see
  "Scope decisions" below for what was deliberately excluded and why.
- **Target release / milestone**: next release, alongside the streak work from PRs #296 and #297.
- **Owner / driver(s)**: ChoreOps maintainer + ChoreOps Builder
- **Status**: Planned — not started
- **Branch / delivery**: `ccpk1/streak-repair`, off `main` after #297 merged (`7520470`, 2026-09-15).
  Single PR; the change is self-contained.

## Summary & immediate steps

| Phase | Description | % | Quick notes |
| --- | --- | --- | --- |
| 1 – Data layer | Per-day streak buffer on badge progress, pruned to 5 days; schema bump | 0% | First collection-valued field on badge progress |
| 2 – Service | `repair_streak` service + manager method, response-first | 0% | Mirrors `get_ledger` response pattern |
| 3 – Tests | New suite covering buffer, pruning, repair, response, auth | 0% | 7–9 tests |
| 4 – Docs | `services.yaml`, wiki, release note | 0% | `en.json` is the translation master |

1. **Objective** – give an admin a supported way to undo a broken badge streak, using a short
   retained history of the streak's own values rather than manual `.storage` editing.

2. **Why this shape.** The streak count is destroyed on a break, and badges keep no high-water mark.
   A small per-day buffer of recent counts both **retains the pre-break value** and **self-describes
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
   - **No configurable window.** Retention is the window: the buffer holds the last 5 days, and a
     break older than that simply has nothing to restore from. This removes the general-options
     setting, its validation, and the config plumbing entirely.

## Phase 1 – Data layer

- **Goal**: retain the last 5 days of each badge's streak count, and bump the schema.
- **Key facts established**: `SCHEMA_VERSION_CURRENT = SCHEMA_VERSION_1_5_0` (`const.py:354-355`);
  badge progress keys live at `const.py:1057-1068`; every existing badge-progress field is a scalar,
  so this is the first collection-valued one.
- **Steps**
  1. Add `DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: Final = "streak_history"` to `const.py`, with a
     comment stating the shape: `dict[str, int]` of **local** date key → streak count for that day.
  2. Add `STREAK_HISTORY_RETENTION_DAYS: Final = 5` with a note that this is the effective repair
     lookback, and that there is deliberately no user-facing setting for it.
  3. **Record the day's value** in the `days_cycle` evaluation path in
     `engines/gamification_engine.py` — the value must be recorded on **every** evaluation,
     including the break (where it writes the count that existed *before* zeroing), because
     recording only on advance would leave nothing to restore from.
     - Reference `dt_today_iso()` (`utils/dt_utils.py:149`) for the key. **Local date, never raw
       `datetime`** — same convention as the period buckets.
  4. **Prune** to the most recent 5 date keys on write, sorted by key (ISO dates sort correctly as
     strings).
  5. **Read defensively.** A missing, non-dict, or partially malformed buffer must degrade to an
     empty buffer rather than raising, so a corrupt value cannot break badge evaluation.
  6. **Schema bump**: add `SCHEMA_VERSION_1_5_3: Final = 153` and point `SCHEMA_VERSION_CURRENT` at
     it. The convention is `major*100 + minor*10 + patch` (`const.py:353-355`: 1.0.0 → 100,
     1.5.0 → 150), and the shipping release is 1.5.3. Migration is **non-destructive**: existing
     badge progress entries simply have no buffer, and the defensive read treats that as empty. No
     backfill — a history cannot be invented for days that were never recorded.
  7. Confirm the write path: badge progress is persisted via
     `coordinator._persist_and_update()` from `GamificationManager` (see existing calls at
     `managers/gamification_manager.py:487`, `:1125`).
- **Key issues**
  - **Retention is the only thing bounding the lookback.** Reducing retention later silently shortens
    the repair window, so it is a behaviour-affecting constant and should be treated as such.
  - Forward-only: the buffer accrues from install. A break that happens before the feature ships has
    nothing to restore from, which the service must report clearly rather than failing obscurely.

## Phase 2 – Service

- **Goal**: an admin-callable `choreops.repair_streak` that restores a badge streak, auto-filling
  from the retained history, and returns that history for reference.
- **Steps**
  1. **Constants**: `SERVICE_REPAIR_STREAK`, `SERVICE_FIELD_REPAIR_COUNT`, and `TRANS_KEY_*` for the
     service name, field labels, and errors.
  2. **Payload validator** in `services.py`, mirroring `_validate_manual_adjust_points_payload`
     (`services.py:129`): require exactly one of `user_id` / `user_name`; require `badge_name`.
     `count` is optional.
  3. **Manager method** on `GamificationManager` (only managers write). It owns the write and returns
     a plain dict for the response:
     - resolve the badge by name for the assignee; return a clear error if unknown or if the badge
       has no streak-carrying progress
     - `count` supplied → use it verbatim (no cap, per the scope decision)
     - `count` omitted → use the **highest value** in the retained buffer; if the buffer is empty,
       return an error explaining there is nothing to restore from
     - write `DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT = count`
     - **write `last_update_day = yesterday`** — this is the load-bearing detail. Yesterday, never
       today: the streak's own idempotency gate treats `last_update_day == today` as already
       counted, so today would *hold* instead of advancing. Yesterday also retroactively clears the
       miss, because the miss check anchors on this field.
     - persist via `coordinator._persist_and_update()`
     - return `{user, badge, restored_count, source ("manual"|"history"), history: [{date, count}]}`
  4. **Handler** in `services.py`, registered with `supports_response=SupportsResponse.OPTIONAL`
     (pattern already used at `services.py:1542`, `:3733`):
     - resolve entry id and assignee
     - **auth**: copy the real pattern —
       `await is_user_authorized_for_action(hass, user_id, AUTH_ACTION_MANAGEMENT)`, raising
       `HomeAssistantError` with a translation key on failure.
       ⚠️ **Do not use `async_register_admin_service`** — it is referenced in `AGENTS.md` but does
       not exist in this codebase.
     - call the manager, log at info with `reason` and actor, fire the event, request a refresh
     - return the dict
  5. **Event**: `choreops_streak_repaired`, carrying user, badge, count, source and reason, so
     households can build rules on top (the issue's "earn back your streak" automation).
  6. **Log line** with reason and actor, as the audit surface in place of a ledger entry.
  7. **`services.yaml`**: document the service with field descriptions and selectors, and state that
     it returns JSON when called with `return_response: true` — copy the wording style from
     `get_ledger` (`services.yaml:506`).
  8. **Translations**: add service and field labels to
     `custom_components/choreops/translations/en.json`. **There is no `strings.json` in this repo**,
     so `en.json` is the master and no regeneration step applies.
- **Key issues**
  - **`criteria_met` side effect.** Restoring above the threshold re-awards the badge on the next
    evaluation. Expected, but note it in the wiki so it is not reported as a bug.
  - **Achievement divergence is the accepted price.** A repaired badge streak will outpace an
    achievement or chore streak over the same chore. Documented, not fixed — repairing those is out
    of scope.
  - **`max()` across tracked chores** means a badge's streak need not match any single chore's, so
    the retained values are badge-level only.

## Phase 3 – Tests

- **Goal**: pin the buffer and the service contract, including the response.
- **Steps**
  1. New `tests/test_repair_streak.py`:
     - buffer records the day's count, keyed by local date
     - buffer prunes to 5 entries, dropping the oldest
     - the **pre-break value is retained** after a break (the core reason for this design)
     - repair with no `count` restores the highest retained value
     - repair with an explicit `count` uses it verbatim (including a value above the retained max,
       proving no cap)
     - repair sets `last_update_day` to yesterday, and today's evaluation then **advances**
     - empty buffer returns the "nothing to restore" error
     - unknown badge / unknown user refused
     - unauthorized caller refused
     - response contains `history` with date and value pairs
     - corrupt buffer (string, list, mixed types) degrades to empty and does not raise
  2. Confirm no regression in `test_badge_progress_persistence.py`,
     `test_badge_streak_schedule_awareness.py`, `test_gamification_engine.py`,
     `test_badge_target_types.py`.
- **Key issues**
  - Timezone: pin the default timezone with a `try/finally` restore (the established convention in
    `test_badge_period_end_cycles.py`), since buffer keys are local dates.
  - Any test asserting "2 days ago" must derive its keys from `dt_today_iso()` rather than hardcoding
    dates, or it will be weekday/clock dependent.
  - Verify non-vacuity for the retention assertion: a buffer that never prunes must fail it.

## Phase 4 – Docs

- **Goal**: make the service discoverable and the consequences explicit.
- **Steps**
  1. Wiki `Configuration:-Badges-Periodic.md`: a "Repairing a broken streak" section — what the
     service does, that it auto-fills from the last 5 days when `count` is omitted, that it can also
     set any value (no cap), that it needs an admin, and that restoring above the threshold re-awards
     the badge.
  2. Note the two accepted limitations: it is **badges only**, so achievements and chore streaks over
     the same chore are not affected; and a break older than the retention window has nothing to
     restore from.
  3. Refresh that page's `Last Updated` footer.
  4. Release note: one entry.
  5. PR description: record why the ledger was not used, why there are no guards, and why the
     scalar-plus-date alternative was rejected (it needs two fields and an invariant to answer
     "how long ago").

## Testing & validation

- **Targeted**: `python -m pytest tests/test_repair_streak.py tests/test_badge_progress_persistence.py tests/test_badge_streak_schedule_awareness.py tests/test_gamification_engine.py tests/test_badge_target_types.py -q --tb=line`
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
