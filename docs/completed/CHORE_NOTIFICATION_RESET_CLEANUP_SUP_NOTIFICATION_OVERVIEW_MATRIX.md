# Supporting artifact: ChoreOps notification overview and lifecycle matrix

## Purpose

Create a ChoreOps-specific notification overview that can serve two jobs at once:

1. a maintainer-facing baseline matrix for Phase 3B lifecycle hardening
2. the starting source for a future user-facing notification overview page if the current ChoreOps docs tree still lacks one

This document is intentionally preserved as a completed contract artifact, not final user documentation. It consolidates the finalized ChoreOps behavior from the codebase and wiki for the archived notification lifecycle initiative.

## Source references used

- [docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_COMPLETED.md](CHORE_NOTIFICATION_RESET_CLEANUP_COMPLETED.md)
- [choreops-wiki/Configuration:-Notifications.md](../../choreops-wiki/Configuration:-Notifications.md)
- [choreops-wiki/Technical:-Notifications.md](../../choreops-wiki/Technical:-Notifications.md)
- [docs/completed/legacy-kidschores/NOTIFICATION_MODERNIZATION_EXECUTIVE_SUMMARY.md](../completed/legacy-kidschores/NOTIFICATION_MODERNIZATION_EXECUTIVE_SUMMARY.md)

## Documentation inventory finding

### What exists today

- ChoreOps wiki user-facing notification overview in [choreops-wiki/Configuration:-Notifications.md](../../choreops-wiki/Configuration:-Notifications.md)
- ChoreOps wiki technical notification architecture page in [choreops-wiki/Technical:-Notifications.md](../../choreops-wiki/Technical:-Notifications.md)
- Archived implementation record in [docs/completed/CHORE_NOTIFICATION_RESET_CLEANUP_COMPLETED.md](CHORE_NOTIFICATION_RESET_CLEANUP_COMPLETED.md)

### What appears missing in main docs

- No current notification overview or matrix was found under `docs/` outside the wiki and in-process planning material.
- No newer ChoreOps-specific notification matrix in `docs/` appears to supersede the wiki overview.

### Planning conclusion

- Use this artifact as the Phase 3B source-of-truth matrix.
- After implementation and validation, either:
  - promote a cleaned user-facing version into `docs/`, or
  - refresh the two wiki pages from this matrix and keep the formal contract in the completed initiative record.

## Canonical notification families

The current code and wiki imply three practical notification families:

| Family              | Scope                                                               | Typical audience                            | Current intent                                                                                     |
| ------------------- | ------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Assignee status     | Chore due-window, due reminder, overdue, post-action clear behavior | Assignee                                    | Latest valid chore state should be the only remaining assignee-facing state notification on device |
| Approver workflow   | Chore claimed, reward claimed, overdue action workflows             | Approver(s) associated to the assignee      | Clear stale approval-action notifications when claim is resolved or invalidated                    |
| System/gamification | Badge, achievement, challenge, penalty, bonus, system alerts        | Assignee and or approver depending on event | Independent alerts; not part of the chore state-collapse contract                                  |

Phase 3B is specifically about locking the assignee status family into one documented, testable lifecycle contract.

## Terminology and transport model

This initiative needs two separate vocabularies. Mixing them is what made the prior discussion fuzzy.

### Domain lifecycle terms

These describe what happened to the chore:

- due window opened
- due reminder became valid
- chore became overdue
- chore was claimed
- chore was approved
- chore was missed
- chore was reset
- chore deletion event occurred

These are product-state events. They are not notification transport operations.

### Notification transport operations

These describe how ChoreOps changes what is visible on the device:

- `replace`: send a newer notification using the same canonical tag or notification identity so it overwrites the prior one
- `clear`: send an explicit clear command for a specific previously-sent notification identity
- `compatibility clear`: clear legacy tags that may still exist from older paths while the system is being normalized

### Critical distinction

A chore can be deleted as a domain event, but notifications are not "deleted" as the transport primitive.

For Phase 3B, the transport primitives are:

- replace by canonical tag or notification identity
- clear by exact tag when replacement is not the right tool

## Explicit technical approach

The codebase and Companion App behavior support a precise policy.

### What the platform evidence says

