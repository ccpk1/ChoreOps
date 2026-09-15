# Initiative Plan — Badge Streak Schedule Awareness (Issue #294 follow-on)

## Initiative snapshot

- **Name / Code**: Badge Streak Schedule Awareness — `BADGE_STREAK_SCHEDULE_AWARENESS`
- **Target release / milestone**: next release after 1.5.3 — the #294 hotfix and this initiative ship
  **together in one release** (decided 2026-09-14). From the user's perspective this is one bug
  ("streak badges don't work"); the analysis just found several distinct defects behind it.
- **Owner / driver(s)**: ChoreOps maintainer + ChoreOps Builder (ChoreOps Test Builder for Phase 4)
- **Status**: ✅ **Phases 0–5 shipped** — PR [#296](https://github.com/ccpk1/ChoreOps/pull/296) merged to
  `main` on 2026-09-15 as `0c98fdc`. Phase 6 work is on `ccpk1/streak-subsystem-unification`.
  All decisions resolved (17 total). **Phase 6 is split into two tranches** (see the Phase 6 section):
  Tranche A (O4/O5, code hygiene) can start now; Tranche B (O3/C3, achievement behaviour) waits for
  the field confirmation the entry criteria require. **Issue #122 was investigated and closed — it is
  out of scope**, see the record in the Phase 6 section.
- **Branch / delivery**: `ccpk1/issue294` carries both the #294 hotfix and this initiative, which
  ship as a single release via PR #296 against `main`. The phases are **separate commits** so
  reviewers can follow the history, and the hotfix commit (`73e97d5`) doubles as a bisect point if
  the wider change later needs backing out. The PR is a **draft** because the full-directory test
  run has not been executed yet — note that CI runs only `lint-validation` and HACS validation, so
  pytest is a manual pre-merge gate. Wiki docs were pushed directly to `choreops-wiki` `master`
  (that repo has no PR flow).

## Summary & immediate steps

| Phase / Step                                            | Description                                                                   | % complete | Quick notes                                                        |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------ |
| Phase 0 – Prerequisite (#294 hotfix)                    | Land the calendar-midnight streak fix so this defect becomes observable        | 100%       | ✅ Committed `73e97d5` (3 files, +499/−6)                           |
| Phase 1 – Snapshot fields (data layer)                   | Surface due-chore scope and schedule-derived miss signal in the stats snapshot | 100%       | ✅ `due_count`, `approved_due_today`, `missed_since_advance` + shared builder; 19 new tests |
| Phase 1B – Eligible scope must mean "counts toward today" (O1) | Legitimacy-aware scope so rotation/standby assignees are not charged | 100%       | ✅ Claim-mode deny-list; 18 new tests; closes conflict C1              |
| Phase 1C – Single missed-occurrence authority (O2)       | One helper for "was an occurrence missed between X and Y"                      | 100%       | ✅ `has_missed_occurrence_between`; 27 new tests; closes O2          |
| Phase 2 – Evaluator semantics (both families)           | Streaks: neutral days hold, break/resume by missed occurrence. Both: eligible-day scope | 100%       | ✅ Motivating case now works end to end; restart gate added (see below) |
| Phase 3 – Persistence & status alignment                | Ensure neutral days write nothing and status transitions stay coherent         | 100%       | ✅ Audit clean; 9 tests; fixed lost credit for a satisfied day after a break |
| Phase 4 – Tests & validation                            | Extend the #294 regression suite; add schedule-matrix + days-family coverage    | 100%       | ✅ 24 new tests; step 7 exposed and closed a decision-11 implementation gap |
| Phase 5 – Docs, wiki & release notes                    | Document eligible-occurrence semantics, option equivalence, and the behaviour change | 100%       | ✅ Wiki (4 pages), help text, Development Standards, Architecture, release-note draft |
| Phase 6A – Code hygiene (O4/O5)                         | Retire `streak_yesterday`; delete the dead calendar streak API                 | 0% | ✅ Unblocked — mechanical, no product decision needed |
| Phase 6B – Achievement alignment (O3/C3)                | Achievements adopt the shared helper; settle open-ended streak semantics        | 0% | ⛔ Blocked — needs decisions 18–20 **and** field confirmation of the badge fix |

1. **Key objective** – Make badge streak target types count **consecutive satisfied eligible occurrences** instead of consecutive calendar days, so a streak respects each tracked chore's schedule. A badge must not break (or stall) on a day when the tracked chores are simply not due, and must never award from a gap where an occurrence genuinely passed unmet.

2. **Summary of recent work** –
   - **#294 root cause found and fixed** (`ccpk1/issue294`): `_evaluate_streak` treated every unmet day as a break, and the nightly midnight evaluation runs on a brand-new day with zero approvals, so `days_cycle_count` was reset to 0 every night. All streak target types with a threshold above 1 were unreachable. Fix: hold while the day is still in progress; break only once a full day passes unmet. Regression suite added at `tests/test_badge_streak_midnight_reset.py` (6 tests; 3 failed before the fix).
   - **This defect was previously masked by #294.** With every streak being zeroed nightly, a schedule-driven stall was invisible.
   - **Verified divergence across three streak systems**: chore-level streaks have been schedule-aware since `139fc40` (Jan 2026, via `RecurrenceEngine.has_missed_occurrences`); completion-streak achievements inherit that via `_get_tracked_current_streak` (`7ead4da` / #171); **badge streak target types never were**. This is a consistency defect, not a missing feature.
   - **Impact verified by walking real schedules** (see "Verified evidence"):
     `Streak: Selected Chores Completed` (100%) cannot accumulate in any household that has a
     non-daily chore, **even at 100% compliance**.
   - **Phase 1 complete** (`69335e5`, 2026-09-14): `due_count`, `approved_due_today` and
     `missed_since_advance` now available on the completion snapshot; `build_schedule_config`
     extracted as one shared builder; `BadgeScopedCompletionSnapshot` TypedDict added so mypy
     enforces the contract (it caught four unenforced call sites during implementation). 19 new
     tests. **No evaluator behaviour changed** — all existing badge/gamification suites pass
     unmodified, which is the evidence that Phase 1 stayed a pure data-layer change.
   - **Placement decision recorded**: the miss check is computed **eagerly in the snapshot**, not
     deferred to the evaluator. The manager already holds `coordinator.chores_data`, and this
     avoids leaking schedule-building into the pure engine.

3. **Next steps (short term)** –
   1. ✅ Decisions 8–11 confirmed (2026-09-14).
   2. ✅ Phase 1 complete — data layer in place, no evaluator behaviour changed.
   3. ✅ Post-Phase-1 audit found four conflicts (C1–C4) and five unification opportunities.
   4. ✅ Decisions 12 (O1) and 13 (O2) added to the critical path; 14 (O3/O4/O5) deferred to Phase 6.
   5. ✅ Phase 1C complete — one missed-occurrence authority shared by chore and badge streaks.
   6. ✅ Phase 2 complete — eligible scope live in both evaluators; the motivating regression is
      fixed end to end.
   7. ✅ Phase 3 complete — write path audited clean; neutral days write nothing; a satisfied day
      after a break now starts a new streak instead of earning no credit.
   8. ✅ **Phase 4 complete** — 24 new tests across the schedule matrix, Days-family scope, contract
      traps and retention independence. One implementation gap was found and closed (decision 17).
   9. ✅ **Phase 5 complete and PR #296 opened (draft)** — wiki (4 pages), option help text,
      Development Standards, Architecture, and a release-note draft now in the PR description.
   10. ✅ **Phases 0–5 shipped** — PR #296 merged to `main` (`0c98fdc`, 2026-09-15).
   11. ✅ **Issue #122 investigated and closed** — a streak day-boundary is a convention with no
       generally correct answer, and the day boundary is not even consulted by the miss check. Full
       evidence kept in the Phase 6 section. **Out of scope.**
   12. **Next: Phase 6A (O4 + O5)** — retire `streak_yesterday` and delete the dead
       `StatisticsEngine.update_streak` / `get_streak` pair. Both are mechanical and need no product
       decision.
   13. **Then Phase 6B (O3 + C3), after decisions 18–20 are answered** — and only once the badge fix
       has been confirmed in the field, per the entry criteria.

4. **Risks / blockers** –
   - **BLOCKER (C1) — the eligible scope is currently too coarse.** `_is_chore_due_today_for_assignee`
     is schedule-only, so a rotation or primary-standby chore reads as owed by **every** assigned
     assignee while only the turn holder (or a window-permitted standby) can complete it. Phase 2
     must not ship before Phase 1B, or the fix introduces a new unfair-break vector. Detail under
     "Conflicts found during Phase 1 review".
   - **KNOWN LIMITATION (C2) — achievement streaks still break on non-daily schedules.**
     `_streak_alive` gates on a literal today-or-yesterday calendar window and zeroes a valid
     weekly-chore streak (verified: Monday completion ⇒ 0 on Wednesday). Users cannot distinguish
     the two systems, so this is stated as a known limitation in the achievements wiki page and in
     the merged release note rather than left silent. Closed by **Phase 6B / O3**.
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
   - **Behaviour change, both families (decision 8 confirmed).** Badges scoped to mixed-frequency
     chores become easier to earn, because days the non-daily chore is absent now qualify. Badges
     scoped to all-daily chores are unaffected. This is accepted and must be in the release note;
     the concrete numbers are in decision 8.
   - **Semantic risk (decision 9 confirmed as "leave in place").** The *Due* and non-*Due*
     spellings converge, so two streak options and three days options become redundant. No options
     are removed, so nothing breaks — but the picker will look like it offers more choice than it
     does until the help text explains the equivalence in Phase 5.
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
        **⚠️ SUPERSEDED IN PART by decision 12** — schedule-alone eligibility is too coarse and
        wrongly includes rotation chores for non-turn assignees (conflict C1). The overdue/missed
        half of this decision stands; the "due today" half is replaced by
        **counts toward today's obligation**.
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
     8. **CONFIRMED — the fix covers BOTH families (Days and Streak).** Decided 2026-09-14.
        One rule — *a chore counts today only if it is due today* — is applied once and consumed by
        both the streak evaluator and the days evaluator. Rationale: the two families share the
        day-status helper and the identical defect; fixing streaks alone would leave `Days` badges
        stalling and invite the same bug report later.

        **Accepted consequences (must appear in the release note):**
        - Badges scoped to chores that are **all daily**: **no change**.
        - Badges scoped to **mixed frequencies** become **easier**, because days the weekly chore
          is absent can now qualify. Concrete: 10 mixed chores, only 3 due today, all 3 done —
          today scores 3/10 = 30% (day does not count); after the change it scores 3/3 = 100%
          (day counts).
        - The "Days Minimum 3/5/7 Chores" options shift scope to "of the chores due today".
        - The `Days` family's three *Due*/*Selected* pairs become redundant (six options, three
          distinct behaviours) — see decision 9.

     9. **CONFIRMED — leave the redundant options in place; document the equivalence.**
        Decided 2026-09-14. No options are removed from the picker in this release. The redundant
        pairs are described as equivalent in the option help text, and any consolidation is
        deferred to a later, separately-reviewable change.

        Consequences to carry forward:
        - Phase 5 must add the equivalence wording to the help text for the redundant options in
          **both** families (two streak pairs, three days pairs).
        - No migration is required: each badge stores its target type internally and both
          spellings keep resolving.
        - Bonus: `Streak: Selected Chores Completed` becomes "100% of the chores due today, overdue
          tolerated" — a behaviour that previously had no option, so the release also adds a
          capability. Worth mentioning in the release note.

     10. **CONFIRMED BY DEFAULT — the `Days Minimum 3/5/7` variants keep the all-selected scope.**
         These options count an **absolute number** of completed chores, not a ratio
         (`count_required` compared against `approved_count`, `gamification_engine.py:936-947`).
         Applying the eligible scope to them would make the threshold unreachable whenever fewer
         chores are due than the required count — e.g. only 3 chores due today but `Days Minimum 5`
         requires 5 approvals among 3 eligible chores. The badge would stop advancing permanently.

         Decision: the eligible scope applies to the **percentage** variants only. The min-count
         variants continue to count completions of **all selected chores**, which is what the label
         literally promises ("at least N chores completed that day") and what they do today.

         - Consequence: this is a deliberate distinction, not an inconsistency, and it must be
           stated in the help text and wiki so it does not read as an oversight. A non-due chore is
           an *impossible obstacle* to a ratio but *extra credit* to an absolute count.
         - Alternative if uniform semantics are preferred later: clamp the requirement to the
           eligible count (`required = min(N, eligible_count)`). Not the default, because it
           silently makes existing min-count badges easier and the "minimum 5" label becomes
           misleading.
         - Phase 4 must pin this: `Days Minimum 5` with only 3 chores eligible must remain
           satisfiable by completing 5 selected chores, and must never become permanently unmet.

     11. **CONFIRMED BY DEFAULT — a selected chore with no due date and no recurrence stays in
         scope.** (Terminology per decision 12: "counts toward today's obligation", not
         "actionable" — see the naming trap there.)

         Background: `_is_chore_due_today_for_assignee` treats a chore as due today only if it has a
         due date falling today, or it is a **daily** chore with no due date. A chore with
         `frequency = none` and no due date is never "due today" (first guard in
         `no_due_date_daily_matches_today`, `chore_manager.py:3911`).

         Decision: a chore that is **open and uncompleted with no fixed date** counts toward the
         day. It is legitimately owed today, so excluding it would mean a badge scoped to it
         silently ignores it.

         - Consequence: behaviour for these chores is unchanged from today. Completing one still
           helps a ratio badge; missing one still counts against it.
         - Alternative: strict "due today" only, treating open one-time chores as outside the badge.
           Not chosen — it silently removes chores the user explicitly selected, and creates the
           permanently-neutral badge described above.
         - Phase 4 must pin: a badge scoped to a dateless one-time chore still advances when it is
           completed, and the "all selected chores are open one-timers" case does not stall forever.

   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

     12. **CONFIRMED — the eligible scope becomes *counts toward today's obligation*, not
        "scheduled today". (O1, closes conflict C1.)** Phase 1B. A chore counts toward an
        assignee's day when it is scheduled today **and** that assignee is the one who owes it.

        Three deliberate properties:
        - **It includes chores the assignee already completed.** The question is "does this chore
          form part of today's obligation for this assignee", not "can they still act". This is
          the naming trap: an "actionable" or "outstanding" naming would exclude completed chores
          and make every day permanently unsatisfiable — re-creating the original bug in a new
          form. `ChoreManager.chore_counts_toward_due_today_summary` answers the *other* question
          ("should this appear in the to-do list") and therefore **cannot be reused**: it returns
          False for `completed`.
        - **It excludes assignees who do not own the chore today.** Ownership is the rule, not
          ability to act. For `rotation_simple` / `rotation_smart` / `rotation_primary_standby`,
          only the **turn holder** owns the occurrence. A **standby never owns it**, even when
          `standby_claim_mode` lets them claim at any time — that is permission to help, not
          ownership. A would-be **stealer** on an overdue `allow_steal` chore does not own it
          either: stealing is an opportunity to earn points by finishing someone else's late work.
        - **It requires the assignee to still be assigned.** Port the guard from
          `chore_counts_toward_due_today_summary` (added for issue #205) so a stale chore entry
          cannot inflate `due_count` with a chore the assignee can no longer be credited for.

        Naming: the two concepts must be named apart so they cannot be confused again —
        `scheduled_today` (date-only, what `_is_chore_due_today_for_assignee` does now) versus
        `counts_toward_today` (what badges consume). Keep the old helper as the schedule primitive
        rather than deleting it; the sensor and other callers still need the date-only answer.

        Non-rotation modes are unaffected in behaviour: for `independent` / `shared_first` /
        `shared_all`, every assigned assignee already owes the chore, so the new scope resolves to
        the same set as before.

     13. **CONFIRMED — one authority for "was an occurrence missed between X and Y". (O2, closes
        conflicts C2/C3 at the source.)** Phase 1C. Three consumers currently answer this same
        question differently: `ChoreEngine.calculate_streak` (inline schedule-config assembly),
        `StatisticsManager._has_missed_occurrence_since_advance` (added in Phase 1), and
        `GamificationManager._streak_alive` (a calendar shortcut -- see decision 14). Consolidate
        on a single engine-level helper that takes the chore definition plus two bounds and answers
        it, with `calculate_streak` and the badge snapshot both calling it.

        The helper must preserve two behaviours that exist only inside `calculate_streak` today,
        because forgetting either is a silent regression:
        - **Day-based schedules are normalised to local day boundaries** (`start_of_local_day`),
          so DST shifts do not create phantom missed occurrences between consecutive dates.
        - **`daily_multi` and hour/minute interval units are exempt from that normalisation**,
          since their occurrences are not day-aligned.

        Anchor semantics stay caller-supplied, because the correct anchor genuinely differs: the
        badge path anchors on the badge's `last_update_day`, while `calculate_streak` anchors on the
        previous completion. The helper owns *how* to detect a miss, not *when* to look.

     14. **DEFERRED — streak subsystem unification moves to Phase 6** (O3, O4, O5). Recorded here
        so the intent is not lost, but deliberately **out of scope for the release-blocking
        phases**: Phase 6 changes achievement behaviour and deletes a public-looking engine method,
        both of which deserve their own review rather than being buckled onto the badge fix.
        - **O3** -- `COMPLETION_STREAK` achievements adopt the shared helper, removing the last
          calendar-day streak gate in the system (conflict C2).
        - **O4** -- `last_update_day` is now overloaded three ways (same-day idempotency gate,
          miss-check anchor, and the source of `streak_yesterday`). No behaviour change intended;
          needs an explicit typed comment so a future writer understands the blast radius.
        - **O5** -- remove or fix the dead `StatisticsEngine.update_streak` / `get_streak` pair
          (conflict C4), which currently preserves the exact anti-pattern this initiative removes.

        **Sequencing note:** Phase 6 is **split into two tranches** (revised 2026-09-15 after planning).
        Tranche **6A** (O4, O5 — code hygiene) carries no behaviour risk and can start immediately.
        Tranche **6B** (O3, C3 — achievement behaviour) must not begin until decisions 18–20 are
        answered **and** the badge behaviour is confirmed in the field. Doing O3 in the same release
        as the badge change would make it impossible to attribute any remaining streak report to the
        right subsystem. Full detail, including the verified O3/C3 coupling, is in the Phase 6
        section.
        make it impossible to attribute any remaining streak report to the right subsystem.

     15. **CONFIRMED 2026-09-15 — the Phase 4 harness mutates chore schedules in memory.**
        `StreakDayReplay` gains a neutral-day helper that edits the tracked chore's scheduling
        fields (`applicable_days`, due date, frequency) in `coordinator.chores_data` before
        evaluating a simulated day, rather than driving a dedicated schedule-matrix scenario file.
        Rationale: the harness stays scenario-agnostic, so one replay implementation serves every
        schedule shape, and it is the technique the badge setup already uses to force an
        open-ended reset schedule.

        Trade-off accepted: the tests construct their own schedules, so the matrix is only as
        realistic as the fields the helper sets. Each case must therefore assert its own
        preconditions — as `test_undated_weekly_chore_is_not_owed_today` does today — rather than
        trusting the scenario to supply them.

     16. **CONFIRMED 2026-09-15 — full matrix for standard schedules, one case each for the two
        custom frequencies.** `custom` and `custom_from_complete` anchor their occurrences to the
        **completion or creation time**, whereas the rrule frequencies anchor to the window start
        that `has_missed_occurrence_between` supplies. The same replayed day therefore means
        different things to the two families, and folding them into the shared matrix would invite
        assertions that pass only because the test rigged the setup.

        Consequence: the matrix covers daily, Mon/Wed/Fri, weekly (including a rescheduled due
        date), biweekly and monthly fully. The custom frequencies get one explicit, separately
        scheduled case each, and any limitation they expose is stated in the test rather than
        silently assumed away. If a custom frequency later turns out to need full coverage, that is
        a deliberate addition, not an oversight.

     17. **CONFIRMED 2026-09-15 — an undated one-timer counts toward the day, always (closes the
        decision 11 gap).** A chore with `frequency = none` and no due date counts as owed today
        whether it is open or already completed, exactly like any other chore in scope.

        Background: decision 11 required this behaviour, but the implementation never delivered it.
        `_is_chore_scheduled_today_for_assignee` defers a `None` due date to
        `no_due_date_daily_matches_today`, whose first guard rejects every frequency except
        `FREQUENCY_DAILY`, so `due_count` excluded such a chore outright. A badge scoped only to
        open one-timers therefore had an eligible count of zero every day: rule 3 (neutral hold)
        applied and the badge could neither advance nor break. Found by the Phase 4 step 7 pin.

        Implemented as `StatisticsManager._is_undated_one_timer`, OR-ed with the schedule
        primitive. No claim-mode list change was needed, because a completed chore already resolves
        to `blocked_already_approved`, which counts.

        **Consequence — CORRECTED 2026-09-15 after verification.** An earlier revision of this decision
        stated that "one completion of a `frequency = none` chore keeps the day satisfied on every
        later day, so a badge scoped only to it advances daily off that single completion". **That was
        wrong — it was reasoned, not tested.** Verified by probe: the chore completed on day −1
        advances the badge to 1, and on the following day the snapshot reports `due_count=1`,
        `approved_due_today=0`, `missed_since_advance=False`, after which the count **stays at 1 and
        never moves again**.

        The actual and worse behaviour is that such a badge **freezes**. `approved_due_today` is read
        from that day's own period bucket only, so a later day has nothing approved; and because
        `has_missed_occurrence_between` short-circuits to `False` for `FREQUENCY_NONE`, no miss is
        ever detected either. The day is therefore neither satisfied nor missed, so the streak
        neither advances nor breaks. It is not free advancement — it is permanent stalling.

        **This is exactly what decision 18 fixes.** Once an unscheduled chore follows daily streak
        rules, the day after a completion is a genuine missed day, the break is detected, and a badge
        scoped to it becomes a normal daily streak: keep it up and it builds, skip a day and it
        resets. Decision 17 remains correct as written — such a chore *is* owed every day — it is the
        downstream streak consequence that needed decision 18 to land.

        No published documentation is affected: the merged release note and the wiki say only that
        such a chore "counts on every day", which is accurate. The incorrect claim existed only here.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update.

     18. **CONFIRMED 2026-09-15 — an unscheduled chore follows daily streak rules (closes C3, pairs
        with O3).** A chore with no due date and no recurrence is evaluated as if it were daily: do
        it every day and the streak builds; skip a day and it breaks to zero. This applies to
        **both badges and achievements**, so all three systems agree.

        Rationale (product owner): the user never expressed an intent for such a chore, so an
        intent must be inferred, and daily is the only relatively logical model — "streak" already
        means consecutive days to a user, and a month-long streak off sporadic completions would be
        meaningless. It is explicitly accepted as a compromise built on an assumption.

        Implementation consequence: `has_missed_occurrence_between` stops short-circuiting
        `FREQUENCY_NONE` and evaluates it on a daily recurrence instead, which also lets
        `calculate_streak`'s inline `FREQUENCY_NONE` special case be deleted so the helper truly owns
        the rule. This **fixes the frozen-badge defect** described under decision 17's corrected
        consequence.

        Behaviour change to note in the release note: badges scoped to an unscheduled chore
        previously stalled after one advance; they now behave as daily streaks.

     19. **CONFIRMED 2026-09-15 (against the recommendation) — an unreadable schedule counts as a
        miss.** When a chore's schedule cannot be evaluated, the streak breaks rather than holding.

        Rationale (product owner): unreadable data is a distinct problem that the user can notice
        and report; silently continuing the streak would mask the underlying bug. This reverses the
        earlier recommendation to fail open.

        Consequence to accept: a data defect will zero streaks instead of passing quietly, so a
        message should make the cause visible rather than leaving the user to guess. This also makes
        all callers agree — `calculate_streak` already passes
        `unusable_schedule_counts_as_miss=True` — removing the documented policy split.

        ⚠️ **Scope question to settle:** the badge path currently passes `False`. Applying decision
        19 everywhere means changing **already-merged badge behaviour**, which needs its own release
        note entry and arguably its own PR rather than riding along in 6B. Confirm whether this is
        achievements-only or all streak paths.

     20. **CONFIRMED 2026-09-15 — the achievement miss window ends at the start of today.**
        Matches the badge path exactly, so today's still-pending occurrence cannot break a streak
        mid-day. Accepted consequence: the same documented one-day latch as badges (a missed
        occurrence breaks the streak on the following day).

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

### Conflicts found during Phase 1 review (2026-09-14)

A post-Phase 1 audit of every streak implementation and every "due today" notion in the codebase.
These are **not** hypothetical: two of them would ship defects into the exact feature we are
fixing.

**C1 — The eligible scope is coarser than the dashboard's, so rotation chores will be wrongly
required. (Blocks Phase 2; addressed by Phase 1B.)**

`_is_chore_due_today_for_assignee` (our eligibility source) is **schedule-only**: pause guard →
per-assignee due date → dateless-daily. `ChoreManager.chore_counts_toward_due_today_summary`
(`chore_manager.py:4572`) — what the dashboard's "Due Today" means — is **schedule *and*
legitimacy**, and additionally excludes `not_my_turn`, `standby`, `overdue`, `missed`, `paused` and
six blocked claim modes.

Verified mechanics: `ChoreEngine.resolve_assignee_chore_state` (`chore_engine.py:714`) returns
`not_my_turn` for rotation assignees other than the turn holder (P3), and `standby` for non-turn
assignees on `rotation_primary_standby`. Only the turn holder (or a window-permitted standby) can
complete the chore. But `_is_chore_due_today_for_assignee` falls back to the chore-level due date,
so **every** assignee reads as eligible on a dated rotation chore.

Consequence once Phase 2 lands: a badge scoped to a rotation chore counts an uncompletable chore
for every non-turn assignee → the day can never be satisfied → stall or break. **This is the same
bug class we are fixing, entering through a different door.**

Eligibility also lacks the **assignment guard** that `chore_counts_toward_due_today_summary`
carries explicitly *because of issue #205* ("prevents stale entries from inflating Due Today after
a user is removed"). If a tracked chore outlives the assignment, `due_count` increments while
`approved` cannot — an uncompletable chore again.

**C2 — Achievement streaks still break on non-daily schedules. (Addressed by Phase 6 / O3.)**

`GamificationManager._streak_alive` (`gamification_manager.py:2881`) requires `last_completed` to be
**today or yesterday**. Verified against the real logic for a weekly chore whose schedule-aware
chore streak is 3, evaluated on a Wednesday:

| Last completed | Streak reported to the achievement |
| --- | --- |
| Monday (2 days ago) | **0** |
| Yesterday | 3 |
| Today | 3 |

So `COMPLETION_STREAK` achievements carry the **same defect** as badges did: a weekly-chore streak
can never exceed 1 for the achievement. The plan's earlier claim that achievements "inherit"
schedule awareness was half right — they inherit the value, but this calendar gate destroys it.
`_streak_alive` is precisely the approximation we rejected for badges.

**C3 — Open-ended chores have two contradictory "missed" semantics. (Phase 6 / O2.)**

`ChoreEngine.calculate_streak` for `FREQUENCY_NONE` uses a calendar check (`days_diff <= 1` breaks
the streak), while `RecurrenceEngine.has_missed_occurrences` returns `False` for `FREQUENCY_NONE`
(no schedule ⇒ nothing to miss). Same chore, two answers. Not a live conflict today, but it means
an open-ended chore can never *break* a badge streak, only stall it — which should be a deliberate
choice rather than an accident.

**C4 — Dead code carrying the exact anti-pattern we just removed. (Phase 6 / O5.)**

`StatisticsEngine.update_streak` / `get_streak` (`statistics_engine.py:333`, `:408`) have **zero
production callers** (verified: only their own docstrings and `test_statistics_engine.py`, which
has 13 tests pinning them green). They implement literal calendar-yesterday logic, are generically
named, and their docstring documents the behaviour as correct. That is an attractive trap — the
next person adding a streak would plausibly reach for them and reintroduce this entire bug class.

---

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

### Days family: worked answers and eligibility rules

Answers to the concrete question *"5 chores selected, threshold 5/day, 3 with due dates and 2
without — what counts as a successful day?"*, verified by evaluating the real evaluators.

**Eligibility rule (what "counts today" means).** `_is_chore_due_today_for_assignee`
(`statistics_manager.py:2632`) returns true when either:

1. the chore has a due date for this assignee and it falls today; or
2. the chore has no due date **and** is a daily recurring chore (and today matches its applicable
   days, if it has any).

A chore with **no due date and no recurrence** (`frequency = none`) is **never** "due today" —
guard (a) in `no_due_date_daily_matches_today` returns false for any frequency other than daily.
This matters for decision 11.

Because both of the dateless chores in the question are daily recurring, they *are* eligible today.
So the eligible count is 5, and the answers are:

| Day | `Days Minimum 5` | `Days 100% Selected` | `Days 80% Selected` |
| --- | --- | --- | --- |
| All 5 completed | ✅ day counts | ✅ 5/5 | ✅ |
| Missed one **with** a due date | ❌ only 4 completed | ❌ 4/5 = 80% | ✅ 4/5 |
| Missed one **without** a due date | ❌ only 4 completed | ❌ 4/5 = 80% | ✅ 4/5 |

**The key answer: there is currently no distinction between missing a dated and a dateless chore.**
Both weigh exactly the same, because the evaluators count all selected chores and all approvals
regardless of schedule. A dateless daily chore is treated as an obligation on every day, which is
consistent with how it behaves everywhere else in the integration.

**What this initiative changes for that scenario: nothing.** Both dateless chores are eligible, so
the eligible count equals the selected count and every row above is unchanged. The fix only alters
outcomes when a selected chore is genuinely **not available** today — a weekly chore on the wrong
day, a day-restricted chore, or a one-time chore whose due date is elsewhere. That is the case
where the old logic demanded an impossible completion.

### Days family: two gaps this analysis exposed

Both are new decisions, taken by default to **preserve existing behaviour**, because in each case
the alternative silently changes or permanently breaks existing badges.

**Gap A — the `Days Minimum 3/5/7` options break under the eligible scope (decision 10).** These
variants use an **absolute count**, not a percentage: `count_required` is compared against
`approved_count` (`gamification_engine.py:936-947`). If the eligible scope replaces the denominator
there, a household with only 3 chores due today can never satisfy `Days Minimum 5` — the threshold
becomes unreachable and the badge stops advancing permanently.

**Gap B — a selected chore with no due date and no recurrence would be dropped (decision 11).**
Such a chore is never "due today", so a strict eligible scope would exclude it from the badge
entirely: completing it would stop helping, and missing it would stop mattering. Worse, a badge
scoped *only* to such chores would have an eligible count of 0 every day, so it would sit
permanently neutral — never advancing and never breaking.

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

- **Goal**: Give the engine everything it needs to classify a day, without touching any evaluation maths yet.
- **Status**: ✅ **Complete** (2026-09-14). No evaluator behaviour changed — confirmed by all
  existing badge/gamification suites passing unmodified.
- **Precondition**: ✅ satisfied — decision 8 is confirmed as *both families*, so the eligible scope
  is applied in the shared day-status layer and consumed by every evaluator.
- **Steps / detailed work items**
  1. ✅ Add `due_count` and `approved_due_today` to the completion snapshot returned by
     `get_badge_scoped_today_completion` (`managers/statistics_manager.py`). Reuses the existing
     `_is_chore_due_today_for_assignee` — no second schedule check was added — and computes both
     in the same loop as `total_count` / `approved_count`.
  2. ✅ Extract `ChoreEngine.build_schedule_config()` (`engines/chore_engine.py`), now called by
     `calculate_streak` instead of assembling the config inline. Behavioural no-op, pinned by
     `tests/test_workflow_streak_schedule.py` (11 tests) staying green.
  3. ✅ Add `missed_since_advance: bool` implementing the contract, via the new
     `StatisticsManager._has_missed_occurrence_since_advance()`. Anchor is the badge's
     `last_update_day` only; upper bound is the start of today; no window means no miss.
  4. ✅ **Placement decided: eager, in the snapshot.** Rationale: the manager already holds
     `coordinator.chores_data`, `RecurrenceEngine` is importable there (verified), and computing
     once per snapshot avoids leaking schedule-building into the pure engine. Short-circuits on the
     first missed chore. `last_update_day_iso` is a keyword argument with an empty default, so
     achievements/challenges (which have no badge anchor) correctly get no window.
  5. ✅ Fail safe on missing/unparseable anchor or unknown chore IDs — all yield "no miss".
  6. ✅ New `BadgeScopedCompletionSnapshot` TypedDict in `type_defs.py`, now the declared type of
     `today_completion` / `today_completion_due` **and** the return type of the snapshot method, so
     mypy enforces the contract rather than trusting a `dict[str, Any]`.
  7. ✅ Add `tests/test_badge_schedule_snapshot.py` — 19 tests covering the eligible scope, all five
     contract traps, and the shared builder.
- **Key issues**
  - **Purity/layering — verified, no blocker.** The boundary checker only forbids `homeassistant`
    imports in pure modules (`utils/`, `engines/`); managers are not pure, and
    `managers/chore_manager.py:30-39` already imports `../engines/chore_engine` and
    `../engines/schedule_engine`. `statistics_manager` may therefore import `RecurrenceEngine`
    directly. `statistics_manager` already reads `self.coordinator.chores_data`, so the schedule
    inputs are in reach.
  - **Loop cost**: only tracked chores are evaluated, and the check short-circuits on the first miss.
    The check cannot be skipped on neutral days (see the contract's ordering note) — that
    restriction is a correctness requirement, not a performance choice.
  - `has_missed_occurrences` takes UTC datetimes; the snapshot is ISO-date based. Bounds are built
    with `datetime.combine(date, time.min, tzinfo=get_default_timezone())` then `as_utc(...)` —
    no raw `datetime` timezone guessing.
  - **Contract trap confirmed by test:** `_record_day`-style reasoning about a chore's own
    `last_completed` would have used the wrong anchor. `test_todays_pending_occurrence_is_not_a_miss`
    pins the start-of-today upper bound, which is the trap that would have re-created the #294
    symptom mid-day.

### Phase 1B – Eligible scope must mean "counts toward today's obligation" (O1)

- **Goal**: Replace schedule-only eligibility with legitimacy-aware eligibility, so a chore an
  assignee cannot be credited for never counts against them (closes conflict C1).
- **Status**: ✅ **Complete** (2026-09-14). Closes conflict C1.
- **Why before Phase 2**: Phase 2 consumes `due_count` / `approved_due_today`. Shipping Phase 2
  first would introduce unfair breaks for rotation and standby chores — the exact failure mode this
  initiative exists to remove.
- **⚠️ Implementation correction — the rule is OWNERSHIP, and a claim-mode allow-list.** Two
  successive wrong guesses were corrected during implementation, both caught by tests:
  1. The plan said to derive "owes it" from the **display state**. A test disproved it: for
     `rotation_primary_standby`, `resolve_assignee_chore_state` returns **`standby` in both
     cases** — whether the standby may act or not — so the state alone cannot separate them.
  2. Switching to a claim-mode *deny-list* was also wrong, and the product owner corrected the
     model itself: **a primary/standby chore never belongs to a standby**, even when
     `standby_claim_mode: anytime` grants permission to claim. Permission to help is not
     ownership — only the turn holder owns it. Likewise, **`steal_available` must not count**:
     stealing is an opportunity to earn points by finishing someone else's late chore, not a
     responsibility they were assigned.

  3. A third correction closed the last gap: **someone else completing the chore does not
     discharge the obligation when it was this assignee's turn.** If the primary skips their
     turn and a standby covers, the primary is still charged — they did not do it; being rescued
     is not the same as doing the work. Conversely for `shared_first`, one completion satisfies
     the chore for everyone, so the non-completers are relieved. Both cases read the **same**
     `blocked_completed_by_other` claim mode, so it cannot be classified statically; it is
     resolved in context by whether the assignee is the rotation turn holder.

  Implemented as an explicit **allow-list**, `CHORE_CLAIM_MODES_COUNTING_TOWARD_DAY`, so an
  unclassified mode is not charged against anyone until reviewed deliberately. The complementary
  `CHORE_CLAIM_MODES_NOT_COUNTING_TOWARD_DAY` is also explicit, and
  `TestClaimModeClassification::test_modes_partition_the_enum` asserts the two sets plus the
  context-dependent mode partition `CHORE_CLAIM_MODES` — a newly added claim mode therefore fails
  the test until it is classified.
  Verified mechanics (`state` / `claim_mode`): turn holder = `pending`/`claimable`; standby with
  `anytime` = `standby`/`standby_available`; standby with `on_overdue` or `manual_only` =
  `standby`/`blocked_standby`; non-turn assignee on an overdue `allow_steal` chore =
  `overdue`/`steal_available` while the turn holder stays `overdue`/`claimable`; non-completer of a
  `shared_first` chore = `completed_by_other`/`blocked_completed_by_other`; primary after a standby
  covers = the same `completed_by_other`/`blocked_completed_by_other`.
- **Steps / detailed work items**
  1. ✅ Kept `_is_chore_due_today_for_assignee` as the schedule primitive, renamed to
     `_is_chore_scheduled_today_for_assignee` so the two concepts cannot be confused again.
     Added `_chore_counts_toward_today` implementing decision 12.
  2. ✅ Did **not** reuse `chore_counts_toward_due_today_summary`. Its assignment guard (the issue
     #205 fix) was ported into the new resolver instead.
  3. ✅ Derives legitimacy from the existing resolution via
     `ChoreManager.get_chore_status_context`, so rotation and standby semantics stay in one place.
  4. ✅ Rewired `get_badge_scoped_today_completion` so `due_count` / `approved_due_today` use the
     new scope. `total_count` / `approved_count` unchanged.
  5. ✅ Added `CHORE_CLAIM_MODES_COUNTING_TOWARD_DAY` (allow-list, 5 modes) and
     `CHORE_CLAIM_MODES_NOT_COUNTING_TOWARD_DAY` (6 modes) to `const.py`, with reasons per mode and
     a partition test.
  6. ✅ 22 new tests in `tests/test_badge_schedule_snapshot.py` covering rotation, shared modes,
     all three primary-standby claim modes, steal, the standby-completes case, the
     stale-assignment guard, non-rotation invariance, and claim-mode classification.
- **Key issues**
  - **The completed-chore trap is the highest-risk part of the whole initiative**, and it appears in
    two forms: the display state (`completed` / `approved`) and the claim mode
    (`blocked_already_approved`). Both must keep counting. Pinned by
    `test_completed_chore_keeps_counting_for_the_completer`, which also asserts the claim mode is
    `blocked_already_approved` so it cannot pass vacuously.
  - Non-rotation modes are pinned as unchanged by `test_non_rotation_modes_exclude_nothing`
    (`due_count == total_count` for `shared_all` / `shared_first` / `independent`).
  - **`CHORE_CLAIM_MODES_COUNTING_TOWARD_DAY` must stay minimal.** Adding
    `blocked_already_approved`, `blocked_waiting_window` or `blocked_missed_locked` would silently
    make satisfied days unsatisfiable; adding `steal_available` or either standby mode would
    charge an assignee for work that was never theirs.
  - **Resolved: the stealer question.** Earlier guidance was to count `steal_available` on the
    reasoning that a chore left undone must be someone's failure. The product owner corrected
    this: the stealer picks up someone else's late chore for points, and the original owner keeps
    the failure. Implemented as not-counting, with the turn holder still charged.
  - **Resolved: the standby-covers question.** A standby completing the primary's turn does **not**
    excuse the primary. Earlier guidance was to count it as relieved (the primary reads
    `completed_by_other`); the product owner corrected this — it was the primary's turn and they
    did not do it. The standby earns their own credit. Note the pairing with `shared_first`,
    where the same claim mode *does* relieve the others: the difference is whether the non-actor
    was personally on the hook.
  - **Standby-completes does not advance the rotation.** Verified: the turn stays with the primary
    after a standby approves, so the primary remains the turn holder and stays charged. If a future
    change advances the turn on standby completion, the primary would escape on the following day,
    which would weaken this rule.
  - **Performance**: `get_chore_status_context` now runs per tracked chore per badge snapshot (two
    per badge). It is the same read path sensors use and evaluation is debounced, so no short-circuit
    was added. If profiling shows a problem, gate it on non-rotation and non-`shared_first` chores
    first — both are cheap checks that skip the resolution entirely.


### Phase 1C – Single missed-occurrence authority (O2)

- **Goal**: One engine-level helper answers "was an occurrence missed between X and Y", used by
  both chore streaks and badge streaks (closes the divergence behind conflicts C2/C3).
- **Status**: ✅ **Complete** (2026-09-14). Closes O2.
- **Steps / detailed work items**
  1. ✅ Added `ChoreEngine.has_missed_occurrence_between(chore_data, *, window_start_utc,
     window_end_utc, unusable_schedule_counts_as_miss=False)`. It builds the schedule config,
     normalises, constructs `RecurrenceEngine` and reports whether an occurrence was missed.
  2. ✅ `calculate_streak` now delegates, replacing its inline config assembly, its inline
     normalisation and its direct `has_missed_occurrences` call. Behaviour preserved:
     `test_workflow_streak_schedule.py` passes **unchanged** (11 tests), which is the evidence the
     refactor was a no-op.
  3. ✅ `StatisticsManager.has_missed_occurrence_since_advance` now delegates, and the Phase 1
     duplicate of the builder + check was deleted along with the now-unused `RecurrenceEngine`
     import in `statistics_manager.py`.
  4. ✅ Both normalisation behaviours moved into the helper as a single expression: local-day
     boundaries for day-based schedules, and the exemption for `daily_multi` and hour/minute
     units. Previously the badge path matched the chore path only by coincidence; now it is
     explicit and shared.
  5. ✅ Anchors stay caller-supplied: the badge path passes the badge's advance day, the chore path
     the previous completion.
  6. ✅ Added `tests/test_missed_occurrence_authority.py` — 27 tests: helper contract,
     cross-caller parity, the time-of-day insensitivity invariant, sub-day exemption, a DST
     transition case, and the error-policy split.
- **⚠️ Finding not in the plan — the two callers deliberately disagree on the error path.** The
  old `calculate_streak` wrapped schedule evaluation in a bare `except` and returned **1 (broke
  the streak)** on failure; the badge path fails safe with **False (no miss)** so bad data never
  breaks a valid streak. Both were intentional, so the helper takes
  `unusable_schedule_counts_as_miss` and each caller states its own policy at the call site
  rather than inheriting the other's. This is also why the boundary checker's bare-exception
  allowlist entry for `chore_engine.py` ("any failure safely resets streak") is now unnecessary —
  `chore_engine.py` no longer contains a bare `except`.
- **Key issues**
  - **The FREQUENCY_NONE divergence is preserved, not fixed.** `calculate_streak` decays an
    open-ended chore with a calendar rule (`days_diff <= 1`) while the helper returns "no miss"
    for `FREQUENCY_NONE`. That is conflict **C3**, deliberately deferred to Phase 6, so the
    helper documents it rather than silently unifying it. Do not "fix" it here — the two would
    then disagree for every open-ended chore.
  - `RecurrenceEngine` barely raises: probing unknown frequencies (`"bogus"`, `"custom"`, `None`)
    found no exception, so the error path is defensive only. The policy split is therefore pinned
    with a monkeypatch rather than by finding a naturally failing input.
  - Verified the dedupe rather than assuming it: without the precomputed value the miss check ran
    **twice** per badge evaluation (once per scope variant); with it, **once**. The test asserting
    a single call would fail at two, so it is not vacuous.
  - Helper has no Home Assistant dependency and stays in the pure engine layer; the manager
    supplies `chore_data` from `coordinator.chores_data`.

### Phase 2 – Evaluator semantics (both families)

- **Goal**: Apply the eligibility rule to the streak evaluator, and the eligible denominator to
  **both** the streak and days evaluators (decision 8).
- **Status**: ✅ **Complete** (2026-09-14).
- **Steps / detailed work items**
  1. ✅ `_resolve_daily_status` now surfaces `eligible_total`, `approved_eligible` and
     `missed_since_advance` alongside the existing keys, so both evaluators read the eligible
     scope from one place. With decision 8 confirmed the scope is **not** per-evaluator.
  2. ✅ `_evaluate_streak`'s decision block rewritten to the precedence: strict break → **missed
     break** → neutral hold → idempotent hold → advance → in-progress hold. The no-overdue check
     was removed from `today_met` because the strict branch already handles it ahead of every
     other rule.
  3. ✅ The advance branch no longer reads `streak_yesterday`; continuity now comes from the
     absence of a missed occurrence. The key and its `STATISTICS_MANAGER` computation are left in
     place for Phase 6 / O4 to retire deliberately.
  4. ✅ Both evaluators score percentages against the eligible scope. The absolute-count variants
     (`Days Minimum 3/5/7`) deliberately keep the all-selected scope (decision 10).
  5. ✅ `reason` strings updated: a neutral day reports "nothing owed today" rather than an
     alarming `0/7`, and the day detail shows the eligible fraction actually used.
  6. ✅ Docstrings rewritten to define an eligible occurrence, a neutral day and a missed
     occurrence, and the `streak_yesterday` context requirement removed from the streak contract.
  7. ✅ `make_context` in `tests/test_gamification_engine.py` gained `due_count`,
     `approved_due_today` and `missed_since_advance`, and lost the now-inert `streak_yesterday`.
- **⚠️ Defect found while implementing — a broken streak could never restart.** The plan assumed
  the anchor would clear once the streak restarted, but the restart was itself blocked by the old
  miss, a circular dependency: the miss breaks the streak → the streak does not advance →
  `last_update_day` is only stamped on an advance → the anchor stays behind the miss → the miss is
  detected again forever. Verified by direct evaluation: `cycle_count=2` and `cycle_count=0` both
  returned 0 on a satisfied day with the miss still in the window.

  Fixed in the engine with **`cycle_count > 0` gating the miss check**: a miss only matters when
  there is a streak to break. With no credited days there is nothing to protect, and a past miss
  must not permanently block a restart. This keeps every break-detection case working (all of them
  have an active streak) while making recovery possible, and needs no schema, persistence or extra
  field — unlike the fallback design in the Notes.
- **Key issues**
  - **Existing tests required re-expression, as predicted.** The two `TestStreakStillBreaks` guards
    in `test_badge_streak_midnight_reset.py` relied on the calendar gate and were updated to drive
    the miss mechanism; they pass unchanged in intent. In `test_gamification_engine.py`,
    `test_streak_starts_fresh_without_yesterday` became
    `test_streak_starts_at_one_when_no_credit_exists` (a fresh start now requires no credited
    days, since calendar adjacency no longer implies continuity), and
    `test_streak_breaks_after_a_full_day_without_completion` became
    `test_streak_breaks_when_an_occurrence_was_missed`.
  - **Test-isolation defect fixed in the Phase 1C tests.** `test_missed_occurrence_authority.py`
    passed in isolation but failed in a fuller run, because the helper normalises to *local* day
    boundaries and the default timezone is a module global other test files mutate. It now pins
    UTC with an autouse fixture that restores the previous value. This is the documented
    cross-test timezone hazard, and it was introduced by Phase 1C — the tests were passing by luck.
  - `criteria_met` is still derived from `current_value`, so a neutral day cannot flip an
    already-earned criteria state.
  - The days evaluator's hold-instead-of-zero behaviour is preserved, and strict mode still zeroes
    immediately.

### Phase 3 – Persistence & status alignment

- **Goal**: Keep the write path consistent with the new semantics.
- **Status**: ✅ **Complete** (2026-09-14).
- **Steps / detailed work items**
  1. ✅ **Audited — no defect found.** The `days_cycle` branch already writes
     `days_cycle_count` only when it changes, and the hold/neutral paths return the unchanged
     count, so a neutral day produces zero writes. Confirmed empirically rather than by
     inspection: a deep copy of the progress record is identical after re-evaluating a neutral
     day.
  2. ✅ Break path confirmed on both halves: it writes `0` and deliberately leaves
     `last_update_day` stale. Verified the staleness is load-bearing (it is the miss anchor) and
     that a restart then stamps a fresh anchor, so the stale value cannot block recovery.
  3. ✅ `_resolve_target_status_transition` and `_is_periodic_award_recorded_for_current_cycle`
     reviewed: a neutral day cannot flip `criteria_met` (the count is unchanged, so the derived
     status is unchanged), and an earned badge is not re-awarded — pinned by test, since badges are
     never removed and a stale high streak must not keep paying out.
  4. ✅ `_advance_non_cumulative_badge_cycle_if_needed` returns early unless
     `end_date_iso < today_iso`, so it only fires on a real cycle boundary. Pinned with a pair of
     tests: an open cycle leaves a neutral day alone, and an ended cycle resets.
  5. ✅ Added `tests/test_badge_progress_persistence.py` — 9 tests covering zero writes on a
     neutral day, anchor stability, the break/restart/steady-state sequence, no re-award, and the
     rollover distinction.
  6. ✅ **Write-path simplification (behaviour-preserving).** The anchor rule in the `days_cycle`
     branch contained a vacuous disjunct (`or previous_update_day == today_iso`), because the inner
     guard made that path a no-op. Reduced to a single condition that states the rule the new
     semantics depend on: *the anchor advances only when the streak advances*. Provably equivalent
     (given `previous_update_day != today_iso`, the disjunct is always false), and pinned by the
     persistence tests.
- **⚠️ Engine defect found while auditing — a compliant day after a break earned no credit.**
  Testing the restart path exposed an inconsistency: the same real-world situation produced
  different results depending only on whether the break had already been persisted.

  | Situation | Before | After |
  | --- | --- | --- |
  | Miss pending, streak still credited, today satisfied | **0** (day uncredited) | 1 (new streak) |
  | Miss pending, streak already at 0, today satisfied | 1 | 1 |

  The second was correct. In the first, the child's compliant day was discarded: they only received
  credit on a later evaluation, so a full day of work earned nothing on the day it happened.

  Fixed in `_evaluate_streak`: when a miss voids the streak **and** today is satisfied, the count
  becomes `1` rather than `0` — the old streak is void, but today's work starts a new one. A miss
  with nothing done today still breaks to `0`, and all existing break-detection cases are
  unaffected. This is a Phase 2 semantics correction discovered by Phase 3 tests, not a write-path
  change.
- **Key issues**
  - The first evaluation of a badge legitimately writes, because the progress record is populated
    lazily. The zero-write assertion therefore snapshots *after* one evaluation; comparing against
    the pre-initialization state would fail for the wrong reason. Documented in the test.
  - The now-inert `streak_yesterday` computation remains in `statistics_manager.py` with no
    consumer; retire it in Phase 6 / O4 as planned, not here.
  - Cumulative badges were not touched by this phase, and remain out of scope.

### Phase 4 – Tests & validation

- **Goal**: Lock the semantics with a schedule matrix, and prove no regression in the existing suites.
- **Status**: ✅ **Complete** (2026-09-15) — all 11 steps done, 24 new tests, one implementation gap closed (see step 7).
- **Steps / detailed work items**
  1. ✅ Extend `tests/test_badge_streak_midnight_reset.py` with the `StreakDayReplay` harness already built for #294:
     - ✅ add a `neutral` helper, so the harness can express a day on which the tracked chore is not due. Per **decision 15** the helper mutates the chore's scheduling fields in `coordinator.chores_data` before evaluating the simulated day; no dedicated schedule-matrix scenario file is added. Implemented as two context managers plus a probe: `chore_schedule(frequency, due_date_day_iso, applicable_days)` restores the originals on exit so a case can compose schedules, `neutral_day(day_iso)` applies the neutral schedule, and `owed_today(day_iso)` reports `due_count` so every case asserts its own preconditions (decision 15's accepted trade-off).
     - ✅ **CORRECTION (2026-09-15) — the seeding requirement stated here was wrong.** An earlier revision of this step required seeding `DATA_USER_CHORE_DATA_LAST_COMPLETED` alongside the daily period buckets, claiming that "the miss check would see no completions at all and every day would read as missed". That claim is false. `ChoreEngine.has_missed_occurrence_between` (`chore_engine.py:1479`) builds its window from the supplied bounds and calls `RecurrenceEngine.has_missed_occurrences` (`schedule_engine.py:194`), which generates occurrences from the recurrence rule and **never reads a completion timestamp**; `build_schedule_config` (`chore_engine.py:1431`) reads only frequency, interval, unit, `applicable_days` and `daily_multi_times`. The harness therefore replays correctly on period data alone. Seeding completions is optional realism if a case needs it, never a prerequisite — do not add it on the strength of the old wording.
  2. ✅ **Verify — do not re-express — the two existing break-semantics guards** (`TestStreakStillBreaks`). This work was completed during Phase 2 (see that phase's key issues), and the guards already drive the break through the miss mechanism: they seed `last_update_day` three days back and evaluate the skipped day and the following day, exercising the documented one-day-later latch. **Verified 2026-09-15** by temporarily forcing `missed_since_advance = False` in `_evaluate_streak` (`gamification_engine.py:1135`): both guards fail (`test_missing_a_full_day_breaks_the_streak`, `test_streak_restarts_at_one_after_a_break`), so they genuinely exercise the miss branch rather than passing on the surrounding hold rules. The probe was reverted and the engine diff confirmed clean. Leave their intent intact (a genuinely missed day still breaks; a broken streak restarts at 1); do not delete or weaken them.
  3. ✅ Extend `TestStreakSurvivesInProgressDay` with the neutral-day case: seed an intact streak, evaluate a day where nothing is due, assert the count is unchanged **and** `last_update_day` is unchanged (proving the hold is a true no-op, not a re-stamp). Implemented as `test_neutral_day_holds_without_restamping_the_anchor`, which asserts `owed_today() == 0` *inside* the neutral block — without that assertion the test would pass vacuously, because a day that is still owed holds in-progress and produces the same two values.
  4. ✅ Add `tests/test_badge_streak_schedule_awareness.py` covering the matrix. Per **decision 16** the standard schedules get full coverage — Mon/Wed/Fri (`applicable_days`), weekly with a rescheduled due date, biweekly, monthly — plus a mixed daily+weekly badge; the two completion-anchored custom frequencies get one explicit case each instead of a full matrix slot, because their occurrences anchor to the completion/creation time rather than the window start the miss check supplies (see decision 16). Assert: neutral days hold; consecutive occurrences advance; a genuinely missed occurrence breaks; a gap with no missed occurrence resumes. **Implemented 2026-09-15** — 13 tests. Cases state intent through a `MatrixReplay` wrapper (`satisfy` / `hold` / `miss`) and assert **both** halves of their own precondition, because the harness constructs schedules: `owed_today` for the eligible scope and the new `scheduled_occurrence_on` probe for the recurrence.
  5. ✅ Add the regression case that motivated this plan: **4 daily chores + 1 weekly due Monday, all dailies done every day → the 100% streak badge reaches the threshold** (currently caps at 1 with a break). Cover both the partial-progress and full-day orderings, since the advance path previously reset to 1. Implemented as `TestMotivatingRegression` — the full-across-days ordering reaches the threshold and awards, and the partial-then-complete ordering advances 2 → 3 within a single day.
  6. ✅ Add **Days-family** coverage required by decision 8: the primer's table with 4 dailies + 1 weekly must show `Days 100%` advancing on a day the weekly is absent (currently stalls), and the 10-mixed-chores/3-due case must score 3/3 rather than 3/10. Also cover the "Days Minimum 3/5/7" scope shift. **Implemented 2026-09-15** in `tests/test_badge_days_scope.py` — the scenario presents 3 of 5 selected chores owed, so the ratio cases discriminate 3/3 from 3/5; `_assert_scope_precondition` asserts that 3-of-5 split so they cannot pass vacuously. Also pins that the eligible scope did **not** make a day unconditionally satisfiable (one owed chore left undone still holds the day), and that the min-count variants sit outside it (step 7).
  7. ✅ **Complete — the pin exposed an unimplemented decision, now fixed (decision 17).**
     - ✅ **DEFECT FOUND: decision 11 was never implemented, so a dateless one-time chore was dropped from the eligible scope.** Found by `test_dateless_one_time_chore_counts_toward_the_day`. Verified against the code path: `_chore_counts_toward_today` (`statistics_manager.py:2761`) calls `_is_chore_scheduled_today_for_assignee` first, which for a `None` due date defers to `ChoreManager.no_due_date_daily_matches_today` (`chore_manager.py:3911`) — and that function's **first guard** returns False for any frequency other than `FREQUENCY_DAILY`. A chore with `frequency = none` and no due date was therefore never scheduled today, so `due_count` excluded it before the claim-mode list or the assignment guard was consulted.

       Why this was a defect rather than a choice: decision 11 confirmed such a chore "is legitimately owed today", and its stated rationale was to avoid "a badge scoped to it silently ignoring it". The implemented behaviour was exactly that. Worse, the "all selected chores are open one-timers" case that decision 11 required not to stall **did** stall: `eligible_total == 0` on every day, so rule 3 (neutral hold) applied and the badge could neither advance nor break — permanently inert.

       **Resolved by decision 17 (product owner, 2026-09-15): an undated one-timer counts toward the day, always.** Implemented as `StatisticsManager._is_undated_one_timer` (`statistics_manager.py:2828`), OR-ed with the schedule primitive inside `_chore_counts_toward_today`. No claim-mode list change was needed: a completed chore already resolves to `blocked_already_approved`, which is in `CHORE_CLAIM_MODES_COUNTING_TOWARD_DAY`, so Option A was a one-gate change. It is a static method that ignores `today_iso`, because the answer does not vary by day. The assignment guard still runs first, so a stale entry cannot re-enter through this path.

       **Accepted consequence (must appear in the release note):** one completion of a `frequency = none` chore keeps the day satisfied on every later day, so a badge scoped only to it advances daily off that single completion. The alternative — counting it only until approved — was rejected because it is self-contradictory: open gives `0/1` unmet while completed gives `eligible_total == 0` neutral, so the badge could never advance and decision 11's pin would stay unsatisfiable.
     - ✅ `Days Minimum 5` with only 3 chores eligible must remain satisfiable by completing 5 selected chores (never permanently unmet), and the min-count variants must keep counting completions of non-due selected chores. Pinned in both directions by `TestMinimumCountKeepsAllSelectedScope`.
     - ✅ Pinned by `TestDatelessOneTimeChoreStaysInScope`: the single one-timer case and the all-one-timers case that must accumulate to the threshold rather than stall.
   8. ✅ Add the reference scenario from the "Days family: worked answers" section as a test: 5
     selected chores (3 dated, 2 dateless daily), asserting the three rows of that table — and
     confirm the outcomes are unchanged by this initiative, since both dateless chores are
     eligible. Implemented as `TestWorkedAnswersAreUnchanged`, with `_assert_scope_precondition` asserting the 3-of-5 eligible day so the ratio assertions cannot pass vacuously.
  9. ✅ Add the contract-trap tests, one per trap named in Phase 1 step 6, and the `never_overdue` case explicitly: skipping a due occurrence must still break the streak (the case a lateness-flag design gets wrong). Implemented as `TestStreakContractTraps` — four cases: the `never_overdue` skip still breaks; today's pending occurrence is not a miss; a chore added mid-streak reports no spurious miss (the anchor trap); and a break is not permanent (the recovery trap, which must still restart at 1).
  10. ✅ Parametrize across retention settings (including a low `retention_daily`) to prove the design does not depend on period history surviving. Implemented as `TestIndependentOfPeriodHistory`, which simulates the *outcome* of aggressive pruning by deleting the tracked chores' daily period buckets outright (the harness gained `clear_daily_period_history`). This is deliberately stronger than setting a `retention_daily` option value: `get_retention_config` reads config-entry options and the replay never runs the pruning job, so setting the option would not have applied it and the test would have been vacuous. Two cases: a neutral day still holds, and a skipped occurrence still breaks.
  11. ✅ Run the targeted suites, then the badge/gamification set, then the release-gate commands from [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) §2: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, `python -m pytest tests/ -v --tb=line`. **Done 2026-09-15 for the targeted and badge/gamification sets** (see the Phase 4 baseline). The full-directory run was declined deliberately — targeted runs were used instead, so a full-suite pass remains outstanding for the release step.
- **⚠️ Finding not in the plan — the recurrence rebases on the window start, so a widened probe is not a valid oracle for interval frequencies.** Occurrences land at **local midnight**, and `has_missed_occurrence_between` treats both bounds as exclusive, so the narrow window `[day, day + 1)` reports no miss on the very day an occurrence falls — the anchor day's own occurrence is the window's *lower bound*. Widening to `[day - 1, day + 1)` isolates one day's occurrence, which is what the harness probe uses.

  That probe is nonetheless invalid for `biweekly` and `monthly`, because `build_schedule_config` is called with `base_date_iso=window_start`: the recurrence **rebases on the anchor**, and for an `INTERVAL=2` frequency the base week's parity decides which days are occurrences. Verified — a biweekly Monday anchored `2026-08-31` yields `08-31, 09-14, 09-28`, while the same chore probed from `09-13` yields `09-21, 10-05`. Production is correct (the anchor only ever moves onto an occurrence day, so the phase stays aligned), but the probe describes a different schedule than production evaluates. Those two cases therefore assert the streak outcome only, and their docstrings say why — the alternative is an assertion that passes for the wrong reason.

  A second correction came from the same probe: a hand-picked 62-day monthly anchor genuinely **contained** a missed occurrence (`07-14 → 08-14 → 09-14`), so that case would have broken the streak instead of advancing it. Monthly offsets are now derived from the shipped engine (`consecutive_monthly_offsets`), since a month is not a fixed number of days.
- **Key issues**
  - **The harness identifiers were renamed for honesty.** `StreakDayReplay` → `PeriodicDayReplay` and `_add_streak_badge` → `_add_periodic_badge`, because the Days-family tests reuse both and the old names would have misled the next reader about what they drive. Applied across the three files that reference them (`test_badge_streak_midnight_reset`, `test_badge_progress_persistence`, `test_badge_streak_schedule_awareness`).
  - **Non-vacuity verified for the matrix, not assumed.** Replacing the neutral-hold branch (`eligible_total == 0` → `cycle_count`) with `0` fails 5 of the 13 cases — Mon/Wed/Fri, weekly, biweekly, monthly and the pending-occurrence trap. The hold assertions are therefore load-bearing rather than satisfied by an advancing or already-broken streak. Probe reverted, engine diff confirmed clean.
  - **Every matrix case asserts its own preconditions**, since decision 15 has the harness construct schedules. A case that mis-schedules itself would otherwise pass for the wrong reason; this caught three errors during implementation — the two probe/setup mistakes listed above, and the retention case that anchored a week before its occurrence and so measured a genuine miss rather than a neutral day.
  - Timezone correctness: the scheduling layer stores UTC while day keys are local. Follow the established convention in `tests/test_badge_period_end_cycles.py` (explicit `set_default_timezone` with `try/finally`) rather than relying on the default zone.
  - The full suite is a release step, not a CI gate — validate broadly before release, since cross-test state (the `dt_utils` default-timezone module global) can only appear in a full run.
  - Do not weaken the two existing break-semantics guards (`TestStreakStillBreaks`) to make new cases pass.

### Phase 5 – Docs, wiki & release notes

- **Goal**: Make the unified streak definition discoverable and explain the behaviour change.
- **Status**: ✅ **Complete** (2026-09-15).
- **Steps / detailed work items**
  1. ✅ Update the wiki to state that a streak counts consecutive **eligible occurrences**, that days
     where nothing is due are neutral. **Scope correction:** the plan said this applies to "chore streaks, achievements and badges alike" — that is true of **chore streaks and badges**, but **not achievements**: `_streak_alive` still gates on today-or-yesterday (conflict C2, deferred to Phase 6). The achievements page therefore documents the current calendar-day limitation and its scheduling, rather than overstating the fix. Files touched:
     - `choreops-wiki/Configuration:-Chores.md` — "How the schedule affects streaks" under Scheduling
     - `choreops-wiki/Advanced:-Chores.md` — "Chore streaks vs badge streaks", including why the pause rule is chore-specific
     - `choreops-wiki/Configuration:-Badges-Periodic.md` — full "Streak and days semantics" section (terms, worked Mon/Wed/Fri table, the unbounded-neutral-stretch note, both exceptions, the verbatim guidance, and an upgrading note)
     - `choreops-wiki/Configuration:-Achievements.md` — a `> [!WARNING]` stating the current limitation and pointing at the badge rules
  2. ✅ Document the two confirmed semantic decisions where users will look for them: that an
     unbounded stretch of neutral days keeps a streak alive (decision 6), and that legacy
     in-progress counts are not migrated (decision 7). Both are update-visible behaviour, so a
     short "what changed" note belongs in the periodic-badges page.
  3. ✅ **Per decision 9**, add equivalence wording to the option help text for the redundant pairs —
     two in the streak family, three in the days family — so users can pick either: the *Due* and
     non-*Due* spellings behave identically once "selected" means "due today".
  4. ✅ Update the badge target-type **help text** so the scope of the non-*Due* options is described accurately ("the selected chores that are due today"). **Two plan corrections:** there is no `strings.json` in this repo — `translations/en.json` is the master file — and the option **labels** live in `const.py` (`TARGET_TYPE_OPTIONS`), not in translations, so no label change was made and no regeneration step was needed. The guidance therefore went into the existing `data_description/target_type` strings for the periodic and daily badge steps (2 each, covering both the `config` and `options` copies), which is where the picker reads them from.
  5. ✅ **Recommended guidance to include verbatim in the badges wiki.**
  6. ✅ Document the two documented distinctions from decisions 10 and 11 in the same periodic-badges page.
  7. ✅ Add the streak definition to [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) so future
     work does not reintroduce calendar-day counting — including the `missed_since_advance`
     contract and its three traps, which are the easiest part of this design to re-break.
     Implemented as "Streak and Days target semantics (do not reintroduce calendar-day counting)" under the scheduling standards, covering the ownership rule, the neutral-day rule, why break detection must never be calendar-based, the two shared authorities and their caller-owned anchor/error policy, the three traps, and the occurrence-at-midnight / rebasing gotchas that cost time during Phase 4.
  8. ✅ Draft the release note describing the behaviour change. Drafted below, ready to paste into the release PR description — release notes have no dedicated file in this repo.
  9. ✅ Update `docs/ARCHITECTURE.md` for the shared schedule-config builder introduced in Phase 1, together with the caller-owned anchor and error policy. Corrected the stale `engines/schedule.py` path to `engines/schedule_engine.py` while there.
- **Key issues**
  - Wiki is a separate repository with no PR flow (commit directly to `choreops-wiki` `master`).
  - No new translation key was needed: the guidance extends existing `data_description` strings, so the `TRANS_KEY_*` rule does not apply here (that rule governs integration strings, and these are flow help text).

#### Release note draft

> **Badge streak and Days targets now respect each chore's schedule**
>
> Issue #294 fixed streaks being reset every night. This release fixes the wider defect behind it.
>
> **What changed**
>
> - A streak or Days badge counts consecutive *occurrences* of the chores you selected, not calendar days. A chore that is not due today no longer counts against the day, so a badge scoped to a mix of daily and weekly chores can be earned on days the weekly chore is absent. Previously such a badge stalled — and at a 100% threshold it could never accumulate at all, even at perfect compliance.
> - A day on which nothing is due is **neutral**: it neither advances nor breaks a streak. There is no limit on how long a neutral stretch can be, so a monthly chore's streak can span several months.
> - A missed occurrence breaks the streak on the **following** day, since on the day itself the occurrence has not yet passed.
> - The `Selected Chores` and `Selected Due Chores` options now behave the same way, because "selected" now means "selected and due today". No options were removed, so existing badges keep working either way.
> - `Days Minimum 3/5/7 Chores` options are **unchanged**: they count completed chores regardless of due date, because they are an absolute count rather than a ratio.
> - A selected chore with no schedule (one-time, no due date) counts on **every** day, including after it has been completed.
>
> **What to expect**
>
> - In-progress streak and days counts are not converted. They continue from where they are and self-correct on the next day that advances.
> - Badges already earned stay earned.
> - Some Days and Streak badges may advance more readily than before. This is the intended fix.
> - Achievement streak tracking is **unchanged** for now: it still uses calendar days, so it can differ from a badge streak on a non-daily chore. Bringing it in line is planned for a later release.

### Phase 6 – Streak subsystem unification — split into two tranches

- **Goal**: Remove the remaining calendar-day streak logic and the anti-patterns that would
  reintroduce it. **Not part of the badge fix release** (decision 14).
- **Why two tranches**: the original single phase bundled code hygiene with a behaviour change to
  achievements. Only the behaviour change is risky, needs product decisions, and needs field
  confirmation. Splitting lets the mechanical cleanup proceed immediately instead of waiting on the
  contested part.

| Tranche | Items | Risk | Gate |
| --- | --- | --- | --- |
| **6A** | O4, O5 | Low — dead code and a doc comment | None; can start now |
| **6B** | O3, C3 | Medium — changes what users' achievements report | Decisions 18–20 **and** field confirmation |

#### Phase 6A – Code hygiene (O4, O5) — UNBLOCKED

- **Goal**: Remove the dead calendar-day streak code and the stale field, so the anti-pattern cannot
  be reintroduced by reaching for either.
- **Entry criteria**: none beyond Phase 6A being started deliberately. Verified premises: `O4`'s
  `streak_yesterday` has no production consumer, and `O5`'s target pair has no production caller
  (the only two hits are the class docstring and the method's own example).
- **Steps / detailed work items**
  1. ✅ Premise verified — `streak_yesterday` is computed at `statistics_manager.py:2471` and returned
     at `:2482`; no production caller reads it. Two test files pass the key inertly
     (`test_badge_target_types.py:902`, `test_workflow_gamification_pending_queue.py:225`) and
     **neither asserts on its value**, so removal is low-risk.
  2. **O4 — document `last_update_day`'s two surviving roles** (same-day idempotency gate and
     miss-check anchor) with a typed comment at the definition site, then **delete `streak_yesterday`**
     and its `dt_add_interval` computation. Two roles remain, not three, once the field is gone.
  3. **O5 — delete `StatisticsEngine.update_streak` / `get_streak`** (`statistics_engine.py:333`,
     `:408`) and the 13 tests in `test_statistics_engine.py` that pin their calendar semantics.
  4. **O5 — fix the class docstring at `statistics_engine.py:60`**, which currently shows
     `stats.update_streak(...)` as usage. Deleting the method without this leaves the docstring
     documenting a method that no longer exists — the exact kind of stale guidance that caused this
     initiative.
  5. Run `tests/test_statistics_engine.py`, the badge/gamification set, and the release gates.
- **Key issues**
  - **Deleting a tested public method is a deliberate act.** State the rationale in the commit — dead
    generic API whose docstring documents calendar-yesterday logic as correct is a trap for the next
    contributor, which is why deletion beats fixing.
  - Removing `streak_yesterday` is a *read-path only* change: nothing persisted it, so no schema bump
    and no migration.
  - O4 and O5 are independent of each other and can land as two commits.

#### Phase 6B – Achievement alignment (O3, C3) — BLOCKED

- **Goal**: Remove the last calendar-day streak gate in the system by pointing `COMPLETION_STREAK`
  achievements at the shared missed-occurrence authority (closing conflict C2), and settle whether an
  open-ended chore can break a streak (conflict C3).
- **Entry criteria — BOTH must hold**:
  1. ✅ **Decisions 18, 19 and 20 confirmed** (2026-09-15). See the section below. One follow-up
     remains: whether decision 19 also applies to the **badge** path.
  2. ⛔ **The badge fix confirmed in the field — still outstanding.** Phases 0–5 merged 2026-09-15
     but the latest tag is `1.5.3-beta.1`, so the fix is **unreleased and no user has run it**.
     Starting 6B before that makes it impossible to attribute a new streak report to the right
     subsystem — which is the whole reason this criterion exists.
- **Steps / detailed work items**
  1. Replace `_streak_alive` (`gamification_manager.py:2893`) with the shared helper, per decision 19
     (error policy) and decision 20 (upper bound), then retire `_streak_alive`.
  2. Update `_get_tracked_current_streak` (`gamification_manager.py:2912`) and its stale docstring
     ("last completed today or yesterday"), plus the comment at `gamification_manager.py:620-622`
     which describes the zeroing behaviour being removed.
  3. Re-express the **5 of 13** tests in `test_gamification_streak_reset.py` that pin the calendar
     gate (`test_streak_alive_today_and_yesterday`, `test_streak_alive_two_days_ago_is_dead`,
     `test_streak_alive_handles_datetime_strings`, `test_streak_alive_fails_open`, and the
     B1 group around `:144`). Most keep the same *intent* — a genuinely missed day still breaks.
     **`test_streak_alive_fails_open` is the exception:** decision 19 reverses that policy, so it must
     be renamed and re-asserted to pin the new intent (unreadable data breaks the streak), not
     quietly adjusted — see the note under Phase 6B key issues.
  4. Settle C3 per decision 18: stop short-circuiting `FREQUENCY_NONE` in
     `has_missed_occurrence_between` and evaluate it on a daily recurrence, then delete
     `calculate_streak`'s inline `FREQUENCY_NONE` branch so the helper owns the rule. This also
     fixes the frozen-badge defect recorded under decision 17.
  5. Pass `unusable_schedule_counts_as_miss=True` per decision 19 — **but see the scope question
     there before changing the badge path.**
  6. Add achievement-side coverage mirroring the badge matrix: a weekly chore's achievement streak
     must accumulate instead of capping at 1, and an unscheduled chore's streak must break after a
     skipped day rather than freezing.
- **Key issues**
  - **O3 alone would regress open-ended streaks — verified.** For a `FREQUENCY_NONE` chore whose
    stored streak is 5 and was last completed 10 days ago: `_streak_alive` reports 0 (correct, it
    broke), but `has_missed_occurrence_between` short-circuits to `False` for `FREQUENCY_NONE`, so
    O3 alone would report **5 forever** while `calculate_streak` still resets the underlying streak
    to 1 on the next completion. That is conflict C3, which is why decision 18 ships with O3 rather
    than after it.
  - **`test_streak_alive_fails_open` must be inverted, not merely re-expressed.** It currently pins
    the fail-open policy that decision 19 reverses. Rename and re-assert it to pin the new intent —
    unreadable data breaks the streak — so the change is deliberate and visible rather than looking
    like a test that was quietly weakened.
  - O3 changes achievement behaviour and needs its own release note and validation pass.
  - The achievement streak is read through `max()` across tracked chores, so "the streak" is really
    "the best single chore streak". Worth confirming that stays intended.

#### Decisions 18–20 — CONFIRMED 2026-09-15

All three answer the same design question — *how should achievements match badges* — and none of them
introduces a new user-facing setting.

**Decision 18 — an unscheduled chore follows daily streak rules. (CONFIRMED, closes C3.)**

A chore with no due date and no recurrence is treated as if it were daily, for **badges and
achievements alike**: complete it every day and the streak builds; skip a day and it breaks to zero.

*Why:* the user never stated an intent for such a chore, so one must be inferred, and daily is the
only relatively logical model — "streak" already means consecutive days to a user, and a month-long
streak built from sporadic completions would be meaningless. It is explicitly accepted as a
compromise resting on an assumption.

*Side effect:* this also fixes the frozen-badge defect above. Without it, a badge scoped to an
unscheduled chore advanced once and then stalled permanently, because nothing was ever approved on
later days and nothing was ever detectably missed.

**Decision 19 — an unreadable schedule counts as a miss. (CONFIRMED against the recommendation.)**

When a chore's schedule cannot be evaluated, the streak breaks rather than holding.

*Why:* unreadable data is a distinct problem the user can notice and report; continuing the streak
silently would mask the underlying bug. This reverses the earlier recommendation to fail open.

*Accepted consequence:* a data defect will zero streaks rather than pass quietly, so the cause needs
to be visible — otherwise the user sees a lost streak with no explanation. This also removes the
policy split between callers, since `calculate_streak` already passes `True`.

*⚠️ Scope still to confirm:* the badge path currently passes `False`. Applying decision 19 to badges
changes **already-merged behaviour**, which warrants its own release-note entry and arguably its own
PR rather than riding along in 6B.

**Decision 20 — the miss window ends at the start of today. (CONFIRMED as recommended.)**

Matches the badge path exactly, so today's still-pending occurrence cannot break a streak mid-day.
Accepted consequence: the same documented one-day latch as badges — a missed occurrence breaks the
streak on the following day, because on the missed day itself the occurrence has not yet passed.
data keeps the streak.

*A user's expectation.* A data problem should never destroy progress the user earned. Punishing them
for the integration's inability to read a schedule is the worst outcome.

*Recommendation:* **pass `False`** (no miss on unusable data), preserving today's fail-open behaviour
and matching the badge policy. Rationale: it is the safe direction, it keeps achievements and badges
consistent, and an unusable schedule is a bug the user cannot act on. Passing `True` would newly zero
streaks on malformed data — a regression dressed up as consistency.

**Decision 20 — what is the upper bound of the achievement miss window?**

*Background.* The badge path bounds its window at **the start of today**, not "now". Using "now"
would mean today's still-pending occurrence counts as missed and breaks the streak mid-day. The
lower bound is the previous completion.

*A user's expectation.* A streak must not break while the day is still in progress and the chore has
not yet been done. This is precisely the #294 complaint.

*Recommendation:* **start of today**, matching the badge path exactly. Rationale: it is the fix for
the original bug and the only bound that cannot produce a mid-day false break. Accepted consequence:
the same one-day latch as badges — a missed occurrence breaks the streak on the **following** day,
because on the missed day itself the occurrence has not yet passed. This is inherent, already
documented for badges, and should be documented for achievements too.

**Decision 15/16 note:** no change. Tranche 6B reuses the same harness and preconditions approach.

#### Issue #122 — investigated, closed, OUT OF SCOPE (2026-09-15)

**#122 ("Align streak cutoff time with due date") is not being fixed.** It was investigated while
planning 6B and closed as a design question. The user's request was reasonable; there is simply no
generally correct answer. Record kept here so the analysis is not repeated.

**The request.** A daily chore due at 04:00 so it can be finished before bed; the reporter loses
achievement streak progress when completing after midnight.

**Why it cannot be fixed properly — the decisive finding: the miss check never reads the due time.**
Tested the same window against a chore due at 00:00, 04:00, 12:00, 20:00 and 23:00 — all five return
`missed = True`, and all five generate an identical occurrence series. `build_schedule_config` is
called with `base_date_iso=window_start`, so occurrences are generated from the **caller's anchor**
(the previous completion), never from the chore's due date or time. The due time reaches
*eligibility* and *overdue* handling, but not the miss maths. "Cutoff = due time" is therefore not a
parameter change; it requires re-anchoring occurrence generation on the due time, which is exactly
what the current design avoids.

Re-anchoring does not work cleanly either:

- **Circular for completion-anchored schedules.** For `custom_from_complete` the due date/time is
  *derived from* the completion, so "which day does this completion belong to?" would depend on a due
  time that depends on the completion. The codebase already works around the time-drift half of this
  — `custom_from_complete_date_only` exists for that reason.
- **The ambiguity is irreducible.** A 00:30 completion is equally "late for the just-passed 04:00" and
  "early for the next 04:00". Nothing in the data distinguishes the intent, so any rule is a
  convention rather than a correctness result.
- **A fixed cutoff only relocates the problem** — a user whose bedtime drifts past the chosen hour has
  the identical complaint.

**Why a day-boundary change would be intrusive.** Three competing notions of "today" already exist:

| Notion | Source | Conflict if streaks diverge |
| --- | --- | --- |
| Local midnight | `start_of_local_day`, period buckets, dashboards | Streak says Tuesday, charts say Monday |
| Chore reset boundary | `approval_reset_type` — per chore, and **absent for `upon_completion`** | No boundary to reuse in that case |
| Occurrence point-in-time | `has_missed_occurrence_between` | Completing before the due moment is not representable as "satisfied" |

A chore can already be `at_midnight_once` while due at 04:00, so the system holds two contradictory
turnover points for one chore. A streak cutoff would add a fourth.

Secondary hazards: **DST** (a 04:00 boundary on a transition night either does not exist or occurs
twice, and this code is deliberately DST-safe at these call sites), **retroactive re-attribution**
(changing a cutoff would silently shift existing streaks), and **partial benefit** (date-only chores
have no due time, so their cutoff is 00:00 either way).

**Conclusion.** #122 is a convention request, not a defect with a right answer. The only shape that
"always works" makes the boundary an explicit user-chosen convention applied to streak evaluation and
documented as intentionally disagreeing with the statistics buckets — a larger, more intrusive change
than 6B, trading one predictable limitation for a documented inconsistency. **Excluded from 6B.**

**Two side notes from the investigation, both resolved:**

1. **The workaround previously offered on #122 did not work.** The comment suggested tracking the
   streak with a periodic badge instead of an achievement, but the badge path uses the same normalised
   occurrence maths and breaks identically. The issue was closed with a corrected explanation.
2. **#122 was arguably mislabelled `enh: feature`** while describing lost credit for on-time work. It
   was closed as a design question, so this no longer needs resolving.

**What users can rely on instead,** and what the closing note states: consistency of timing matters
far more than the clock, so a steady bedtime keeps a streak intact (verified: 23:30 → 00:30 continues;
23:30 → 23:30 continues). **Days** and count-based targets are the forgiving alternatives, since they
accumulate rather than reset.

---

## Testing & validation

- **Commands (per phase, targeted):**
  - `python -m pytest tests/test_badge_streak_midnight_reset.py tests/test_gamification_engine.py -v`
  - `python -m pytest tests/test_badge_target_types.py tests/test_badge_no_overdue_cycles.py tests/test_badge_period_end_cycles.py tests/test_workflow_streak_schedule.py tests/test_gamification_streak_reset.py tests/test_schedule_engine_streaks.py -v`
  - Phase 1B adds: `python -m pytest tests/test_badge_schedule_snapshot.py -v` (extended with rotation /
    standby / stale-assignment / completed-still-counts cases)
  - Phase 1C adds: `python -m pytest tests/test_workflow_streak_schedule.py tests/test_schedule_engine_streaks.py -v`
    (must stay green unchanged — that is the proof the consolidation preserved behaviour)
- **Commands (release gate):**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- **Baseline for #294 (commit `73e97d5`):** new suite 6/6 pass; `test_gamification_engine.py` +
  `test_gamification_streak_reset.py` 64 pass; 7 badge/gamification suites 113 pass / 4 skip;
  `quick_lint.sh` green (ruff + mypy + 13 boundary checks).
- **Baseline for Phase 1 (commit `69335e5`):** `test_badge_schedule_snapshot.py` 19/19 pass;
  **12 badge + gamification suites 212 pass / 4 skip**; **5 statistics + chore suites 371 pass**
  (including `test_workflow_streak_schedule.py`, which proves the extracted
  `build_schedule_config` did not change `calculate_streak`); `quick_lint.sh` green with mypy
  0 errors.
- **Baseline for Phase 1B (commit `f94916e`, corrected 2026-09-14):**
  `test_badge_schedule_snapshot.py` **40/40 pass** (19 from Phase 1 + 21 Phase 1B cases); targeted
  set across `test_badge_schedule_snapshot`, `test_badge_streak_midnight_reset`,
  `test_gamification_engine`, `test_badge_target_types`, `test_rotation_fsm_states`,
  `test_rotation_primary_standby`, `test_rotation_services`, `test_workflow_streak_schedule`,
  `test_badge_no_overdue_cycles`, `test_shared_chore_features` → **193 passed**; `quick_lint.sh`
  green with mypy 0 errors. Phases 1C–6 must not regress these.
- **Baseline for Phase 1C (2026-09-14):** `test_missed_occurrence_authority.py` **27/27 pass**;
  targeted set across `test_missed_occurrence_authority`, `test_badge_schedule_snapshot`,
  `test_badge_streak_midnight_reset`, `test_workflow_streak_schedule`, `test_schedule_engine_streaks`,
  `test_gamification_engine`, `test_gamification_streak_reset`, `test_badge_target_types`,
  `test_badge_no_overdue_cycles`, `test_chore_engine` → **349 passed**; `quick_lint.sh` green with
  mypy 0 errors. Phases 2–6 must not regress these.
- **Baseline for Phase 2 (2026-09-14):** `test_gamification_engine.py` **52/52 pass** (47 + 5 new
  Days-family cases); targeted set across `test_gamification_engine`, `test_badge_streak_midnight_reset`,
  `test_badge_schedule_snapshot`, `test_missed_occurrence_authority`, `test_badge_target_types`,
  `test_badge_no_overdue_cycles`, `test_badge_period_end_cycles`, `test_badge_cumulative`,
  `test_gamification_streak_reset`, `test_gamification_shadow_comparison`,
  `test_workflow_gamification_pending_queue`, `test_workflow_streak_schedule`,
  `test_rotation_fsm_states`, `test_rotation_primary_standby`, `test_shared_chore_features` →
  **300 passed / 4 skipped**; `quick_lint.sh` green with mypy 0 errors.
  **Motivating regression confirmed fixed end to end:** 3 daily chores + 1 weekly not due today,
  all dailies done → the streak advances and reaches the threshold (was: capped at 1, then broke).
  Phases 3–6 must not regress these.
- **Baseline for Phase 3 (2026-09-14):** `test_badge_progress_persistence.py` **9/9 pass**;
  targeted set across the 16 badge, streak, gamification, rotation and shared-chore suites →
  **310 passed / 4 skipped**; `quick_lint.sh` green with mypy 0 errors.
  Phases 4–6 must not regress these.
- **Phase 4, steps 1–3 (2026-09-15, uncommitted):** `test_badge_streak_midnight_reset.py`
  **11/11 pass** (6 baseline + 4 prior + 1 new neutral-day case). Broader regression set across
  `test_badge_streak_midnight_reset`, `test_gamification_engine`, `test_badge_schedule_snapshot`,
  `test_missed_occurrence_authority`, `test_badge_progress_persistence`, `test_badge_target_types`,
  `test_badge_no_overdue_cycles`, `test_badge_period_end_cycles`, `test_gamification_streak_reset`,
  `test_workflow_streak_schedule`, `test_schedule_engine_streaks` → **247 passed**. `quick_lint.sh`
  green with mypy 0 errors. **Non-vacuity evidence recorded:** disabling `missed_since_advance` in
  `_evaluate_streak` fails both `TestStreakStillBreaks` guards; the probe was reverted with a clean
  engine diff.
- **Phase 4 complete (2026-09-15, uncommitted):** 24 new tests. `test_badge_days_scope.py` 9/9;
  `test_badge_streak_schedule_awareness.py` 15/15; `test_badge_streak_midnight_reset.py` 11/11;
  `test_badge_progress_persistence.py` 9/9 → **44 passed** across the four Phase 4 suites. Broader
  badge/gamification/rotation set across 13 suites → **290 passed**. Other consumers of the changed
  eligible-scope resolver (`test_statistics_engine`, `test_statistics_manager_report_rollup`,
  `test_chore_engine`, `test_chore_manager`, `test_due_today_after_assignment_change`,
  `test_dashboard_due_today_weekday_gating`) → **319 passed**. `quick_lint.sh` green with mypy 0
  errors. **Non-vacuity evidence:** replacing the neutral-hold branch with `0` fails 5 of the 13
  matrix cases; the probe was reverted with a clean engine diff.
  **⚠️ The full-directory run was deliberately skipped** (targeted runs only), so a full-suite pass
  is still outstanding for the release step. Phases 5–6 must not regress the 44 Phase 4 tests.
- **Outstanding tests:** none for Phase 4 — the schedule matrix and days-family coverage are in
  place. A full-directory run remains for the release gate.
- **Links to failing logs:** n/a.

---

## Notes & follow-up

### Opportunities surfaced during contract review

**O1/O2 were promoted to the critical path** (decisions 12, 13 — Phases 1B, 1C) because they close
defects that would otherwise ship:

1. **O1 — one "what must this assignee do today" notion.** Promoted to Phase 1B. Two definitions
   of *today* drive two user-visible features, and the schedule-only one would wrongly charge
   rotation/standby assignees. Resolved by naming the concepts apart (`scheduled_today` vs
   `counts_toward_today`) and having badges consume the legitimacy-aware one.
2. **O2 — one "missed occurrence since X" authority.** Promoted to Phase 1C. Three consumers
   answer the question differently today; consolidating removes the divergence that makes C2 and
   C3 possible, and is the prerequisite for O3.

**O3–O5 are deferred to Phase 6** (decision 14) — they change other subsystems and deserve separate
review:

3. **O3 — achievement streaks adopt the shared helper.** The highest-value item available: it
   closes conflict C2 and removes the last calendar-day streak gate in the system. Not in the badge
   release, because it changes achievement behaviour and must be attributable on its own.
4. **O4 — `last_update_day` now serves three roles** (same-day idempotency gate, miss-check anchor,
   and the source of `streak_yesterday`). No behaviour change intended; needs an explicit typed
   comment so a future writer understands the blast radius. Decide the fate of `streak_yesterday`
   at the same time.
5. **O5 — remove or fix the dead `StatisticsEngine.update_streak` / `get_streak` pair.** Dead
   generic API whose docstring documents calendar-yesterday logic as correct — precisely the
   anti-pattern this initiative removes. Deleting is preferred over fixing.
6. ✅ **DONE in Phase 1C — duplicate miss check removed.** `has_missed_occurrence_since_advance`
   was called twice per badge (once for the all-tracked snapshot, once for the due-only snapshot)
   for an identical answer. The manager now computes it once and passes it to both via
   `missed_since_advance`; verified one call per evaluation instead of two.

### Earlier opportunities (kept)

7. **`days_cycle_count` is not exposed on the badge progress sensor** (verified: `sensor.py`
   surfaces `status`, `overall_progress`, `criteria_met`, `last_update_day`). Anyone diagnosing a
   streak currently cannot see the counter. Consider exposing it while streak semantics are in
   flux — it would have made #294 self-evident and would make this change verifiable in the field.
8. **`_streak_alive` and the shared helper are the same question** for two systems — this is O3,
   now scheduled in Phase 6.

### Other notes

- **Relationship to #290 (`repair_streak`)**: this plan removes most of #290's motivation. Its two stated causes were (a) a single missed day killing the streak, and (b) pause/sick days not being exempt. After this initiative, days with nothing to do are neutral, and the remaining #290 case is narrower: a genuinely missed occurrence being excused after the fact. The repo memory note for #290 concluded it should **not** proceed before #294; the same applies here. Do not start #290 in parallel.
- **Fallback design (Option B) — do not take without a reason.** Instead of deriving misses from schedule math, persist a per-badge "last eligible occurrence" anchor and a `previous_cycle_count` on break. This is simpler in the engine but requires a schema bump, depends on retention for history lookups, and still fails the `never_overdue` case if implemented from lateness flags. Documented only so the choice in Phase 2 is an informed one.
- **Not in scope:** cumulative badge maintenance; the "Days" target family; challenge evaluation (disabled during sunset); the per-chore notification and dashboard grouping paths.
- **Known adjacent issue (not scheduled):** a `never_overdue` chore whose due date goes stale (`never_overdue` + daily + pending leaves a past due date that never advances) interacts with the "eligible today" rule. Phase 4 step 4 pins the streak behaviour; if the stale-due-date behaviour itself needs changing, it belongs in its own initiative.
- **Memory artefacts:** the verified #294 root cause, the #294 fix, and this schedule-divergence finding are recorded in `/memories/repo/badge-streaks.md`. Keep that file current as phases land so the finding is not re-derived.
