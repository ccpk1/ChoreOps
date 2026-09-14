# Initiative Plan — Badge Streak Schedule Awareness (Issue #294 follow-on)

## Initiative snapshot

- **Name / Code**: Badge Streak Schedule Awareness — `BADGE_STREAK_SCHEDULE_AWARENESS`
- **Target release / milestone**: next release after 1.5.3 — the #294 hotfix and this initiative ship
  **together in one release** (decided 2026-09-14). From the user's perspective this is one bug
  ("streak badges don't work"); the analysis just found several distinct defects behind it.
- **Owner / driver(s)**: ChoreOps maintainer + ChoreOps Builder (ChoreOps Test Builder for Phase 4)
- **Status**: In progress — Phase 0 committed; Phases 1–5 not started
- **Branch / delivery**: `ccpk1/issue294` carries both the #294 hotfix and this initiative, which
  ship as a single release. Keep the phases as **separate commits** regardless — reviewers follow
  commit history, and the hotfix commit (`73e97d5`) doubles as a bisect point if the wider change
  later needs backing out.

## Summary & immediate steps

| Phase / Step                                            | Description                                                                   | % complete | Quick notes                                                        |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------ |
| Phase 0 – Prerequisite (#294 hotfix)                    | Land the calendar-midnight streak fix so this defect becomes observable        | 100%       | ✅ Committed `73e97d5` (3 files, +499/−6)                           |
| Phase 1 – Schedule-aware day classification (data layer) | Surface due-chore scope and schedule-derived miss signal in the stats snapshot | 0%         | `statistics_manager.py` + `type_defs.py`; miss check is a backstop only |
| Phase 2 – Streak semantics in the engine                | Neutral days hold; break/resume driven by missed occurrences, not calendar gaps | 0%         | `gamification_engine.py::_evaluate_streak` only                     |
| Phase 3 – Persistence & status alignment                | Ensure neutral days write nothing and status transitions stay coherent         | 0%         | `gamification_manager.py` days_cycle bucket + status transition      |
| Phase 4 – Tests & validation                            | Extend the #294 regression suite; add schedule-matrix coverage                  | 0%         | Reuses the day-replay harness built for #294                        |
| Phase 5 – Docs, wiki & release notes                    | Document "eligible occurrence" streak semantics across all three streak systems | 0%         | Wiki + Development Standards + release note                         |

1. **Key objective** – Make badge streak target types count **consecutive satisfied eligible occurrences** instead of consecutive calendar days, so a streak respects each tracked chore's schedule. A badge must not break (or stall) on a day when the tracked chores are simply not due, and must never award from a gap where an occurrence genuinely passed unmet.

2. **Summary of recent work** –
   - **#294 root cause found and fixed** (`ccpk1/issue294`): `_evaluate_streak` treated every unmet day as a break, and the nightly midnight evaluation runs on a brand-new day with zero approvals, so `days_cycle_count` was reset to 0 every night. All streak target types with a threshold above 1 were unreachable. Fix: hold while the day is still in progress; break only once a full day passes unmet. Regression suite added at `tests/test_badge_streak_midnight_reset.py` (6 tests; 3 failed before the fix).
   - **This defect was previously masked by #294.** With every streak being zeroed nightly, a schedule-driven stall was invisible.
   - **Verified divergence across three streak systems**: chore-level streaks have been schedule-aware since `139fc40` (Jan 2026, via `RecurrenceEngine.has_missed_occurrences`); completion-streak achievements inherit that via `_get_tracked_current_streak` (`7ead4da` / #171); **badge streak target types never were**. This is a consistency defect, not a missing feature.
   - **Impact verified by walking real schedules** (see "Verified evidence"):
     `Streak: Selected Chores Completed` (100%) cannot accumulate in any household that has a
     non-daily chore, **even at 100% compliance**.

3. **Next steps (short term)** –
   1. Resolve decision 8 (which families the "chores that count today" fix covers) — it gates Phase 1.
   2. Resolve decision 9 (picker duplicates) — it is smaller but affects Phase 5 docs.
   3. Start Phase 1.

4. **Risks / blockers** –
   - **Sequencing**: the original plan required the #294 hotfix to land first. Both now live on
     `ccpk1/issue294` and ship in one release, with the hotfix isolated in `73e97d5` so reviewers
     can follow it separately.
   - **`missed_since_advance` is easy to get wrong in three specific ways** (all now pinned in
     the Phase 1 contract below): the upper bound must be the **start of today**, or today's
     still-pending occurrence reads as a miss and breaks streaks mid-day; the lower bound must be
     **clamped** to the upper bound, or an already-completed chore yields an inverted interval;
     and the anchor must be **`last_update_day`, not the chore's `last_completed`**, or a chore
     added to the scope mid-streak reports a spurious miss.
   - **Check ordering is load-bearing.** The miss check must run **before** the advance branch. If
     it runs after, a day that meets its criteria advances even though an earlier occurrence was
     missed.
   - **Behaviour change risk (Days family).** `streak_yesterday` is shared by `_resolve_daily_status`,
     so touching the denominator there silently affects `_evaluate_daily_completion` too. If
     decision 8 is "streaks only", the change must be made per-evaluator, not in the shared
     helper.
   - **Behaviour change risk**: users currently holding a badge cannot lose it (badges are never
     removed), but in-progress streak counts may legitimately rise, and some Days badges may
     become markedly easier to earn. Expect support questions.
   - **Semantic risk**: switching the day denominator from "all tracked chores" to "eligible
     today" makes the scope of `Streak: Selected Chores …` and `Streak: Selected Due Chores …`
     converge, so two of the five streak options become redundant (three distinct behaviours
     remain — see decision 9). Intended, but it must be documented or it reads as a regression.
   - **Retention risk**: daily period buckets are pruned (`DEFAULT_RETENTION_DAILY = 14`). The
     design must therefore **not** walk daily period history to detect misses; it uses schedule
     math on completion timestamps (see Decisions).
   - **never_overdue risk**: lateness timestamps (`last_missed` / `last_overdue`) are never written
     when overdue handling is disabled, so a miss-detection strategy based on those flags alone
     would let a streak survive indefinitely while nothing is done. The chosen signal avoids this.
   - **Performance**: `has_missed_occurrences` builds an rrule per chore. The snapshot is rebuilt
     per badge in `_build_target_runtime_context`, so cost is badges × tracked chores ×
     evaluations. Short-circuit on the first miss. Note the check cannot be skipped on neutral days
     (see the contract), so there is no "cheap path" for a dormant badge — profile if a household
     has many badges over many chores.

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — data model, storage, schema checkpoints
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — constants, logging, signal rules
   - [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) — Phase 0 audit framework
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) — §2 Quality gates
   - Existing regression suite: `tests/test_badge_streak_midnight_reset.py` (#294)
   - Prior art to reuse: `ChoreEngine.calculate_streak` (`engines/chore_engine.py:1431`), `RecurrenceEngine.has_missed_occurrences` (`engines/schedule_engine.py:194`)
   - Related issues: #294 (fixed — streak never accumulates), #290 (repair/freeze service — this plan removes most of its motivation), #293 / #295 (cycle-scoped lateness), #171 (achievement streak decay)

6. **Decisions & completion check**
   - **Decisions captured**:
     1. **Streak unit = eligible occurrence, not calendar day.** A day on which no tracked chore is
        eligible is *neutral*: it neither advances nor breaks the streak. Consecutive occurrences
        extend the streak (Mon→Wed→Fri = 3). This matches the documented intent of the chore-level
        system (`has_missed_occurrences` docstring: *"Weekly Monday: last=Jan 6, current=Jan 13 →
        False (consecutive Mondays)"*), so all three streak systems converge on one definition.
     2. **Eligible today = due today** (reusing the existing `_is_chore_due_today_for_assignee`,
        which already handles per-assignee due dates and dateless dailies). Chores that are
        overdue-but-not-due-today are **out of scope for non-strict variants** — lateness is
        surfaced through `has_overdue` / `cycle_failed`, which remain gated behind
        `require_no_overdue` (strict modes). Rationale: keep the existing strict/non-strict
        contract intact; the strict variants are the documented "survival check" modes.
     3. **Miss detection uses schedule math on completion timestamps**, via the tested `RecurrenceEngine.has_missed_occurrences` primitive, **not** lateness flags and **not** daily period history. Rationale: works regardless of overdue-handling configuration (the `never_overdue` case), is retention-independent, and reuses a shipped, unit-tested implementation (`test_schedule_engine_streaks.py`).
     4. **Neutral days never advance the streak** — only days where at least one tracked chore is eligible can advance it. Prevents a long dormant stretch (e.g. a monthly chore) from inflating the count.
     5. **No storage schema bump expected.** The design reuses `days_cycle_count`, `last_update_day` and existing completion timestamps. `SCHEMA_VERSION_CURRENT` (150) stays unchanged. A bump becomes necessary only if the fallback design (Option B below) is chosen.
     6. **CONFIRMED — neutral-gap ceiling: unbounded.** An indefinite stretch of neutral days keeps
        a streak alive. Days where nothing is due neither advance nor break the streak, with no
        ceiling and no `streak_max_gap_days` setting in v1. Revisit only if a real report appears.
        Consequence to document: a monthly chore's badge measures consecutive *occurrences*, so a
        streak can span many calendar weeks.
     7. **CONFIRMED — no migration of legacy in-progress counts.** `days_cycle_count` values
        accumulated under calendar-day semantics are left as-is; all changes are forward-only. The
        counter self-corrects from the next advance. No backfill, no schema bump, no repair pass.
     8. **NEEDS DECISION — how far should the fix reach?**

        Restated plainly: the defect described in the primer is not streak-specific. It affects the
        non-*Due* options in **both** families. The question is whether the fix is applied to both
        families (one rule everywhere) or only to streaks (the narrow reported bug).

        - **(a) Streaks only.** Repair only `Streak: …` targets. The `Days: …` targets keep their
          current behaviour: the 100% variants stall on any day a selected chore is not due, and
          the 80% variants advance by coincidence. Smaller, more surgical diff; the "chores that
          count today" rule then differs between two families that look identical in the picker.
        - **(b) Both families (recommended).** One rule — *a chore counts today only if it is due
          today* — applied once and consumed by both the streak and the days evaluators.

        **What (b) changes for an existing user:**

        - Badge scoped to chores that are **all daily** — **no change**, because everything is due
          every day.
        - Badge scoped to **mixed frequencies** — the badge becomes **easier**, because days the
          weekly chore is absent can now qualify. Concrete: 10 mixed chores, only 3 due today, all
          3 done. Today that scores 3/10 = 30%, so the day does not count; after (b) it scores
          3/3 = 100%, so the day counts. That is the *intended* meaning ("of what was actually
          available"), but badges configured under the old reading will visibly progress faster.
        - The "Days Minimum 3/5/7 Chores" options also change scope: "3 chores" becomes "3 of the
          chores due today" rather than "3 of any selected chores".

        **Recommendation: (b).** The two families are the same feature reading the same label
        pattern, and they already share the day-status helper. Fixing streaks alone leaves the
        identical stall in place for `Days` badges. The cost is a one-time easing of mixed-scope
        badges, which the release note should call out explicitly.

     9. **NEEDS DECISION — keep the now-duplicate options in the picker?**

        Restated plainly: once "selected chores" means "selected chores due today" (decision 8),
        the word *Due* in the option names no longer distinguishes anything, so some options
        measure exactly the same thing. The streak family has five options today:

        | Today's option | What it measures today | After the fix |
        | --- | --- | --- |
        | Streak: Selected Chores Completed | 100% of all selected | 100% of due — **still distinct**, no duplicate exists |
        | Streak: 80% of Selected Chores Completed | 80% of all selected | 80% of due — **duplicate** of the next one |
        | Streak: 80% of Selected Due Chores Completed | 80% of due | unchanged |
        | Streak: Selected Chores Completed (No Overdue) | 100% of all selected, no overdue | 100% of due, no overdue — **duplicate** of the next one |
        | Streak: Selected Due Chores Completed (No Overdue) | 100% of due, no overdue | unchanged |

        So **two** options become redundant, leaving **three** genuinely distinct behaviours: 100%,
        80%, and 100% with no-overdue. Note there is deliberately no plain "100% of due chores"
        option today — after the fix the first row becomes exactly that, which is a useful
        behaviour that previously had no way to be expressed.

        (If decision 8 is (b), the `Days` family collapses further: it has both a 100%-selected
        *and* a 100%-due option today, so **three** pairs become redundant — six options down to
        three. The "Days Minimum 3/5/7 Chores" options also shift scope to "of the chores due
        today".)

        There is **no migration risk either way**: each badge stores its chosen target type
        internally, and both spellings keep resolving, so hiding options only changes what new
        badges can pick.

        - **(a) Leave all five options in place (recommended).** Describe the equivalence in the
          option help text so users can pick either. Keeps the picker stable through an upgrade
          that is already changing badge behaviour, and keeps the diff focused on semantics.
        - **(b) Remove the redundant options now.** Cleaner picker immediately, but bundles a UI
          change into a behavioural fix and makes the change harder to review and justify.

        **Recommendation: (a)**, because there is no correctness cost to the duplicates once they
        are documented, and consolidating is safe to do in any later release.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update.

## Tracking expectations

- **Summary upkeep**: Refresh the Summary section after each significant change — updated percentages, new blockers, completed steps, with dates or commit references.
- **Detailed tracking**: Use the phase sections below for granular progress, decisions and issues. Keep the Summary high level.

---

## Background & root cause (verified analysis, 2026-09-14)

### Three streak systems diverged

| System                                        | Schedule-aware? | Evidence                                                                                 |
| --------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------- |
| Chore streak (`chore_current_streak`)         | ✅ since `139fc40` | `ChoreEngine.calculate_streak` → `has_missed_occurrences` (`chore_engine.py:1431`, `:1530`) |
| Achievement (`COMPLETION_STREAK`)             | ✅ inherits      | `_get_tracked_current_streak` + `_streak_alive` (`gamification_manager.py:2871`, `:2890`)  |
| **Badge streak target types**                 | ❌ never         | `GamificationEngine._evaluate_streak` counts calendar days                                 |

### Three independent root causes

> **Framing correction (2026-09-14, after contract review):** cause 2 is the **primary** cause of
> the advance failure; cause 1 is what makes the day satisfiable in mixed scopes; cause 3 is what
> makes the break detectable once neutral days are allowed to hold. All three must be fixed
> together — fixing only the denominator turns the observed "reset to 1" into a different wrong
> answer (see the reference implementation note).

1. **Non-due chores count against the percentage.** `get_badge_scoped_today_completion`
   (`statistics_manager.py:2534`) computes `total_count` over every tracked chore when
   `only_due_today=False`. A weekly chore that is not due today scores as "not approved"
   permanently, so a 100% threshold is unreachable and mixed scopes stall.
2. **Advancing requires a literal calendar-yesterday.** `streak_yesterday`
   (`statistics_manager.py:2462`) compares `last_update_day == yesterday`. Because a neutral day
   cannot advance, `last_update_day` stays put, so the very next eligible day fails the
   "yesterday" test and the streak restarts at 1 instead of continuing. No gap longer than one
   day can ever resume.
3. **No notion of a neutral day or of a missed occurrence.** A day with nothing scheduled is
   indistinguishable from a failed day. Once neutral days are allowed to hold (a required part of
   the fix), the break can no longer be inferred from staleness and must be detected explicitly —
   otherwise a streak never breaks after a failed occurrence followed by a neutral day.

### Verified evidence (after the #294 hold fix)

**Single Mon/Wed/Fri chore, child never misses a due date:**

```
Mon done → 1   Tue not due → hold 1   Wed done → 1  (NO advance)
Thu not due → 0  (BREAK)   Fri done → 1
```

**Default scope: 4 daily chores + 1 weekly due Monday, all dailies completed every day**
(threshold 10 on a badge scoped to all 5 chores):

```
Streak: Selected Chores Completed (100%)  Mon:1  Tue:1  Wed:0  Thu:0  Fri:0  Sat:0  Sun:0
Streak: 80% of Selected Chores (80%)      Mon:1  Tue:2  Wed:3  Thu:4  Fri:5  Sat:6  Sun:7
```

The 100% variant can never accumulate in any household containing a non-daily chore, even at 100%
compliance — it advances on Monday, cannot advance on Tuesday (the weekly is not due), and breaks
on Wednesday. The 80% variant works only incidentally: 4/5 = 80% clears the threshold on days the
weekly is absent, so calendar continuity happens to hold.

### Target semantics (reference implementation for Phase 2)

```
Inputs per badge:
  due_count / approved_due_today  # eligible scope for today              (NEW)
  missed_since_advance: bool      # occurrence passed unmet since the last advance (NEW)
  days_cycle_count                # existing
  already_counted_today           # existing (last_update_day == today_iso)

Precedence (ORDER IS LOAD-BEARING):
  1. strict (require_no_overdue) and lateness present -> break (0)
  2. missed_since_advance                             -> break (0)
  3. due_count == 0                                   -> neutral: hold
  4. criteria met and already_counted_today           -> hold (idempotent)
  5. criteria met                                     -> advance (count + 1)
  6. otherwise                                        -> hold (day still in progress)
```

Two deliberate consequences:

- **Advancing no longer requires `streak_yesterday`.** Continuity is proven by the *absence* of
  a missed occurrence since the last advance, which is what makes resume-across-neutral-gaps
  correct. Removing only the gate is not enough — without rule 2 the streak would then never
  break, which is why the miss signal and the gate removal are one change.
- **Rule 2 must precede rule 5.** If the miss check runs after the advance branch, a day that
  meets its criteria advances even though an earlier occurrence was missed.

### `missed_since_advance` contract (Phase 1)

For each badge, over its tracked chores, evaluate:

```
lower = last_update_day at local start-of-day     # the streak's own anchor
upper = start_of_today_local
if lower is unset or lower >= upper: no miss      # fresh badge, or already advanced today

for each tracked chore (short-circuit on the first hit):
    if RecurrenceEngine(chore schedule).has_missed_occurrences(lower, upper):
        -> miss
```

Rationale for each choice — all three are traps if guessed:

- **Anchor on the badge's `last_update_day`; do not consult the chore's `last_completed`.** A
  satisfied day always advances the streak and therefore moves the anchor, so occurrences
  belonging to already-evaluated days fall *before* it and cannot break the streak. Using
  `max(anchor, last_completed)` instead would *lose* a genuine miss: Monday satisfied (anchor
  moves to Monday), Tuesday skipped, Wednesday completed — the completion would raise the lower
  bound past the skipped Tuesday occurrence and the break would never register.
  This anchor choice is also what makes the percentage tolerance work automatically: on a day met
  at 80%, the streak advances, the anchor moves, and the deliberately-skipped chore's occurrence
  is excluded. No special-casing of partial variants is needed. It equally stops a chore added to
  the scope mid-streak (with an old `last_completed`) from reporting a spurious miss.
- **Upper bound is the start of today, not "now".** Otherwise today's still-pending occurrence
  counts as missed and the streak breaks mid-day — reintroducing the #294 symptom in a new form.
- **No window means no miss.** When the anchor is unset (fresh badge, first evaluation) or already
  equals today, there is nothing to evaluate. Anchoring a new badge to its cycle start date
  instead would let pre-enrolment history break it, so "unset ⇒ no miss" is the deliberate choice.

Because of the anchor, the miss check is a **backstop for windows that were never evaluated**
(HA down, catch-up gaps, neutral stretches after a failed occurrence). A day that was evaluated
is handled by the day-level rules, and its occurrence cannot resurface.

Consequence to accept and document: a missed occurrence breaks the streak on the **following**
day, because on the missed day itself the occurrence has not yet passed. This is the same
one-day-later latch as #294 and is inherent — a day in progress is indistinguishable from a
missed day until it ends.

Fail safe: a missing or unparseable `last_update_day` must yield "no miss", so a valid streak is
never wrongly zeroed — the same convention as `_streak_alive`
(`gamification_manager.py:2871`).

Evaluation order note: the check **cannot** be made conditional on the day being non-neutral, even
though it is only consulted for one outcome. The decisive case is a missed occurrence followed by
a neutral day: Monday's occurrence goes unsatisfied, Tuesday has nothing due, and only the miss
check can break the streak on Tuesday — the neutral-hold rule (3) would otherwise keep it alive
indefinitely. This is exactly why rule 2 precedes rule 3. The only safe skip is `lower >= upper`
(no window). If profiling makes the eager rrule cost a problem, the fallback is to short-circuit
per chore on the first miss, not to defer the whole check.

### Badge target type primer (read this before the decisions)

When you create a badge you pick a **target type** from a list. Three things about that list
matter here:

**1. "Days" vs "Streak" — accumulating versus consecutive.**

- A **"Days …"** target counts *how many days* met the criteria during the badge's cycle. It
  accumulates: a missed day does not reset it. "Days Selected Chores Completed" with a threshold
  of 5 means *"complete all selected chores on 5 days"*, not necessarily in a row.
- A **"Streak: …"** target counts *how many days in a row* met the criteria. It resets to 0 the
  moment a day is missed. The same wording with a streak prefix means *"5 days in a row"*.

That reset behaviour is the whole reason "Streak" badges were the reported bug: the counter can
be destroyed by a single bad day, so it is far more sensitive to a mis-classified day than the
"Days" family.

**2. "Selected Chores" vs "Selected Due Chores" — the scope.**

- **"Selected Chores"** (no *Due*) is meant to score every chore you selected for the badge.
- **"Selected Due Chores"** scores only those that are due *today*.

**3. The defect lives in the non-*Due* variants.** They score every selected chore, including
chores that are **not due today**. A chore that is not due today cannot be completed today, so it
sits in the day's score as a permanent failure. For a badge scoped to a mix of daily and weekly
chores, that makes some days impossible to satisfy. Worked example with 4 daily chores and 1
weekly chore due Saturday, badge scoped to all 5, on a Tuesday where the 4 dailies are done:

| Target type | What the day scores | Outcome |
| --- | --- | --- |
| Days 100% (selected) | 4/5 = 80% | day cannot count; the badge only advances on Saturdays |
| Days 80% (selected) | 4/5 = 80% | day counts — but only because the threshold was low enough to absorb the absent chore |
| Streak 100% (selected) | 4/5 = 80% | day cannot count, **and the streak resets** — the reported bug |
| any "Due" variant | 4/4 = 100% | correct today |

The fix is to make "selected" mean "selected **and due today**" everywhere. That single change is
what decisions 8 and 9 are about.

---

## Detailed phase tracking

### Phase 0 – Prerequisite (#294 hotfix)

- **Goal**: Land the calendar-midnight fix so the schedule defect becomes observable and the two changes are reviewed separately.
- **Steps / detailed work items**
  1. ✅ Engine fix in `_evaluate_streak` — hold while the day is in progress, plus the mandatory strict-mode break branch (`engines/gamification_engine.py:1134-1159`).
  2. ✅ Repurpose `test_streak_breaks_when_today_fails` into `test_streak_holds_while_today_is_still_in_progress` + `test_streak_breaks_after_a_full_day_without_completion` (`tests/test_gamification_engine.py`).
  3. ✅ Add `tests/test_badge_streak_midnight_reset.py` (6 tests) including a partial-progress case.
  4. ✅ Commit the hotfix in isolation — `73e97d5` on `ccpk1/issue294` (not pushed). It ships in
     the same release as this initiative; the separate commit exists so the hotfix stays
     reviewable on its own and can be bisected to.
- **Key issues**
  - Phases 1–3 must not be folded into the hotfix commit; it is a 1-file behavioural correction
    and must stay a distinct, reviewable change.
  - The PR description should note that the hotfix is expected to surface schedule-related streak
    reports, since it removes the masking defect (see Background).

### Phase 1 – Schedule-aware day classification (data layer)

- **Goal**: Give the engine everything it needs to classify a day, without touching streak maths yet.
- **Precondition**: decision 8 must be resolved first, because it determines whether the
  denominator is replaced in the shared `_resolve_daily_status` or only in the streak path.
- **Steps / detailed work items**
  1. Add `due_count` and `approved_due_today` to the completion snapshot returned by
     `get_badge_scoped_today_completion` (`managers/statistics_manager.py:2534`). Reuse the
     existing `_is_chore_due_today_for_assignee` (`:2632`) — do not add a second schedule check —
     and set both from the same loop that already tracks `total_count` / `approved_count`.
  2. Add `missed_since_advance: bool` to the same snapshot, implemented to the **`missed_since_advance`
     contract** above. Mirror the schedule-config assembly already in `ChoreEngine.calculate_streak`
     (`engines/chore_engine.py:1500-1528`) for `frequency` / `interval` / `applicable_days` /
     `daily_multi_times`. Extract that assembly into one shared builder rather than copying it —
     see the drift precedent in Notes.
  3. Implement the **`missed_since_advance` contract** above exactly. The contract fixes the
     ordering (it must run before the neutral hold), the anchor, the upper bound and the skip
     condition; none of those are free choices. Only the *placement* is open: compute it eagerly in
     the snapshot, or expose enough for the engine to compute it. If eager, short-circuit on the
     first missed chore.
  4. Fail safe on a missing or unparseable `last_completed` / `last_update_day` — treat as
     "no miss". Mirror the `_streak_alive` convention (`managers/gamification_manager.py:2871`).
  5. Declare the new keys in the snapshot contract in `type_defs.py` (see the `today_completion` /
     `today_completion_due` fields around `type_defs.py:900`) so the engine reads them from a
     typed surface rather than an untyped `dict[str, Any]`.
  6. Add focused unit tests for each new key in isolation: `due_count` with mixed schedules;
     `approved_due_today`; miss detection for daily / weekly / `never_overdue`; and one test per
     contract trap (start-of-today upper bound, clamping, anchor-over-`last_completed`, chore
     added mid-scope).
- **Key issues**
  - **Purity/layering**: `schedule_engine` lives in `engines/`, and this code lives in a manager,
     which may import engines. Verify with the boundary checker rather than assuming.
   - **Loop cost**: only evaluate tracked chores, short-circuit on the first miss. The check cannot
     be skipped on neutral days (see the contract's ordering note) — that restriction is a
     correctness requirement, not a performance choice.
  - `has_missed_occurrences` takes UTC datetimes; the snapshot is ISO-date based. Convert
     explicitly with the `dt_*` helpers (`utils/dt_utils.py`) — never raw `datetime`.
  - The shared schedule-config builder must not change `calculate_streak`'s behaviour; pin that
     with the existing `test_workflow_streak_schedule.py` suite.

### Phase 2 – Streak semantics in the engine

- **Goal**: Implement the target semantics in `_evaluate_streak` only.
- **Steps / detailed work items**
  1. Extend `_resolve_daily_status` (`engines/gamification_engine.py:1278`) to surface `due_count`, `approved_due_today` and `missed_since_advance` alongside the existing keys, keeping the `dict[str, Any]` contract.
  2. Rewrite the decision block in `_evaluate_streak` (`:1134-1159`) to the reference implementation precedence, in that exact order: strict break → **missed break** → neutral hold → idempotent hold → advance → in-progress hold.
  3. Replace the literal calendar gate: the advance branch must no longer read `streak_yesterday`. Continuity is carried by rule 2 instead. Leave the `streak_yesterday` key in place (see Key issues) but stop consuming it on the streak path.
  4. Change the day denominator to the eligible scope (`due_count` / `approved_due_today`) so non-due chores stop counting against non-due-filtered variants. Keep the `only_due_today=True` path behaviourally identical — after this change both scopes resolve to the same denominator, which is intended; add a comment stating why the two variants converge.
  5. Update the docstring to define an eligible occurrence, a neutral day and a missed occurrence, and replace the now-misleading `streak_yesterday` context requirement line with the new contract.
  6. Update the `reason` string so a neutral day is self-explanatory (it must not render as `0/7 consecutive days` on a day with nothing due), and so a neutral-hold is distinguishable from an in-progress hold when debugging.
- **Key issues**
  - `streak_yesterday` remains in the context because `_resolve_daily_status` is shared with `_evaluate_daily_completion`. Do **not** remove it ungated; per decision 8 it is either kept for the Days path or removed from both deliberately.
  - `criteria_met` must not be recomputed in a way that lets a neutral day flip an already-earned criteria state.
  - **Do not change the denominator inside the shared helper unless decision 8 is (b).** If decision 8 is (a), the eligible scope must be applied in `_evaluate_streak` only, or the Days family changes silently.
  - Verified today: the Days family holds rather than breaks on a non-due day (`Days` type returned 3), so it is **not** broken the way streaks were — it stalls and can over-count. That is a correctness matter, not a release blocker, which is why decision 8 can be taken either way.

### Phase 3 – Persistence & status alignment

- **Goal**: Keep the write path consistent with the new semantics.
- **Steps / detailed work items**
  1. Audit the `days_cycle` branch of `_persist_periodic_badge_progress` (`managers/gamification_manager.py:1986-2004`) against the neutral-day and hold paths, and assert that a neutral day writes nothing (count unchanged, `last_update_day` untouched). Correct only if the audit finds a write.
  2. Confirm the break path writes `0` **and** leaves `last_update_day` un-advanced. Under the new
     semantics that staleness is no longer the break *mechanism* — it is the miss check's anchor.
     Leaving it stale means the missed occurrence keeps being detected until the streak restarts
     (which then stamps a fresh anchor and clears the condition). Verify both halves; if a future
     change starts stamping `last_update_day` on a break, the miss check would go blind.
  3. Review `_resolve_target_status_transition` (`:1237`) and `_is_periodic_award_recorded_for_current_cycle` (`:1285`) for neutral-day edge cases: confirm no re-award occurs on a neutral day and that `in_progress` / `active_cycle` transitions remain coherent.
  4. Verify `_advance_non_cumulative_badge_cycle_if_needed` cannot reset `days_cycle_count` on a day that Phases 1–2 classified as neutral.
  5. Add a persistence-level test asserting a neutral day produces zero writes (compare the progress dict before/after).
- **Key issues**
  - Badges are never removed; a stale high streak must not be re-awarded. Reuse the existing award guards rather than adding new ones.
  - Cumulative badges must stay untouched by this initiative.

### Phase 4 – Tests & validation

- **Goal**: Lock the semantics with a schedule matrix, and prove no regression in the existing suites.
- **Steps / detailed work items**
  1. Extend `tests/test_badge_streak_midnight_reset.py` with the `StreakDayReplay` harness already built for #294. Two harness changes are required:
     - add a `neutral` helper (a day where the tracked chore is not due) so the harness can express the new classification; and
     - seed `DATA_USER_CHORE_DATA_LAST_COMPLETED` alongside the daily period buckets. The current harness only writes period data, so the miss check would see no completions at all and every day would read as missed.
  2. **Re-express the two existing break-semantics guards** (`TestStreakStillBreaks`). They currently seed `last_update_day` and rely on the calendar gate to break. Under the new mechanism the break comes from the miss check, so they must be updated to drive it through schedule/completion data — otherwise they pass vacuously and stop guarding anything. Do not delete or weaken them; the intent (a genuinely missed day still breaks; a broken streak restarts at 1) is exactly the guarantee this change must preserve.
  3. Extend `TestStreakSurvivesInProgressDay` with the neutral-day case: seed an intact streak, evaluate a day where nothing is due, assert the count is unchanged **and** `last_update_day` is unchanged (proving the hold is a true no-op, not a re-stamp).
  4. Add `tests/test_badge_streak_schedule_awareness.py` covering the matrix: Mon/Wed/Fri (`applicable_days`), weekly with a rescheduled due date, biweekly, custom-interval, monthly, and a mixed daily+weekly badge. Assert: neutral days hold; consecutive occurrences advance; a genuinely missed occurrence breaks; a gap with no missed occurrence resumes.
  5. Add the regression case that motivated this plan: **4 daily chores + 1 weekly due Monday, all dailies done every day → `streak_all_chores` reaches the threshold** (currently caps at 1 with a break). Cover both the partial-progress and full-day orderings, since the advance path previously reset to 1.
  6. Add the contract-trap tests, one per trap named in Phase 1 step 6, and the `never_overdue` case explicitly: skipping a due occurrence must still break the streak (the case a lateness-flag design gets wrong).
  7. Parametrize across retention settings (including a low `retention_daily`) to prove the design does not depend on period history surviving.
  8. Run the targeted suites, then the badge/gamification set, then the release-gate commands from [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) §2: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, `python -m pytest tests/ -v --tb=line`.
- **Key issues**
  - Timezone correctness: the scheduling layer stores UTC while day keys are local. Follow the established convention in `tests/test_badge_period_end_cycles.py` (explicit `set_default_timezone` with `try/finally`) rather than relying on the default zone.
  - The full suite is a release step, not a CI gate — validate broadly before release, since cross-test state (the `dt_utils` default-timezone module global) can only appear in a full run.
  - Do not weaken the two existing break-semantics guards (`TestStreakStillBreaks`) to make new cases pass.

### Phase 5 – Docs, wiki & release notes

- **Goal**: Make the unified streak definition discoverable and explain the behaviour change.
- **Steps / detailed work items**
  1. Update the wiki to state that a streak counts consecutive **eligible occurrences**, that days
     where nothing is due are neutral, and that this applies to chore streaks, achievements and
     badges alike. Use the target type labels users see in the picker ("Streak: Selected Chores
     Completed"), not the internal constants:
     - `choreops-wiki/Configuration:-Chores.md`
     - `choreops-wiki/Advanced:-Chores.md` (already corrected for #294 — extend with the occurrence rule)
     - `choreops-wiki/Configuration:-Badges-Periodic.md` (add a streak-semantics section next to the existing cycle-alignment section, plus the primer's worked example)
     - `choreops-wiki/Configuration:-Achievements.md`
  2. Document the two confirmed semantic decisions where users will look for them: that an
     unbounded stretch of neutral days keeps a streak alive (decision 6), and that legacy
     in-progress counts are not migrated (decision 7). Both are update-visible behaviour, so a
     short "what changed" note belongs in the periodic-badges page.
  3. If decision 9 is "leave the options as-is", state the equivalence of
     `streak_*_chores` / `streak_*_due_chores` in the target-type descriptions so users can pick
     the better-named option themselves.
  4. Update the badge target-type descriptions in `custom_components/choreops/translations/en.json`
     so `streak_*_chores` reads as "eligible today", then regenerate the English file with
     `python3 -m script.translations develop --integration choreops` (tests read
     `translations/en.json`, not `strings.json`).
  5. Add the streak definition to [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) so future
     work does not reintroduce calendar-day counting — including the `missed_since_advance`
     contract and its three traps, which are the easiest part of this design to re-break.
  6. Draft the release note describing the behaviour change: in-progress streak counts may rise;
     badges already held are unaffected; some Days badges may be easier to earn (if decision 8 is (b)).
  7. Update `docs/ARCHITECTURE.md` for the shared schedule-config builder introduced in Phase 1.
- **Key issues**
  - Wiki is a separate repository with no PR flow (commit directly to `choreops-wiki` `master`).
  - Any new user-facing string must be a `TRANS_KEY_*` constant in `const.py`; the engine's `reason` strings are existing English f-strings and stay internal, so no new translation key is expected — confirm during implementation.

---

## Testing & validation

- **Commands (per phase, targeted):**
  - `python -m pytest tests/test_badge_streak_midnight_reset.py tests/test_gamification_engine.py -v`
  - `python -m pytest tests/test_badge_target_types.py tests/test_badge_no_overdue_cycles.py tests/test_badge_period_end_cycles.py tests/test_workflow_streak_schedule.py tests/test_gamification_streak_reset.py tests/test_schedule_engine_streaks.py -v`
- **Commands (release gate):**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- **Baseline established for #294 (commit `73e97d5`):** new suite 6/6 pass; `test_gamification_engine.py` + `test_gamification_streak_reset.py` 64 pass; 7 badge/gamification suites 113 pass / 4 skip; `quick_lint.sh` green (ruff + mypy + 13 boundary checks). Phase 4 must not regress these.
- **Outstanding tests:** none yet — Phase 4 defines the matrix.
- **Links to failing logs:** n/a.

---

## Notes & follow-up

### Opportunities surfaced during contract review

1. **Extract one shared schedule-config builder.** The `frequency` / `interval` / `applicable_days`
   / `daily_multi_times` assembly exists in `ChoreEngine.calculate_streak` and would be needed a
   second time for the miss check. This codebase has already been bitten by duplicated scheduling
   math — period-end calculation lived in both `dt_utils` and `RecurrenceEngine`, drifted, and
   needed a parity test to pin it. Extracting one builder in Phase 1 avoids repeating that, and
   Phase 1 already includes the parity step (`test_workflow_streak_schedule.py` must stay green).
2. **`_streak_alive` and `missed_since_advance` are the same question** ("is this streak still
   alive?") answered for two different systems. `_streak_alive` is the cheap calendar
   approximation used by achievement streaks; `missed_since_advance` is the schedule-accurate
   version. Once it exists, achievement streaks could adopt it and gain the same correctness.
   Out of scope here — noted so the duplication is a conscious choice.
3. **The equivalence of the streak options is a documentation opportunity, not just a risk.**
   Describing `Streak: 80% of Selected Chores Completed` and `Streak: 80% of Selected Due Chores
   Completed` as equivalent lets users migrate to the better-named option at their leisure, which
   makes a later picker consolidation safe rather than disruptive. Related: after the fix,
   `Streak: Selected Chores Completed` becomes "100% of the chores due today, overdue tolerated" —
   a useful behaviour that has no option today, so the fix also *adds* a capability.
4. **`days_cycle_count` is not exposed on the badge progress sensor** (verified: `sensor.py`
   surfaces `status`, `overall_progress`, `criteria_met`, `last_update_day`). Anyone diagnosing a
   streak currently cannot see the counter. Consider exposing it while streak semantics are in
   flux — it would have made #294 self-evident and would make this change verifiable in the field.

### Other notes

- **Relationship to #290 (`repair_streak`)**: this plan removes most of #290's motivation. Its two stated causes were (a) a single missed day killing the streak, and (b) pause/sick days not being exempt. After this initiative, days with nothing to do are neutral, and the remaining #290 case is narrower: a genuinely missed occurrence being excused after the fact. The repo memory note for #290 concluded it should **not** proceed before #294; the same applies here. Do not start #290 in parallel.
- **Fallback design (Option B) — do not take without a reason.** Instead of deriving misses from schedule math, persist a per-badge "last eligible occurrence" anchor and a `previous_cycle_count` on break. This is simpler in the engine but requires a schema bump, depends on retention for history lookups, and still fails the `never_overdue` case if implemented from lateness flags. Documented only so the choice in Phase 2 is an informed one.
- **Not in scope:** cumulative badge maintenance; the "Days" target family; challenge evaluation (disabled during sunset); the per-chore notification and dashboard grouping paths.
- **Known adjacent issue (not scheduled):** a `never_overdue` chore whose due date goes stale (`never_overdue` + daily + pending leaves a past due date that never advances) interacts with the "eligible today" rule. Phase 4 step 4 pins the streak behaviour; if the stale-due-date behaviour itself needs changing, it belongs in its own initiative.
- **Memory artefacts:** the verified #294 root cause, the #294 fix, and this schedule-divergence finding are recorded in `/memories/repo/badge-streaks.md`. Keep that file current as phases land so the finding is not re-derived.
