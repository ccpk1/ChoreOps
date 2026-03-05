# Dashboard UI Design Guideline

**Version**: 0.5.0-beta.5 | **Last Updated**: 2026-03-04

This guide defines the visual system for standard ChoreOps dashboards. Use it with `docs/DASHBOARD_TEMPLATE_GUIDE.md`: the template guide defines build/runtime contracts, while this document defines consistent presentation.

## Scope and intent

- Keep chore state understandable at a glance for kids and admins
- Keep template variants visually consistent across user and admin views
- Standardize typography, color semantics, icon usage, and state signaling

> [!NOTE]
> The primary chore icon (user-selected) must remain visible and recognizable in every state.

## State communication model (multi-channel)

A chore state should be communicated through one or more of these channels, depending on card density:

1. **Text only**: localized label (`Upcoming`, `In Progress`, etc.)
2. **Text + state color**: label rendered with the mapped Lovelace CSS variable
3. **Primary icon color**: chore icon color changes by state
4. **Action/status icon**: secondary icon communicates available action or block reason
5. **Card accent/border**: outline or left accent border uses state color for quick scanning

Use at least two channels on compact cards and at least three channels on dense admin grids.

### State source precedence (required)

For state and status rendering, use canonical backend attributes before any
frontend-derived calculation:

1. `global_state` (preferred for shared/global status presentation)
2. `state` (fallback when `global_state` is unavailable)
3. `can_claim` + `claim_mode` (action gating and blocker semantics)

Derived UI calculations are allowed only when a canonical attribute does not exist
(for example, rendering a shared-all progress fraction from
`assigned_user_names` and `completed_by`).

Do not replace canonical status attributes with frontend heuristics when those
attributes are available.

### State vs global-state responsibilities (required)

Use a strict responsibility split to avoid mixed semantics in shared chores:

- `state` (per-user state) controls per-user presentation channels only:
  - line-2 status text
  - primary chore icon color
  - per-user action affordance styling
- `global_state` controls shared/global presentation channels only:
  - shared badge color (`shared_all`, `shared_first`, `rotation`)
  - shared progress-bar color and completion semantics
  - line-3 shared progress/completion status gating and labels

Shared-all completion gating rule:

- Treat `completed_in_part` as partial/in-progress global state (not full complete).
- Render success/green shared-all badge and progress bar only when `global_state`
  is globally complete (`completed`, `already_approved`, or
  `completed_by_other`).
- Numeric progress completion (`X/X`) may be shown as progress context, but must
  not by itself force global-complete color semantics.

## Typography and emphasis

Use a compact, predictable scale:

| UI Element               | Recommended size | Weight | Notes                                       |
| ------------------------ | ---------------- | ------ | ------------------------------------------- |
| Chore title (`primary`)  | `16px`           | `600`  | Keep to one line when possible              |
| State/meta (`secondary`) | `13px`           | `400`  | Use for due text, sibling context, progress |
| Badge text               | `12px`           | `500`  | Short labels only                           |
| Section headers          | `18px`           | `700`  | Keep spacing tight for dashboard density    |
| Helper/footnote text     | `12px`           | `400`  | De-emphasized, never primary signal         |

Emphasis rules:

- Use weight before increasing font size
- Reserve all-caps for short badge tokens only
- Do not rely on color alone; always pair with icon or text

## Standard text emoji and MDI mappings

Use these emoji for inline text contexts (for example markdown summaries, compact status strings, or helper text). Use the MDI icon in Lovelace card `icon` fields.

