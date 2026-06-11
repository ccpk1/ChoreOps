# Gamification Impact Analysis: User Chore Pause

**Created**: 2026-06-07 | **Status**: Analysis complete
**Based on**: `USER_CHORE_PAUSE_PLAN_IN-PROCESS.md`

---

## Summary

Pausing a user's chores has predictable downstream effects on badges, achievements, challenges, streaks, and points. The pause guards suppress the two most impactful signals (`CHORE_OVERDUE`, `CHORE_MISSED`), but other gamification-triggering signals (`CHORE_APPROVED`, `CHORE_DISAPPROVED`, `CHORE_STATUS_RESET`) may still fire through pre-existing claims or midnight auto-approval (see Q3 gap).

**Recommendation**: Document the behavioral caveats. The complexity of making gamification "pause-aware" is prohibitive for MVP and would require significant assumptions about user intent. This is analogous to the existing behavior when admins push chore due dates — stats and badges reflect what actually happened, not what "would have happened" under different conditions.

---

## Signal Flow: What gamification sees during pause

GamificationManager listens to these signals (line 115-143):

| Signal | Suppressed by pause? | Impact if it fires |
|--------|---------------------|-------------------|
| `CHORE_APPROVED` | Partial — midnight auto-approval (Q3) and manual approval (Q8) still fire | Badge progress increments, points awarded, streaks update |
| `CHORE_DISAPPROVED` | No guard | Streak may reset, stats updated |
| `CHORE_STATUS_RESET` | Partial — midnight reset may fire (Q3) | Badge cycle may advance |
| `CHORE_OVERDUE` | ✅ Suppressed (Phase 2 Step 3) | No impact |
| `CHORE_MISSED` | ✅ Suppressed (Phase 2 Step 4) | No impact |
| `POINTS_CHANGED` | Not affected by chore pause | Can fire from rewards, bonuses, penalties |
| `REWARD_APPROVED` | Not affected | Rewards still work for paused users |
| `BONUS_APPLIED` | Not affected | Bonuses still work |
| `PENALTY_APPLIED` | Not affected | Penalties still work |
| `MIDNIGHT_ROLLOVER` | Not affected | Triggers badge cycle evaluation, cumulative maintenance checks |

---

## Impact by gamification element

### Badges — Periodic

**How they work**: Period badges (weekly, monthly, custom) check stats like "chores completed this week" against a threshold. Triggered by `CHORE_APPROVED` and `MIDNIGHT_ROLLOVER`.

**During pause**:
- No new chore completions → badge progress stalls
- A weekly "5 completions" badge: paused all week → 0 completions → badge not earned
- A monthly "20 completions" badge: paused for 2 weeks → ~10 completions (if they did chores the other 2 weeks)

**When unpaused**: Badge evaluation resumes normally at next trigger. Missed periods are not retroactively counted.

**User impact**: Period badges may be harder or impossible to earn during the pause window. This is correct behavior — the user didn't do chores during that time.

---

### Badges — Cumulative

**How they work**: Cumulative badges track lifetime totals (total points, total completions) with optional maintenance thresholds. Triggered by `CHORE_APPROVED`, `MIDNIGHT_ROLLOVER`, and `POINTS_CHANGED`.

**During pause**:
- No new points or completions → lifetime totals don't increase → badge stays at current tier
- If maintenance is enabled: the maintenance period may expire without meeting the threshold → badge can **demote**
- Example: "Gold Star" badge requires 50 completions per month to maintain. Paused for a month → maintenance fails → badge demotes to "Silver Star"

**When unpaused**: Maintenance cycle resumes. If the badge demoted during pause, the user must re-earn it.

**User impact**: Cumulative badge demotion is the most significant gamification impact. A user paused for legitimate reasons (vacation, illness) could lose a hard-earned badge tier. This is analogous to the existing behavior when due dates are pushed — if fewer chores are completed in a period, maintenance may fail.

---

### Achievements

**How they work**: Achievements track thresholds like "100 lifetime completions" or "earn 500 points in 30 days." Triggered by the same signals as badges.

**During pause**:
- Lifetime achievements: progress stalls but doesn't regress (no penalty)
- Time-limited achievements: the clock keeps ticking. A "100 completions in 30 days" achievement becomes harder — if paused for 14 days, they have 16 effective days
- Points-based achievements: may still progress from non-chore sources (rewards, bonuses)

**When unpaused**: Achievement evaluation resumes. Time already elapsed is not recovered.

**User impact**: Time-limited achievements with short windows are most affected. Lifetime achievements are minimally affected (just delayed).

---

### Challenges

**How they work**: Time-limited challenges with a start/end date window. Triggered by `CHORE_APPROVED` and other workflow signals.

