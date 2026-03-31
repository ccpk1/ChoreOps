# admin-peruser-v1 preferences

This v1 template starts with a redesigned approval header and fixed per-user review context while preserving the existing downstream admin cards.

This template has configurable `pref_*` values across the Approval Center and downstream admin sections.

## Color policy note

- This template follows the dashboard theme-first color policy.
- Home Assistant theme variables remain the default source for colors.
- The accent preference below is an intentional product-specific exception for approval and claimed-state emphasis and is declared as a template variable for easier long-term maintenance.

- `pref_points_precision` (default: `fixed_0`)
  - Controls how point values are formatted in admin economy surfaces.
  - Applies to available points totals, weekly/average point metrics, point action chips, and bonus/penalty values.
  - `fixed_0` shows a rounded whole-number display for compact layouts.
  - `adaptive` shows whole numbers when possible, otherwise up to 2 decimals.
  - `fixed_1` always shows 1 decimal place.
  - `fixed_2` always shows 2 decimal places.
  - Allowed: `fixed_0`, `adaptive`, `fixed_1`, `fixed_2`.

## Card: Approval Center

- `pref_claim_accent` (default: `#a957fa`)
  - Accent color used by the per-user Approval Center's product-specific approval emphasis.
  - Applies to summary icon emphasis, lane header accents, approval row chips, and expanded-state border treatments that intentionally use the ChoreOps claim/request accent.

## Card: Approval actions

- `pref_column_count` (default: `2`)
  - Grid columns for approve/disapprove action buttons.
  - Allowed: positive integer.

## Card: Chore management

- `pref_claim_accent` (default: `#a957fa`)
  - Accent color used by Chore Management claimed and pending-claim status emphasis.
  - Applies to the chore-management status color map for claim-related states.
