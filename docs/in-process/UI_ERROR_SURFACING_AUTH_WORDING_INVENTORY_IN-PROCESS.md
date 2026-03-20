# Auth wording inventory

## Purpose

This document is the Phase 1 approval gate for auth/action wording in the UI error surfacing initiative.

It exists to answer one question before implementation changes any auth copy:

- Do we keep the currently surfaced auth/action identifiers as-is, or do we approve a small, explicit replacement list?

If the approved change list is empty, implementation proceeds with propagation-only behavior and no auth/action label changes.

## Current auth templates

Source:

- [custom_components/choreops/translations/en.json](/workspaces/choreops/custom_components/choreops/translations/en.json#L5088)
- [custom_components/choreops/const.py](/workspaces/choreops/custom_components/choreops/const.py#L3148)

Current templates:

- Assignee-scoped: `You are not authorized to {action} for this assignee.`
- Global: `You are not authorized to {action}.`

Current behavior:

- The `{action}` placeholder is populated directly from the `ERROR_ACTION_*` constants.
- That means surfaced messages currently use raw identifiers such as `claim_chores` and `adjust_points`.

## Approval rule

Approval options for each entry:

- `KEEP` = keep the current identifier exactly as-is
- `CHANGE` = replace with the explicitly listed new text
- `DEFER` = do not change in this initiative; revisit later if needed

Implementation rule:

- Only entries explicitly marked `CHANGE` after review may be edited.
- If no entries are marked `CHANGE`, no auth wording edits will be made in implementation.

## Inventory

| Action constant                   | Current value        | Current rendered message                                                                                             | Used by          | Usage locations                                                                                                                                                | Recommendation | Proposed replacement if approved | Notes                                                                |
| --------------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | -------------------------------- | -------------------------------------------------------------------- |
| `ERROR_ACTION_CLAIM_CHORES`       | `claim_chores`       | `You are not authorized to claim_chores for this assignee.`                                                          | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L363), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L1214)  | `KEEP`         | None                             | This is understandable and directly searchable for troubleshooting.  |
| `ERROR_ACTION_APPROVE_CHORES`     | `approve_chores`     | `You are not authorized to approve_chores.` or `You are not authorized to approve_chores for this assignee.`         | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L501), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L1310)  | `KEEP`         | None                             | Slightly technical, but still clear and low risk to leave unchanged. |
| `ERROR_ACTION_DISAPPROVE_CHORES`  | `disapprove_chores`  | `You are not authorized to disapprove_chores.` or `You are not authorized to disapprove_chores for this assignee.`   | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L674), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L1384)  | `KEEP`         | None                             | Not elegant, but specific and operationally clear.                   |
| `ERROR_ACTION_REDEEM_REWARDS`     | `redeem_rewards`     | `You are not authorized to redeem_rewards for this assignee.`                                                        | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L816), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L2002)  | `KEEP`         | None                             | Good enough for v1; likely understandable to users and maintainers.  |
| `ERROR_ACTION_APPROVE_REWARDS`    | `approve_rewards`    | `You are not authorized to approve_rewards.` or `You are not authorized to approve_rewards for this assignee.`       | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L954), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L2111)  | `KEEP`         | None                             | Same rationale as chore approval.                                    |
| `ERROR_ACTION_DISAPPROVE_REWARDS` | `disapprove_rewards` | `You are not authorized to disapprove_rewards.` or `You are not authorized to disapprove_rewards for this assignee.` | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L1126), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L2190) | `KEEP`         | None                             | Same rationale as chore disapproval.                                 |
| `ERROR_ACTION_APPLY_PENALTIES`    | `apply_penalties`    | `You are not authorized to apply_penalties.` or `You are not authorized to apply_penalties for this assignee.`       | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L1425), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L2264) | `KEEP`         | None                             | Technical, but still precise.                                        |
| `ERROR_ACTION_APPLY_BONUSES`      | `apply_bonuses`      | `You are not authorized to apply_bonuses.` or `You are not authorized to apply_bonuses for this assignee.`           | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L1274), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L2338) | `KEEP`         | None                             | Same rationale as penalties.                                         |
| `ERROR_ACTION_ADJUST_POINTS`      | `adjust_points`      | `You are not authorized to adjust_points.` or `You are not authorized to adjust_points for this assignee.`           | Button + service | [button.py](/workspaces/choreops/custom_components/choreops/button.py#L1603), [services.py](/workspaces/choreops/custom_components/choreops/services.py#L2402) | `KEEP`         | None                             | Directly maps to the feature name and likely helps troubleshooting.  |
| `ERROR_ACTION_REMOVE_BADGES`      | `remove_badges`      | `You are not authorized to remove_badges.`                                                                           | Service only     | [services.py](/workspaces/choreops/custom_components/choreops/services.py#L2469)                                                                               | `KEEP`         | None                             | Service-only path; low value to change now.                          |

## Optional alternative replacements

These are **not recommended by default**. They are listed only so approval can be explicit if preferences change.

| Current value        | Possible replacement |
| -------------------- | -------------------- |
| `claim_chores`       | `claim chores`       |
| `approve_chores`     | `approve chores`     |
| `disapprove_chores`  | `disapprove chores`  |
| `redeem_rewards`     | `redeem rewards`     |
| `approve_rewards`    | `approve rewards`    |
| `disapprove_rewards` | `disapprove rewards` |
| `apply_penalties`    | `apply penalties`    |
| `apply_bonuses`      | `apply bonuses`      |
| `adjust_points`      | `adjust points`      |
| `remove_badges`      | `remove badges`      |

These replacements are intentionally minimal. They would preserve the same semantic meaning while removing underscores only.

## Recommendation for approval

Recommended approval set:

- Mark **all entries `KEEP`** for v1.
- Do **not** introduce friendly action-label keys in this initiative.
- Focus implementation effort on error propagation, kiosk/user-link discoverability, and documentation.

Reasoning:

- The current identifiers are technical, but they are still understandable.
- They are specific enough to help with troubleshooting.
- Changing them adds scope without materially improving the core outcome of this initiative, which is surfacing the failure in the UI.

## Explicit decision block

Record approval here before Phase 2 implementation starts:

- Approval date: `2026-03-19`
- Reviewer: `User approval recorded in chat`
- Decision:
  - [x] Keep all current auth/action identifiers unchanged
  - [ ] Change only the entries explicitly listed below

Approved `CHANGE` list:

| Action constant | Approved replacement |
| --------------- | -------------------- |
| _None yet_      |                      |

If this table remains empty, implementation must not change the auth/action labels.
