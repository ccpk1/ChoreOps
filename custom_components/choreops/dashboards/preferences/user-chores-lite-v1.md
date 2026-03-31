# user-chores-lite-v1 preferences

`user-chores-lite-v1` is a dynamic lightweight profile intended for older devices and lower-capability frontend environments. It keeps the ChoreOps dashboard-helper sorting and grouping intelligence while using native Home Assistant cards for the visible UI.

## Quick overview

- Dynamic by design: chores and rewards are still generated from the dashboard helper at runtime.
- Native-card first: the rendered UI uses native `markdown` and `tile` cards.
- Lower-risk interaction model: tap triggers one selected workflow button; hold opens more-info for the related status sensor.
- Focused layout: exactly three top-level cards are rendered for the user view: header, chores, and rewards.

## Dependency policy

- Required custom dependency: `auto-entities`
- Explicitly not used by this profile:
  - `button-card`
  - Mushroom cards
  - `card-mod`

## Header card behavior

- Shows a welcome summary using translated labels.
- Includes chore-oriented summary counts such as overdue and due today.
- Shows points only when gamification is enabled.
- Does **not** include reward status or reward summary counts.
- `pref_points_precision` (default: `fixed_0`)
  - Controls how point values are formatted in the header.
  - `fixed_0` shows a rounded whole-number display for compact layouts.
  - `adaptive` shows whole numbers when possible, otherwise up to 2 decimals.
  - `fixed_1` always shows 1 decimal place.
  - `fixed_2` always shows 2 decimal places.
  - Allowed: `fixed_0`, `adaptive`, `fixed_1`, `fixed_2`.

## Card: Chores

- `pref_use_overdue_grouping` (default: `true`)
  - Shows a dedicated overdue group.

- `pref_today_grouping_mode` (default: `today_morning`)
  - Controls whether today chores are grouped into one or two buckets.
  - Allowed: `off`, `today`, `today_morning`.

- `pref_include_daily_recurring_in_today` (default: `true`)
  - Keeps recurring daily chores in today groups.

- `pref_use_this_week_grouping` (default: `true`)
  - Shows a due-this-week group.

- `pref_include_weekly_recurring_in_this_week` (default: `true`)
  - Keeps recurring weekly chores in the this-week group.

- `pref_exclude_completed` (default: `false`)
  - Hides completed chores.

- `pref_exclude_blocked` (default: `false`)
  - Hides blocked-result chores.
  - Adds `completed_by_other`, `not_my_turn`, and `missed` to the effective exclusion list.

- `pref_exclude_states` (default: `[]`)
  - Excludes chores by state.

- `pref_use_label_grouping` (default: `false`)
  - Groups chores by labels instead of time buckets.

- `pref_exclude_label_list` (default: `[]`)
  - Excludes chores containing any listed labels.

- `pref_label_display_order` (default: `[]`)
  - Optional explicit label-group order.

- `pref_sort_within_groups` (default: `by_state_and_date`)
  - Sorting mode inside each rendered group.
  - Allowed: `default`, `name_asc`, `name_desc`, `date_asc`, `date_desc`, `by_state_and_date`.

## Chore action selection

The lite profile uses one tap action per chore tile.

- Default priority:
  - `claim_button_eid`
  - then `approve_button_eid`
- Claimed/in-progress priority:
  - `disapprove_button_eid`
  - then `approve_button_eid`
- Hold action opens more-info on the chore status sensor.

## Rewards card behavior

- Reward state is shown on the reward tile itself rather than repeated in the header.
- Rewards are grouped into `Available`, `Requested`, `Approved`, and `Locked` sections.
- Empty reward state uses the translated `no_rewards` copy.

## Reward action selection

The lite profile uses one tap action per reward tile.

- Default priority:
  - `claim_button_eid`
  - then `approve_button_eid`
- Requested priority:
  - `disapprove_button_eid`
  - then `approve_button_eid`
- Hold action opens more-info on the reward status sensor.

## Practical tuning examples

- Keep the light default behavior: change nothing and let the helper-provided sorting do the work.
- Hide completed chores: set `pref_exclude_completed: true`.
- Hide blocked-result chores on shared/rotation heavy installs: set `pref_exclude_blocked: true`.
- Prefer label buckets over time buckets: set `pref_use_label_grouping: true` and provide `pref_label_display_order`.
