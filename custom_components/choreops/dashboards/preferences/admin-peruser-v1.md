# admin-peruser-v1 preferences

This v1 template starts with a redesigned approval header and fixed per-user review context while preserving the existing downstream admin cards.

This template has configurable `pref_*` values across the Approval Center and downstream admin sections.

## Color policy note

- This template follows the dashboard theme-first color policy.
- Home Assistant theme variables remain the default source for colors.
- The accent preference below is an intentional product-specific exception for approval and claimed-state emphasis and is declared as a template variable for easier long-term maintenance.

- Universal points precision
  - This template now reads the resolved precision mode from the selected dashboard helper contract instead of a local `pref_points_precision` variable.
  - The source of truth is the ChoreOps General Options setting surfaced as `dashboard_config.points_precision`.
  - `fixed_0` remains the fallback when the helper value is missing during transition.

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
