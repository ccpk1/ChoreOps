# user-kidschores-classic-v1 preferences

`user-kidschores-classic-v1` is the classic kid-focused user layout. It keeps the original multi-card structure with configurable `pref_*` values.

## Scale note

- This is an inline-only small-household template.
- It is intended for roughly `20-40` chores per user.
- It is not a shard-aware high-density template and should not be used as the scale target for larger chore lists.

- Universal points precision
  - This template now reads the resolved precision mode from the assignee dashboard helper contract instead of a local `pref_points_precision` variable.
  - The source of truth is the ChoreOps General Options setting surfaced as `dashboard_config.points_precision`.
  - `fixed_0` remains the fallback when the helper value is missing during transition.

## Card: Chores

- `pref_column_count` (default: `2`)
  - Grid columns for chore buttons.
  - Allowed: positive integer.
- `pref_use_overdue_grouping` (default: `true`)
  - Show a dedicated overdue group.
  - Allowed: `true`, `false`.
- `pref_use_today_grouping` (default: `true`)
  - Show dedicated due-today groups.
  - Allowed: `true`, `false`.
- `pref_include_daily_recurring_in_today` (default: `true`)
  - Keep recurring daily chores in today group.
  - Allowed: `true`, `false`.
- `pref_use_this_week_grouping` (default: `true`)
  - Show dedicated due-this-week group.
  - Allowed: `true`, `false`.
- `pref_include_weekly_recurring_in_this_week` (default: `true`)
  - Keep recurring weekly chores in this-week group.
  - Allowed: `true`, `false`.
- `pref_exclude_completed` (default: `false`)
  - Hide completed chores from the display.
  - Allowed: `true`, `false`.
- `pref_exclude_nonrecurring_no_due_date` (default: `false`)
  - Hide chores that are both non-recurring and missing a due date.
  - Daily chores without a due date are not affected.
  - Allowed: `true`, `false`.
- `pref_max_due_date_days` (default: `0`)
  - Hide chores whose due date is more than this many days ahead.
  - Applies only to chores that have a due date.
  - `0` disables the filter.
  - Allowed: `0` or a positive integer.
- `pref_exclude_group_list` (default: `[]`)
  - Exclude one or more rendered chore groups from the card.
  - Allowed values: `overdue`, `today_morning`, `today`, `this_week`, `later`.
  - Exclusions apply after the dashboard resolves which groups exist.
  - If a listed group does not exist in the current configuration, it is ignored.
  - Example: `['later']` hides the Later bucket.
  - Example: `['later', 'this_week']` hides the Later and Due This Week buckets.
  - When `pref_use_today_grouping` is `true`, exclude both `today_morning` and `today` to hide all today chores.
- `pref_use_label_grouping` (default: `false`)
  - Group chores by labels.
  - Allowed: `true`, `false`.
- `pref_exclude_label_list` (default: `[]`)
  - Exclude chores that contain any listed labels.
  - Allowed: array of label strings.
- `pref_label_display_order` (default: `[]`)
  - Optional explicit label group order.
  - Allowed: array of label strings.
- `pref_sort_within_groups` (default: `default`)
  - Sorting mode per group.
  - Allowed: `default`, `name_asc`, `name_desc`, `date_asc`, `date_desc`.

## Card: Rewards

- `pref_column_count` (default: `1`)
  - Grid columns for reward cards.
  - Allowed: positive integer.
- `pref_use_label_grouping` (default: `false`)
  - Group rewards by labels.
  - Allowed: `true`, `false`.
- `pref_exclude_label_list` (default: `[]`)
  - Exclude rewards that contain listed labels.
  - Allowed: array of label strings.
- `pref_label_display_order` (default: `[]`)
  - Optional explicit label group order.
  - Allowed: array of label strings.
- `pref_sort_rewards` (default: `default`)
  - Sorting mode per reward group.
  - Allowed: `default`, `name_asc`, `name_desc`, `cost_asc`, `cost_desc`.

## Card: Showcase

- `pref_show_penalties` (default: `true`)
  - Show or hide penalty summary section.
  - Allowed: `true`, `false`.