- Tagged replacement is the native mechanism for making a newer mobile-app notification take the place of an older one.
- Explicit clear uses `message: clear_notification` plus the exact tag.
- Companion App docs note a real caveat for explicit clear: platform limitations may require the app to have been used recently, which especially affects iOS and non-critical Android notifications.
- Replacement therefore has better reliability as the primary mechanism when one transient state evolves into another transient state.
- Clear is still valid and required in several lifecycle cases, but it should not be the primary mechanism for ordinary transient-state progression when a direct replacement is available.

### ChoreOps transport policy

For one chore and one assignee:

1. `replace` is the primary mechanism for transient state progression inside one notification family.
2. `clear` is the primary mechanism when a notification becomes invalid and there is no successor notification to replace it.
3. `compatibility clear` may be used temporarily for legacy tag families, but it must not be treated as the canonical contract.

### Preferred operation by scenario

| Scenario                                       | Preferred transport operation | Why                                                                                          |
| ---------------------------------------------- | ----------------------------- | -------------------------------------------------------------------------------------------- |
| Due window -> due reminder                     | Replace                       | Same chore, same assignee, newer transient state                                             |
| Due reminder -> overdue                        | Replace                       | Same transient family; replacement is more reliable than a clear-only transition             |
| Due window -> overdue                          | Replace                       | Same transient family                                                                        |
| Due, reminder, or overdue -> claimed           | Clear                         | Claim invalidates the transient family and there is no new assignee transient successor      |
| Due, reminder, or overdue -> approved          | Clear                         | Final-state success is not the same transient family; stale transient prompt must be removed |
| Due, reminder, or overdue -> missed            | Clear                         | Final-state failure is not the same transient family                                         |
| Any invalidated approver workflow notification | Clear                         | Workflow is resolved or invalidated; no same-family successor is guaranteed                  |
| Chore deletion event                           | Clear                         | No chore-scoped notification should survive once the underlying record is gone               |

### Mobile push vs persistent notification fallback

The current implementation does not provide identical invalidation tools across both delivery backends.

#### Mobile app push path

- Replacement is supported through `tag`
- Explicit clear is supported through `message: clear_notification` plus `tag`
- This is the only path where the full replace-plus-clear contract currently exists

#### Persistent notification fallback path

- Replacement is supported today by reusing `notification_id`
- An explicit dismiss path is not currently wired in the reviewed ChoreOps runtime paths
- Phase 3B decision: keep persistent fallback behavior stable, but do not spend implementation time on parity work in this slice
- The strict replace-plus-clear lifecycle contract should be written for mobile-app notifications and documented as such if fallback limitations remain

### Canonical design decision to lock in

The cleanest technical contract is:

- one canonical assignee transient family per chore, keyed by the current `status` identity
- replacement for transient-to-transient transitions
- explicit clear for transient-to-terminal or transient-to-invalid transitions
- optional compatibility clears for old `due_window` and `overdue` tags until migration confidence is high
- `due reminder` belongs to that same canonical transient family
- `due reminder` must replace `due window`, and `overdue` must replace either earlier transient state

### Implementation note after Phase 3B execution

- Runtime now sends assignee `due window`, `due reminder`, and `overdue` notifications through the canonical `status` identity for mobile-app replacement.
- Claim, approval, reset, and chore deletion now clear that canonical assignee transient identity first.
- Legacy `due_window` and `overdue` tag clears remain in runtime only as compatibility clears.

## Proposed chore audit logic path

This section captures the intended audit rules for one chore across one chore cycle.

### Rule 1: only one live assignee transient state notification per chore

For one assignee and one chore, the transient state notifications are:

- due window
- due reminder
- overdue

These should behave as one collapsing family for that chore lifecycle.

Transport intent:

- use `replace` as the primary mechanism between these three states

If they are sent in sequence:

- `due window`
- `due reminder`
- `overdue`

then only the newest valid one should remain on device.

Locked decision:

- `due reminder` replaces `due window`
- `overdue` replaces `due reminder`
- `overdue` also replaces `due window` directly if the reminder was never shown

Example expected outcome:

- if a chore has already gone overdue, the assignee should not still have a due-window or due-reminder notification for that same chore
- overdue should be the only surviving transient state notification for that chore

### Rule 2: claimed, approved, and missed invalidate transient state notifications

If a chore enters any of these states:

