# user-game-full-v1 preferences

`user-game-full-v1` is a modern full user layout that starts with the welcome + chores flow and reuses the production shared chore-row behavior.

## Quick overview

- Feature-complete chore UX: includes shared progress context, claim-mode nuance, overdue/missed context, and claim/approve/undo controls.
- Modular shared-template architecture: core chore-row logic is sourced from `templates/shared/button_card_template_user_chores_row_v1.yaml` and composed into published runtime templates.
- Portability note: copy from composed runtime templates (vendored output), not directly from shared fragment source files.
- Friendly for drag-and-drop workflows: keep defaults for a simple setup, then tune behavior with `pref_*` values.
- Supports practical organization controls (time buckets, labels, sorting, and state filtering).

## Card: Chores

- `pref_column_count` (default: `1`)
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

- `pref_show_chore_description` (default: `false`)
  - Shows the optional description row when a chore has non-empty description text.
  - When `false`, the description row is always hidden.
  - Allowed: `true`, `false`.

## Card: Rewards

- `pref_column_count` (default: `1`)
  - Grid columns for reward cards.
  - Allowed: positive integer.

- `pref_use_label_grouping` (default: `false`)
  - Groups rewards by label.
  - When `false`, rewards render in a single group.
  - Allowed: `true`, `false`.

- `pref_exclude_label_list` (default: `[]`)
  - Excludes rewards containing any listed labels.
  - Works with or without label grouping enabled.
  - Allowed: array of label strings.

- `pref_label_display_order` (default: `[]`)
  - Optional explicit label-group order when label grouping is enabled.
  - Any labels not listed still appear afterward.
  - Allowed: array of label strings.

- `pref_sort_rewards` (default: `default`)
  - Sorting mode inside each rendered reward group.
  - Allowed: `default`, `name_asc`, `name_desc`, `cost_asc`, `cost_desc`.

- `pref_show_reward_description` (default: `true`)
  - Shows reward description as a dedicated row when description text exists.
  - When `false`, description row is hidden even if reward has description.
  - Allowed: `true`, `false`.

## Practical tuning examples

- Keep it minimal: set only `pref_column_count`, leave everything else as default.
- Hide done chores: add `completed` to `pref_exclude_states` (for example `['completed']`).
- Build a label board: set `pref_use_label_grouping: true` and define `pref_label_display_order`.
- Prioritize urgent work: keep `pref_use_overdue_grouping: true` and use `pref_sort_within_groups: by_state_and_date`.
- Sort rewards by price: set `pref_sort_rewards: cost_asc`.
- Group rewards by labels: set `pref_use_label_grouping: true` and optionally define `pref_label_display_order`.
