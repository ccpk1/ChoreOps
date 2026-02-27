# user-minimal-v1 preferences

This template has configurable `pref_*` values in the chores card.

## Card: Chores

- `pref_column_count` (default: `4`)
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