- claimed
- approved
- missed

then no `due window`, `due reminder`, or `overdue` notification for that chore should remain on device.

Interpretation:

- `claimed` is not a final chore-cycle outcome, but it does invalidate the entire due-state notification family
- `approved` is a final successful outcome for the cycle
- `missed` is a final unsuccessful outcome for the cycle

Transport intent:

- use `clear` on the canonical transient family because there is no newer transient successor

### Rule 3: reset clears all non-final chore notifications

If a chore is reset for the current cycle, all notifications about that chore that are no longer valid should be cleared.

This includes at minimum:

- due window
- due reminder
- overdue
- claimed or approver workflow notifications that are invalidated by the reset

Transport intent:

- use `clear`, not replacement, because reset invalidates notifications rather than advancing them to a newer transient state

### Rule 4: final-state informational notifications are manual-dismiss only

The current preferred policy is:

- approved notifications remain until manually dismissed
- missed notifications remain until manually dismissed

These are treated as final-state informational notifications for that chore cycle, not transient state prompts.

### Rule 5: chore deletion is stronger than reset

If a chore deletion event occurs, all notifications for that chore should be cleared, including any final-state notification that would otherwise survive a normal reset.

Deletion removes the item itself, so no chore-specific notification should survive it.

Transport intent:

- use `clear` for every known chore-scoped notification identity because there is no valid replacement once the chore item no longer exists

## Audit classification model

To keep the implementation and tests organized, audit each chore notification path against these buckets.

### Bucket A: transient assignee state notifications

- due window
- due reminder
- overdue

Expected behavior:

- only one should remain at a time for one chore and one assignee
- any later valid transient state replaces or clears the earlier one
- any terminal or invalidating action clears all of them

### Bucket B: approver workflow notifications

- chore claimed
- chore overdue intervention notifications

Expected behavior:

- these are separate from the assignee transient family
- they must clear when the underlying workflow is resolved or invalidated
- they must not be delivered simply because a user has approver capability; association still controls routing

### Bucket C: final-state informational notifications

- chore approved
- chore missed

Expected behavior:

- these may remain until manually dismissed
- they should not be cleared by normal transient-state replacement
- they should be cleared if the chore itself is deleted

## Expanded transition checklist for the audit

Your base rules are the right core. These additional transition cases should be audited so the contract is complete.

| Transition or event                              | Expected result                                                                                                                                         |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Due window -> due reminder                       | Only due reminder remains                                                                                                                               |
| Due reminder -> overdue                          | Only overdue remains                                                                                                                                    |
| Due window -> overdue                            | Only overdue remains                                                                                                                                    |
| Due window or due reminder or overdue -> claimed | All transient assignee state notifications cleared                                                                                                      |
| Claimed -> approved                              | Any stale assignee transient notifications remain cleared; approver workflow clears; approved notification may remain                                   |
| Claimed -> disapproved                           | Any stale assignee transient notifications remain cleared; claim workflow clears; verify whether a new retry-style assignee notification is independent |
| Overdue -> skipped                               | Overdue and related approver workflow notifications cleared because the cycle was reset or rescheduled                                                  |
| Any transient state -> reset to pending          | All transient notifications for that chore cleared                                                                                                      |
| Any state -> chore deletion event                | All notifications for that chore cleared                                                                                                                |
| Overdue -> missed                                | All transient assignee state notifications cleared; missed notification may remain                                                                      |
| Claim undone or status reset helpers             | Any transient or workflow notification invalidated by the new state is cleared                                                                          |
| Due date edit or reschedule                      | Any no-longer-valid due, reminder, or overdue notification for the old timing is cleared                                                                |

## Recommended Phase 3B policy statement

If the team wants one simple rule to guide implementation and tests, use this:

> For one chore and one assignee, `due window`, `due reminder`, and `overdue` are transient state prompts and must never coexist once a newer valid state exists. Entering `claimed`, `approved`, `missed`, `reset`, `skip`, or `delete` must clear any invalid transient prompt for that chore. `approved` and `missed` may remain as manual-dismiss final-state notifications unless the chore itself is deleted.

## Chore notification event matrix

### Assignee-facing chore events