| Item type    | Standard emoji | Closest MDI icon     | Alternate MDI icon   | Usage note                                           |
| ------------ | -------------- | -------------------- | -------------------- | ---------------------------------------------------- |
| Points       | `⭐`           | `mdi:star`           | `mdi:star-circle`    | Numeric point totals and score highlights            |
| Chores       | `🧹`           | `mdi:broom`          | `mdi:clipboard-list` | Chore lists and chore section headings               |
| Badges       | `🥇`           | `mdi:medal`          | `mdi:shield-star`    | Badge progress and earned badge summaries            |
| Rewards      | `🎁`           | `mdi:gift`           | `mdi:gift-open`      | Reward catalogs and reward claim status              |
| Bonuses      | `✨`           | `mdi:sparkles`       | `mdi:star-plus`      | Positive admin adjustments and bonus callouts        |
| Penalties    | `💥`           | `mdi:alert-octagon`  | `mdi:minus-circle`   | Negative admin adjustments and penalty alerts        |
| Achievements | `🏆`           | `mdi:trophy`         | `mdi:trophy-award`   | Achievement milestones and unlock cards              |
| Challenges   | `🏁`           | `mdi:flag-checkered` | `mdi:flag-variant`   | Challenge start/finish states and challenge sections |

> [!TIP]
> Prefer MDI icons for interactive cards and controls; reserve emoji for text-first contexts where quick scanning is more important than strict icon uniformity.

## Card state styling rules

For blocked or exception states (`waiting`, `missed`, `not_my_turn`, `completed_by_other`):

- Set card opacity to `0.6`
- Flatten heavy shadows/elevation
- Disable primary action button
- Replace action button with status indicator icon

### Claim mode contract (`can_claim` + `claim_mode`)

Use claim capability as the single action truth for claim buttons:

- If `can_claim` is `true`, claim action is enabled and `claim_mode` should be an actionable mode (`claimable` or `steal_available`).
- If `can_claim` is `false`, claim action is disabled and `claim_mode` should be one of:
  - `blocked_completed_by_other`
  - `blocked_already_approved`
  - `blocked_pending_claim`
  - `blocked_waiting_window`
  - `blocked_not_my_turn`
  - `blocked_missed_locked`

UI behavior rule:

- Disable claim action whenever `can_claim` is `false`.
- Show a localized blocker label derived from `claim_mode` only for blocked/exception presentation.
- Treat `state` as display semantics only (color/icon/text), not as claim-action gating.
- Keep terminal completion display state as `completed` (there is no separate `approved` display state).

For high-attention states (`due`, `overdue`):

- Apply state color to icon and border accent
- Keep contrast high for label legibility
- For `overdue`, tie the action affordance icon and outline to `var(--error-color)`

## Metadata stamp presentation

Use metadata stamps as lightweight troubleshooting context, not as a primary UX signal.

Stamp content contract:

- `META STAMP: {template_id} • {release} • {generated_at}`

Placement and visual rules:

- Place the metadata stamp at the top of each card template block immediately after the card header comment marker.
- Keep stamp text in de-emphasized styling relative to `primary`/`secondary` card text.
- Do not replace state communication channels with stamp text.
- Keep stamp formatting compact and consistent across user and admin templates.

## Core per-user states (actionable)

| State       | Display label | Standard hex | Lovelace CSS variable       | Action button icon  | Standard behavior                                   |
| ----------- | ------------- | ------------ | --------------------------- | ------------------- | --------------------------------------------------- |
| `pending`   | Upcoming      | `#4A4A4A`    | `var(--primary-text-color)` | `mdi:arrow-right`   | Neutral icon; start affordance                      |
| `due`       | Due           | `#FF9800`    | `var(--warning-color)`      | `mdi:arrow-right`   | Orange highlight on icon/accent                     |
| `claimed`   | In Progress   | `#A957FA`    | `var(--primary-color)`\*    | `mdi:check-all`     | Solid action button; undo visible                   |
| `completed` | Done          | `#4CAF50`    | `var(--success-color)`      | `mdi:check`         | Green check icon + neutral outline; action disabled |
| `overdue`   | Overdue       | `#F44336`    | `var(--error-color)`        | `mdi:alert-octagon` | Error-colored action icon + outline                 |

\* Optional theme override for claimed purple:

```yaml
choreops-claimed-color: "#A957FA"
```

## Blocked and exception states (per-user)

