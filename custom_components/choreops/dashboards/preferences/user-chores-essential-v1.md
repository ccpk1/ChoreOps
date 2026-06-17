# user-chores-essential-v1 preferences

`user-chores-essential-v1` is a lightweight, chore-focused layout that keeps the strong grouping and filtering behavior from the earlier essentials path while using compact chore rows.

## Scale note

- This is an inline-only small-household template.
- It is intended for roughly `20-25` chores per user, with `~25` as the practical upper bound for reliable rendering.
- It is not a shard-aware high-density template and should not be used as the scale target for larger chore lists.

## Quick overview

- Lightweight by design: focuses on welcome + chores without adding extra dashboard complexity.
- Portable: the chores card can be copied into other dashboard views as a drop-in block.
- Portability note: this template is intentionally kept inline for easy copy/paste portability, but inline rendering can hit template-size limits at scale (commonly around ~25 chores, depending on data and labels). See [Known issues / limitations](#known-issues--limitations).
- Friendly for drag-and-drop workflows: keep defaults for a simple setup, then tune behavior with `pref_*` values.
- Supports practical organization controls (time buckets, labels, sorting, and state filtering).

## Color policy note

- This template follows the dashboard theme-first color policy.
- Home Assistant theme variables remain the default source for colors.
- The accent preferences below are intentional product-specific exceptions for chore-state semantics and are declared as template variables for easier long-term maintenance.

- Universal points precision
  - This template now reads the resolved precision mode from the assignee dashboard helper contract instead of a local `pref_points_precision` variable.
  - The source of truth is the ChoreOps General Options setting surfaced as `dashboard_config.points_precision`.
  - `fixed_0` remains the fallback when the helper value is missing during transition.

## Card: Chores

### Layout & Grid

- `pref_column_count` (default: `3`)
  - Grid columns for chore cards.
  - Allowed: positive integer.

### Time Buckets

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

### Exclude Filters

- `pref_exclude_completed` (default: `false`)
  - Hides completed chores.
  - If set to `true`, `completed` is automatically added to `pref_exclude_states` when missing.
  - Allowed: `true`, `false`.

- `pref_exclude_states` (default: `[]`)
  - Excludes chores by state.
  - Example: `['completed', 'completed_by_other', 'not_my_turn', 'missed']`.
  - Allowed: array of lowercase state strings.

- `pref_exclude_nonrecurring_no_due_date` (default: `false`)
  - Hides chores that are both non-recurring and missing a due date.
  - Daily chores without a due date are not affected.
  - Allowed: `true`, `false`.

- `pref_max_due_date_days` (default: `0`)
  - Hides chores whose due date is more than this many days ahead.
  - Applies only to chores that have a due date.
  - `0` disables the filter.
  - Allowed: `0` or a positive integer.

- `pref_exclude_group_list` (default: `[]`)
  - Excludes one or more rendered chore groups from the card.
  - Allowed values: `overdue`, `today_morning`, `today`, `this_week`, `later`, `standby`.
  - Exclusions apply after the dashboard resolves which groups exist.
  - If a listed group does not exist in the current configuration, it is ignored.
  - Example: `['later']` hides the Later bucket.
  - Example: `['later', 'this_week']` hides the Later and Due This Week buckets.
  - When `pref_use_today_grouping` is `true`, exclude both `today_morning` and `today` to hide all today chores.

- `pref_use_label_grouping` (default: `false`)
  - Groups chores by labels instead of time buckets.
  - Allowed: `true`, `false`.

- `pref_use_standby_grouping` (default: `true`)
  - Groups standbys into a dedicated standby section at the bottom of the chore list.
  - Actionable standbys (overdue global state + `can_claim=true`) still route to the overdue group.
  - Allowed: `true`, `false`.

- `pref_exclude_label_list` (default: `[]`)
  - Excludes chores containing any listed labels.
  - Example: `['junk_label', 'skip_this']`.
  - Allowed: array of label strings.

### Include Filters

Include filters run before all other filtering (Step 0 priority). When set, only chores matching the criteria are processed — all non-matching chores are skipped before exclude checks run.

- `pref_include_label_list` (default: `[]`)
  - Only includes chores that have at least one matching label. Higher priority than `pref_exclude_label_list`.
  - When set, chores without any matching label are skipped before any exclude checks run.
  - Example: `['shared_chores', 'kitchen']` only shows chores tagged with either label.
  - Allowed: array of label strings.

- `pref_include_group_list` (default: `[]`)
  - Only includes chores whose scheduled time bucket is in the list. Higher priority than `pref_exclude_group_list`.
  - Allowed values: `today`, `this_week`, `other`.
  - `today` includes due-today and overdue chores (both have `primary_group: today`).
  - `this_week` includes chores due this week.
  - `other` includes later-dated chores (maps to the Later bucket).
  - Example: `['today', 'this_week']` only shows chores due today or this week.
  - Example: `['other']` only shows later-dated chores.
  - Use `pref_exclude_states: ['overdue']` alongside `today` to hide overdue chores.

- `pref_include_state_list` (default: `[]`)
  - Only includes chores whose current state is in the list. Higher priority than `pref_exclude_states`.
  - Example: `['pending', 'due']` only shows pending and due chores.
  - Allowed: array of lowercase state strings.

### Labels & Sorting

- `pref_use_label_grouping` (default: `false`)
  - Groups chores by labels instead of time buckets.
  - Allowed: `true`, `false`.

- `pref_label_display_order` (default: `[]`)
  - Optional explicit label-group order.
  - Labels not listed still appear afterward in alphabetical order.
  - Allowed: array of label strings.

- `pref_sort_within_groups` (default: `by_state_and_date`)
  - Sorting mode inside each rendered group.
  - Allowed: `default`, `name_asc`, `name_desc`, `date_asc`, `date_desc`, `by_state_and_date`.

### Display

- `pref_show_chore_description` (default: `true`)
  - Shows the optional description row when a chore has non-empty description text.
  - When `false`, the description row is always hidden.
  - Allowed: `true`, `false`.

### Colors & Accents

- `pref_claim_accent` (default: `#a957fa`)
  - Accent color used for claimed and in-progress chore-state treatments.
  - Applies to the inline compact chore row in this template.

- `pref_due_accent` (default: `#ff9800`)
  - Accent color used for due-state highlights.
  - Applies to inline compact row border, icon, and due-text styling.

- `pref_overdue_accent` (default: `#ff4444`)
  - Accent color used for overdue and missed-state highlights.
  - Applies to inline compact row border, icon, and overdue action affordances.

- `pref_steal_accent` (default: `#F2C94C`)
  - Accent color used for `steal_available` treatments.
  - Applies to inline compact row due-text and action-affordance emphasis.

- `pref_standby_accent` (default: `#5B8DEF`)
  - Accent color used for `standby_available` (actionable standby) treatments.
  - Muted blue — noticeable but subdued, distinct from urgency signaling.
  - Applies to inline compact row button border, icon color, due-text color, and a subtle 5% background tint.

## Practical tuning examples

- Keep it minimal: set only `pref_column_count`, leave everything else as default.
- Hide done chores: add `completed` to `pref_exclude_states` (for example `['completed']`).
- Hide unscheduled one-off chores: set `pref_exclude_nonrecurring_no_due_date: true`.
- Hide long-range future chores: set `pref_max_due_date_days: 7`.
- Hide Later chores: set `pref_exclude_group_list: ['later']`.
- Build a label board: set `pref_use_label_grouping: true` and define `pref_label_display_order`.
- Prioritize urgent work: keep `pref_use_overdue_grouping: true` and use `pref_sort_within_groups: by_state_and_date`.

## Known issues / limitations

- Inline template rendering has a practical size ceiling. With richer chore metadata and labels, this layout can hit Home Assistant template output limits at around ~25 chores.
- Typical runtime error when this limit is exceeded:
  - `homeassistant.exceptions.TemplateError: Template output exceeded maximum size of 262144 characters`
- If you encounter this, reduce rendered chore volume (for example by state/label filters) or move to different template profile.