| Event             | Typical timing             | Recipient | Actions | Current documented intent                                      | Current runtime note                                                                                   | Phase 3B required contract decision                                                                    |
| ----------------- | -------------------------- | --------- | ------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Chore now due     | When due window opens      | Assignee  | Claim   | Replace older assignee state notification for same chore       | Sent as part of assignee status family                                                                 | Keep in canonical status family                                                                        |
| Chore reminder    | Before due time            | Assignee  | Claim   | Wiki currently says auto-clear yes                             | Runtime evidence indicates this can stack separately from overdue unless explicitly unified or cleared | Locked decision: reminder joins the canonical `status` replacement family                              |
| Chore overdue     | After due time passes      | Assignee  | Claim   | Should supersede earlier due-state notification for same chore | Real-device report shows claim cleanup can leave overdue notification behind                           | Must be cleared by claim, approval, and reset using the exact tag or notification family actually sent |
| Chore missed      | Strict missed path         | Assignee  | None    | Independent missed alert                                       | Not part of the current due/reminder/overdue lifecycle hardening scope                                 | Keep out of Phase 3B unless implementation uncovers overlap                                            |
| Chore approved    | After approver approval    | Assignee  | None    | Informational success message                                  | Should clear stale due or overdue state notifications first                                            | Must remain compatible with the canonical assignee clear contract                                      |
| Chore disapproved | After approver disapproval | Assignee  | None    | Informational retry or needs-work message                      | Not the core bug path, but stale earlier state alerts must not survive incorrectly                     | Confirm whether it clears or replaces prior assignee status notifications                              |

### Approver-facing chore events

| Event         | Typical timing             | Recipient              | Actions                     | Current documented intent                         | Phase 3B stance                                                                      |
| ------------- | -------------------------- | ---------------------- | --------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Chore claimed | When assignee claims chore | Associated approver(s) | Approve, Disapprove, Remind | Active workflow notification; clear when resolved | Preserve existing workflow semantics                                                 |
| Chore overdue | When chore goes overdue    | Associated approver(s) | Complete, Skip, Remind      | Active workflow notification for intervention     | Preserve existing workflow semantics, but verify self-role non-association edge case |
| Chore missed  | Strict missed path         | Associated approver(s) | None                        | Informational intervention alert                  | Out of main Phase 3B scope unless overlap emerges                                    |

## Reward and non-chore events

These remain in the wider notification system but are not the focus of the current lifecycle hardening slice.

| Event group                                   | Included here for completeness | Phase 3B impact                                                                      |
| --------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------------------ |
| Reward claimed, approved, disapproved         | Yes                            | Only indirect parity review if shared helper methods or tag-clearing code is touched |
| Badge, achievement, challenge, bonus, penalty | Yes                            | No direct Phase 3B behavior change expected                                          |

## Device lifecycle matrix for one chore

This is the most important contract artifact for Phase 3B.

| Transition                         | Expected device result for assignee                                                              | Status in current docs                    | Status in runtime evidence                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------- | ---------------------------------------------------------------------------- |
| Due window -> due reminder         | Due reminder replaces due window so only one current assignee transient notification remains     | Not explicit                              | Needs explicit validation                                                    |
| Due window -> overdue              | Only one current assignee state notification remains for that chore                              | Implied by smart replacement docs         | Needs explicit validation                                                    |
| Due reminder -> overdue            | Overdue replaces due reminder so only overdue remains for that chore                             | Not explicit enough                       | Currently ambiguous and likely inconsistent                                  |
| Due window -> claim                | Claim action invalidates the assignee due-state notification                                     | Documented as auto-clear yes              | Needs exact-tag cleanup verification                                         |
| Due reminder -> claim              | Claim action invalidates the assignee reminder notification                                      | Documented as auto-clear yes              | Real behavior needs explicit coverage                                        |
| Overdue -> claim                   | Claim action invalidates overdue notification on device                                          | Documented as auto-clear yes              | Known live regression                                                        |
| Overdue -> approved                | Approval clears stale overdue notification before or with success notification                   | Documented as auto-clear yes              | Needs exact-tag cleanup verification                                         |
| Any transient state -> missed      | No due, reminder, or overdue notification remains; missed may remain as final-state notification | Not clearly stated                        | Needs explicit validation                                                    |
| Due or overdue -> reset to pending | Reset clears stale actionable state notification from device                                     | Addressed by prior reset slice            | Already improved, but must remain compatible with Phase 3B tag normalization |
| Any state -> chore deletion event  | No notification for that chore remains                                                           | Partially implied by delete cleanup notes | Needs explicit contract wording                                              |

