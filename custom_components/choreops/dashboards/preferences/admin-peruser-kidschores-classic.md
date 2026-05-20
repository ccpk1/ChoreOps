# admin-peruser-kidschores-classic preferences

This template has configurable `pref_*` values in approval action layout.

## Scale note

- This is an inline-only classic admin template.
- It is intended for smaller households, roughly in the same `20-40` chores-per-user range as the other inline-only classic layouts.
- It is not a shard-aware high-density admin template.

- Universal points precision
  - This template now reads the resolved precision mode from the selected dashboard helper contract instead of a local `pref_points_precision` variable.
  - The source of truth is the ChoreOps General Options setting surfaced as `dashboard_config.points_precision`.
  - `fixed_0` remains the fallback when the helper value is missing during transition.

## Card: Approval actions

- `pref_column_count` (default: `2`)
  - Grid columns for approve/disapprove action buttons.
  - Allowed: positive integer.
