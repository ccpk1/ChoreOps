# user-chore-essentials-v1 preferences

`user-chore-essentials-v1` is a lightweight, chore-focused layout that keeps the strong grouping/filtering logic from `user-essential-v1` while using compact chore rows.

## Quick overview

- Lightweight by design: focuses on welcome + chores without adding extra dashboard complexity.
- Portable: the chores card can be copied into other dashboard views as a drop-in block.
- Portability note: this template is intentionally kept inline for easy copy/paste portability, but inline rendering can hit template-size limits at scale (commonly around ~25 chores, depending on data and labels). See [Known issues / limitations](#known-issues--limitations).
- Friendly for drag-and-drop workflows: keep defaults for a simple setup, then tune behavior with `pref_*` values.
- Supports practical organization controls (time buckets, labels, sorting, and state filtering).

## Card: Chores

- `pref_column_count` (default: `3`)
  - Grid columns for chore cards.
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

- `pref_sort_within_groups` (default: `by_state_and_date`)
  - Sorting mode inside each rendered group.
  - Allowed: `default`, `name_asc`, `name_desc`, `date_asc`, `date_desc`, `by_state_and_date`.

- `pref_show_chore_description` (default: `true`)
  - Shows the optional description row when a chore has non-empty description text.
  - When `false`, the description row is always hidden.
  - Allowed: `true`, `false`.

## Practical tuning examples

- Keep it minimal: set only `pref_column_count`, leave everything else as default.
- Hide done chores: add `completed` to `pref_exclude_states` (for example `['completed']`).
- Build a label board: set `pref_use_label_grouping: true` and define `pref_label_display_order`.
- Prioritize urgent work: keep `pref_use_overdue_grouping: true` and use `pref_sort_within_groups: by_state_and_date`.

## Known issues / limitations

- Inline template rendering has a practical size ceiling. With richer chore metadata and labels, this layout can hit Home Assistant template output limits at around ~25 chores.
- Typical runtime error when this limit is exceeded:
  - `homeassistant.exceptions.TemplateError: Template output exceeded maximum size of 262144 characters`
- If you encounter this, reduce rendered chore volume (for example by state/label filters) or move to different template profile.