**During pause**:
- Challenge window keeps ticking regardless of pause
- If the full challenge window falls within the pause period → challenge expires with 0 progress
- If partially overlapping → reduced opportunity to complete

**When unpaused**: Challenge continues if still within the window. Expired challenges remain expired.

**User impact**: Challenges with short windows that overlap significantly with the pause period may be impossible to complete. Admins should consider challenge windows when planning pauses.

---

### Streaks

**How they work**: Consecutive day/week counters for chore completions. Updated by `CHORE_APPROVED` signals.

**During pause**:
- No completions → streak breaks at the next midnight
- A "7-day streak" resets to 0 after the first midnight with no completion

**When unpaused**: Streak starts from 0 on the next completion day.

**User impact**: Streaks always break during pause. This is unavoidable — by definition, the user didn't complete chores on those days.

---

### Points

**How they work**: Point balance tracked in user data. Updated by `CHORE_APPROVED` (chore points), `REWARD_APPROVED` (reward spending), `BONUS_APPLIED`, `PENALTY_APPLIED`.

**During pause**:
- Chore points: no new points earned (correct — no chores completed)
- Reward points: paused users CAN still redeem rewards with existing points
- Bonus/penalty points: unaffected by pause

**When unpaused**: Point earning resumes with next chore completion.

**User impact**: No penalty. Paused users don't lose points they already have.

---

## Why we can't fix this (and shouldn't try)

Making gamification "pause-aware" would require:

| What you'd need | Why it's hard |
|----------------|---------------|
| Track pause periods per user | New storage structure. Must handle overlapping pause/unpause cycles |
| Adjust badge thresholds based on pause | What's the formula? Paused 5 of 7 days → threshold becomes 5 × (2/7)? |
| Freeze time-limited windows | Challenges, achievements with deadlines — should the clock pause? |
| Handle partial periods | Paused for 3 hours vs 3 days vs 3 weeks — different impacts |
| Decide: "freeze" or "exclude"? | Freeze = everything stops and resumes. Exclude = pretend the time didn't happen. Both have edge cases |
| Cumulative maintenance | If maintenance period is 30 days and user is paused for 15, should the requirement be halved? |
| Streak preservation | Should a paused user keep their streak? What if pause is 1 day vs 30 days? |
| Badge demotion rollback | If a badge demoted during pause, should it auto-re-promote on unpause? Based on what? |

Each of these requires assumptions about user intent. A user paused for vacation might want their streak preserved (they're "still committed"). A user paused for punishment might deserve the streak break. The system can't know.

---

## Precedent: This already happens with date pushes

The existing "Push Chores Forward" feature has analogous effects on gamification:

- Pushing a chore's due date forward means fewer completions in the current period
- Badge maintenance may fail because fewer chores were "due" in the window
- Streaks may break if no chores are due on a given day
- These are accepted as correct behavior — stats reflect what actually happened

The pause feature is the same class of problem: an administrative action that changes what chores are processed, with cascading effects on gamification that are correct given the data but may feel surprising.

---

## Recommended approach

### For MVP: Document the caveats

Add a section to the wiki/ARCHITECTURE.md and user documentation:

> **Gamification during chore pause**
>
> When a user's chores are paused:
> - Period badges may not be earnable during the pause window
> - Cumulative badge maintenance may demote if thresholds aren't met
> - Time-limited achievements and challenges continue to count down
> - Streaks will break on the first midnight with no completion
> - Existing points and earned badges are preserved
> - The user can still redeem rewards and receive bonuses/penalties
>
> These effects are correct — they reflect the user's actual chore activity during the pause. To minimize impact, admins should consider badge cycles and challenge windows when planning pauses. Use Push Chores Forward to align due dates with the return date to keep period stats consistent.

### For future: Pause-aware gamification (deferred)

If pause-aware gamification becomes a priority, approach it as a separate feature:

1. Add a `gamification_frozen` flag that pauses ALL gamification evaluation for a user (not just chores)
2. Store the freeze window start/end
3. Adjust badge thresholds proportionally based on freeze duration
4. This is a separate initiative — not part of `user-chore-pause`

---

## Updated plan changes

Add to the plan's Edge Cases Catalog:

| Priority | Edge case |
|----------|-----------|
| High | Cumulative badge maintenance may demote during pause. Document as expected behavior. |
| High | Streaks always break during pause. No fix needed. |
| Medium | Time-limited challenges/achievements continue counting down during pause. Admins should consider challenge windows. |
| Low | Paused users can still redeem rewards with existing points. By design. |

Add to the plan's Documentation phase (Phase 7):

> `[ ]` Add "Gamification during chore pause" section to wiki and ARCHITECTURE.md, documenting expected behavioral caveats for badges, achievements, challenges, streaks, and points.

> **Analysis created**: 2026-06-07 | **Recommendation**: Document only. No code changes for gamification.
