# user-gamification-v1 preferences

This template has multiple cards with configurable `pref_*` values.

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
- `pref_exclude_approved` (default: `false`)
  - Hide approved chores from the display.
  - Allowed: `true`, `false`.
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
