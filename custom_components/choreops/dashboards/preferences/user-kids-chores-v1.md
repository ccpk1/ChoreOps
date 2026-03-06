# user-kids-chores-v1 preferences

`user-kids-chores-v1` is a kid-focused chores layout based on `user-chores-v1` semantics, with larger, simpler, friendlier button-card tiles.

## Quick overview

- Keeps baseline color/state/action semantics aligned with the user chores experience.
- Kid-style tile UX: larger icon and title, simplified status/readout, and clearer tap target.
- Action model is intentionally simplified: tap to claim/approve when available, hold for more-info.
- Friendly for drag-and-drop workflows: keep defaults for a simple setup, then tune behavior with `pref_*` values.
- Supports practical organization controls (time buckets, labels, sorting, and state filtering).

## Card: Chores

- `pref_column_count_mobile` (default: `2`)
  - Grid columns for chore cards on mobile-width screens (`max-width: 768px`).
  - Allowed: positive integer.

- `pref_column_count_wide` (default: `5`)
  - Grid columns for chore cards on wider screens (`min-width: 769px`).
  - Allowed: positive integer.

- `pref_use_overdue_grouping` (default: `true`)
  - Shows a dedicated overdue group.
  - Allowed: `true`, `false`.

- `pref_use_today_grouping` (default: `true`)
  - Splits today chores into AM and PM groups.
  - Allowed: `true`, `false`.

- `pref_include_daily_recurring_in_today` (default: `true`)
  - Keeps recurring daily chores in today groups.
  - When `false`, those chores move to “other” grouping logic.
  - Allowed: `true`, `false`.

- `pref_use_this_week_grouping` (default: `true`)
  - Shows a dedicated due-this-week group.
  - Allowed: `true`, `false`.

- `pref_include_weekly_recurring_in_this_week` (default: `true`)
  - Keeps recurring weekly chores in this-week group.
  - When `false`, those chores move to “other” grouping logic.
  - Allowed: `true`, `false`.

- `pref_exclude_completed` (default: `false`)
  - Hides completed chores.
  - If set to `true`, `completed` is automatically added to `pref_exclude_states` when missing.
  - Allowed: `true`, `false`.

- `pref_exclude_states` (default: `[]`)
  - Excludes chores by state.
  - Example: `['completed', 'completed_by_other', 'not_my_turn', 'missed']`.
  - Allowed: array of lowercase state strings.

- `pref_use_label_grouping` (default: `false`)
  - Groups chores by labels instead of time buckets.
  - Allowed: `true`, `false`.

- `pref_exclude_label_list` (default: `[]`)
  - Excludes chores containing any listed labels.
  - Example: `['junk_label', 'skip_this']`.
  - Allowed: array of label strings.

- `pref_label_display_order` (default: `[]`)
  - Optional explicit label-group order.
  - Labels not listed still appear afterward in alphabetical order.
  - Allowed: array of label strings.

- `pref_sort_within_groups` (default: `default`)
  - Sorting mode inside each rendered group.
  - Allowed: `default`, `name_asc`, `name_desc`, `date_asc`, `date_desc`, `by_state_and_date`.

- `pref_show_chore_description` (default: `false`)
  - Reserved for compatibility with shared preference patterns.
  - Kids tile layout keeps the card simplified and does not render description content.
  - Allowed: `true`, `false`.

## Practical tuning examples

- Keep it kid-simple: keep `pref_column_count_mobile: 2`, `pref_column_count_wide: 5`, and `pref_sort_within_groups: default`.
- Hide done chores: add `completed` to `pref_exclude_states` (for example `['completed']`) when you want only actionable tiles.
- Build a label board: set `pref_use_label_grouping: true` and define `pref_label_display_order`.
- Prioritize urgent work: keep `pref_use_overdue_grouping: true` and use `pref_sort_within_groups: by_state_and_date`.