## Current documentation alignment gaps

### Gap 1: reminder behavior is underspecified

- [choreops-wiki/Configuration:-Notifications.md](../../choreops-wiki/Configuration:-Notifications.md) currently presents due, reminder, and overdue as separate moments and marks reminder auto-clear as yes.
- [choreops-wiki/Technical:-Notifications.md](../../choreops-wiki/Technical:-Notifications.md) describes smart replacement in broad terms, but still lists separate `overdue` and `due_window` tag patterns and does not lock the reminder contract tightly enough.
- Phase 3B now has an explicit decision: reminder is part of the canonical transient replacement family and must not stack with due or overdue.

### Gap 2: claim cleanup vs actual send family

- The current technical description implies assignee due and overdue notifications are comprehensively auto-cleared.
- Real-device evidence shows claim cleanup can miss the overdue notification that was actually sent.
- Phase 3B must not close until the send family and clear family are represented by one matrix and verified by tests.

### Gap 2B: replacement and clear are not described as separate tools

- Current docs talk about auto-clear and smart replacement, but they do not clearly say when ChoreOps prefers one over the other.
- The intended contract should explicitly say: transient progression uses replacement; invalidation without a successor uses clear.
- This distinction matters because platform docs describe stronger reliability for replacement than clear in some conditions.

### Gap 2C: persistent notification fallback has weaker invalidation tooling today

- The reviewed runtime paths support replacement for persistent notifications by reusing `notification_id`.
- The reviewed runtime paths do not yet expose a parallel explicit dismiss helper for persistent fallback in the assignee lifecycle cleanup paths.
- Phase 3B closeout should document this as an intentional scope boundary and confirm that fallback replacement behavior was not regressed.

### Gap 3: self-role scenarios are not documented

- Current docs describe recipients generically as assignees and approvers.
- They do not explicitly document the case where one Home Assistant user or ChoreOps user record can be both assignable and approver-capable in the system.
- Phase 3B should document the rule: approver delivery depends on association to the assignee, not merely role capability.

### Gap 4: final-state retention policy is not documented cleanly

- The docs talk clearly about auto-clearing transient notifications, but they do not clearly separate transient state prompts from final-state informational notifications.
- The current preferred audit direction is that `approved` and `missed` can remain until manually dismissed, while transient due-state prompts must be removed when invalidated.
- This distinction should be made explicit in both maintainer and user-facing documentation after Phase 3B.

## Proposed final documentation deliverables after Phase 3B

### Maintainer contract artifact

- Keep a completed version of this matrix with implementation evidence and test references in `docs/completed/`.

### User-facing overview target

- Publish a concise notification overview page modeled after the KidsChores-style matrix, but written specifically for ChoreOps terminology and current behavior.
- Minimum required sections:
  - event groups
  - recipients
  - action buttons
  - whether the notification replaces or clears earlier notifications
  - simple timeline example for due, reminder, overdue
  - clear statement about claim, approval, and reset cleanup

### Technical page refresh target

- Update the technical page so the replacement section uses the final canonical family language rather than a stale mix of `status`, `overdue`, and `due_window` examples if those are no longer the primary runtime contract.
- Add one explicit lifecycle table matching the transition matrix above.

## Builder and maintainer checklist

Before Phase 3B is considered complete, all of the following must be true:

1. One canonical assignee notification family contract is written and approved.
2. Reminder behavior is explicit, not inferred.
3. Claim, approval, and reset clear paths target the notification family actually sent.
4. Self-role but non-self-associated approver scenarios are tested.
5. Wiki user-facing and technical wording are refreshed to match the final behavior.
6. This matrix is updated with final runtime evidence and test references.
7. The final docs explicitly separate transient prompts from final-state informational notifications.

## Recommended follow-up placement

If the team wants a permanent docs-tree page after validation, the best candidate is a new page under `docs/` with a name like:

- `NOTIFICATION_OVERVIEW.md`, or
- `NOTIFICATION_MATRIX.md`

This completed artifact should be treated as the archived source-of-truth matrix for the finalized Phase 3B lifecycle contract.