| State                | Display label | Standard hex | Lovelace CSS variable        | Status indicator icon       | Context behavior                    |
| -------------------- | ------------- | ------------ | ---------------------------- | --------------------------- | ----------------------------------- |
| `waiting`            | Waiting       | `#9E9E9E`    | `var(--disabled-text-color)` | `mdi:clock-outline`         | Dependency blocked                  |
| `missed`             | Missed        | `#F44336`    | `var(--error-color)`         | `mdi:lock-outline`          | Window closed; locked               |
| `not_my_turn`        | Not Your Turn | `#9E9E9E`    | `var(--disabled-text-color)` | `mdi:account-lock-outline`  | Show `Currently: [Sibling Name]`    |
| `completed_by_other` | Done by Other | `#9E9E9E`    | `var(--disabled-text-color)` | `mdi:account-check-outline` | Show `Completed by: [Sibling Name]` |

### Action affordance style defaults (chore rows)

- Use `var(--primary-text-color)` as the default action icon color when no state-specific override applies
- Use a `2px` actionable outline for default claimable states (commonly `var(--primary-color)`)
- For `completed`, keep action button background transparent, icon `var(--success-color)`, and a neutral outline (`1px` disabled-text)
- For `steal_available`, use gold emphasis (`#F2C94C`) for the button treatment and keep icon color theme-adaptive (`var(--primary-text-color)`)

## Collaborative mode behaviors

### Shared All (teamwork)

- Global progress may be partial (`claimed_in_part`, `completed_in_part`)
- Keep card visible until global completion
- Show team progress context (for example `📊 1/3 Done`)
- Add a compact progress marker (for example 4px micro progress bar) on each shared-all chore row
- When shared-all reaches full completion, accent the shared badge icon (`mdi:account-group`) with success color
- Use explicit completion copy for full completion (for example `Completed: 3/3`)

### Shared First (race)

- When global state becomes `claimed` or `completed`, non-winners move to `completed_by_other`
- Show winner context immediately: `Claimed first by [Name]`

### Rotation (turn-based)

- Active user gets normal actionable presentation
- Non-active users show `not_my_turn` blocked presentation
- Always show current turn holder in secondary text

## UI modifiers and badges

| Modifier type   | Description                                    | Standard hex | Lovelace CSS variable        | Icon                          | Placement                            |
| --------------- | ---------------------------------------------- | ------------ | ---------------------------- | ----------------------------- | ------------------------------------ |
| Steal Available | Claim window can be stolen by another assignee | `#F2C94C`    | `var(--warning-color)`       | `mdi:hand-back-right-outline` | Secondary status + action affordance |
| Shared (All)    | All assignees must complete                    | `#9E9E9E`    | `var(--disabled-text-color)` | `mdi:account-group`           | Appended to chore name               |
| Shared (First)  | First assignee to claim wins                   | `#9E9E9E`    | `var(--disabled-text-color)` | `mdi:flag-checkered`          | Appended to chore name               |
| Rotating        | Assignment shifts by schedule                  | `#9E9E9E`    | `var(--disabled-text-color)` | `mdi:account-sync`            | Appended to chore name               |
| Recurring       | Chore repeats automatically                    | `#9E9E9E`    | `var(--disabled-text-color)` | `mdi:repeat`                  | Prepended to frequency text          |
| Bonus           | Positive admin points                          | `#4CAF50`    | `var(--success-color)`       | `mdi:star-plus` / `mdi:gift`  | Admin action grids                   |
| Penalty         | Negative admin points                          | `#F44336`    | `var(--error-color)`         | `mdi:alert-octagon`           | Admin action grids                   |

Steal color application rule:

- Apply the gold steal treatment only when `claim_mode` is `steal_available`
- Do not apply steal styling for generic blocked states

## Implementation checklist (template authors)

- Keep primary chore icon visible in all states
- Map each state to text + icon + color (minimum two channels)
- Use Lovelace variables first; avoid hardcoding colors where possible
- Add sibling context text for `not_my_turn` and `completed_by_other`
- Keep badge semantics consistent across user/admin templates

## Companion references

- Build/runtime contracts: `docs/DASHBOARD_TEMPLATE_GUIDE.md`
- Canonical template sources: `choreops-dashboards/templates/`
