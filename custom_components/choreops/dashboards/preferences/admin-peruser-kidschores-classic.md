# admin-peruser-kidschores-classic preferences

This template has configurable `pref_*` values in approval action layout.

## Scale note

- This is an inline-only classic admin template.
- It is intended for smaller households, roughly in the same `20-40` chores-per-user range as the other inline-only classic layouts.
- It is not a shard-aware high-density admin template.

- `pref_points_precision` (default: `fixed_0`)
  - Controls how point values are formatted in classic admin summary and chore-value displays.
  - `fixed_0` shows a rounded whole-number display for compact layouts.
  - `adaptive` shows whole numbers when possible, otherwise up to 2 decimals.
  - `fixed_1` always shows 1 decimal place.
  - `fixed_2` always shows 2 decimal places.
  - Allowed: `fixed_0`, `adaptive`, `fixed_1`, `fixed_2`.

## Card: Approval actions

- `pref_column_count` (default: `2`)
  - Grid columns for approve/disapprove action buttons.
  - Allowed: positive integer.
