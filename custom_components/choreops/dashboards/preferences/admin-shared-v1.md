# admin-shared-v1 preferences

`admin-shared-v1` is the shared admin approval board. It shows every user who currently has pending chore or reward approvals, with each user rendered as a compact lane of actionable approval rows.

## Quick overview

- Slim admin header: the shared admin view starts with a compact top-level admin header.
- Shared board layout: all users with pending approvals are shown together in one admin view.
- Lane-based review flow: each user gets a summary header plus stacked approval rows.
- Portable row structure: approval rows are fully self-contained button-card definitions rather than depending on a separate shared row template.
- Collapsible Approval Center: the top summary header supports persisted collapse state.
- Management: a separate profile-selection section sits after the Approval Center and is intended for downstream admin-action cards, not approval filtering.
- This document covers the supported template-level `pref_*` surface only.

## Card: Approval Center

- `pref_ui_control_key_root` (default: `admin-shared/approval-center`)
  - Sets the shared-admin `ui_control` branch used by the shared Approval Center header.
  - Override this only when you intentionally want another shared-admin instance to store its collapse state separately.
  - Example custom values: `admin-shared/approval-center`, `admin-shared/approval-center-compact`, `dashboards/admin/main/approval-center`.
  - Use slash-delimited segments without relying on a leading slash.

- `pref_default_header_collapsed` (default: `false`)
  - Sets the default Approval Center header state when no persisted UI override exists.
  - `false` means expanded by default.
  - `true` means collapsed by default.
  - If pending approvals exist, the template currently prefers opening the header unless a stored override is already present.
  - Allowed: `true`, `false`.

- `pref_primary_tint_mix_pct` (default: `14`)
  - Controls the percent of `var(--primary-color)` mixed into the collapsed Approval Center header background and border treatment.
  - Higher values create a stronger collapsed-state tint.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Controls whether the collapsed Approval Center header uses a tinted background fill.
  - Expanded state continues to use the template's admin-specific surfaced styling.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Controls whether the collapsed Approval Center header shows the thin full border treatment.
  - Expanded state continues to use the template's admin-specific surfaced styling.
  - Allowed: `true`, `false`.

## Card: Management

- `pref_selector_ui_control_key_root` (default: `admin-shared/admin-target-selector`)
  - Sets the shared-admin `ui_control` branch used by the selector header collapse state.
  - Override this only when you intentionally want another shared-admin instance to store its selector-collapse state separately.
  - Allowed: slash-delimited string path.

- `pref_selector_default_header_collapsed` (default: `false`)
  - Sets the default selector section state when no persisted UI override exists.
  - `false` means the selector chips are expanded by default.
  - `true` means the selector chips are hidden until the selector header is expanded.
  - Allowed: `true`, `false`.

- `pref_selector_primary_tint_mix_pct` (default: `14`)
  - Controls the percent of `var(--primary-color)` mixed into the selector header background and border treatment when collapsed.
  - Allowed: integer from `0` to `100`.

- `pref_selector_show_header_background` (default: `true`)
  - Controls whether the collapsed selector header uses a tinted background fill.
  - Allowed: `true`, `false`.

- `pref_selector_show_header_thin_border` (default: `true`)
  - Controls whether the collapsed selector header shows the thin full border treatment.
  - Allowed: `true`, `false`.

- `pref_selector_column_count` (default: `3`)
  - Controls how many inline admin-target chips are shown per row.
  - Values below `1` are clamped back to `1`.
  - Allowed: integer `1+`.

- Management behavior
  - The selector section is separate from the Approval Center and uses the system admin selector entity resolved by the shared admin setup snippet.
  - Its collapse state is shared page chrome and persists under the shared-admin helper, not under any selected user.
  - It is intended to set the current admin-action target for downstream admin cards.
  - The Approval Center continues to show all approvals and does not use this selector as a filter.
  - The section uses an Approval Center-style clickable summary header with a persisted collapse toggle and inline chips for `None` and each available user.
  - The summary header keeps the current review target on the right side.
  - The label simplifies to `Selected profile` only when a user is currently selected; otherwise it shows the chooser guidance.

## Card: Chore management

- `pref_chore_management_ui_control_key_root` (default: `admin-shared/chore-management`)
  - Sets the selected-user `ui_control` branch used by the Chore Management header collapse state.
  - Allowed: slash-delimited string path.

- `pref_chore_management_default_header_collapsed` (default: `false`)
  - Sets the default Chore Management state when no persisted UI override exists.
  - `false` means the chore selector body is expanded by default.
  - `true` means the section stays collapsed until expanded.
  - Allowed: `true`, `false`.

- `pref_chore_management_primary_tint_mix_pct` (default: `14`)
  - Controls the percent of `var(--primary-color)` mixed into the header background and border treatment when collapsed.
  - Allowed: integer from `0` to `100`.

- `pref_chore_management_show_header_background` (default: `true`)
  - Controls whether the collapsed header uses a tinted background fill.
  - Allowed: `true`, `false`.

- `pref_chore_management_show_header_thin_border` (default: `true`)
  - Controls whether the collapsed header shows the thin full border treatment.
  - Allowed: `true`, `false`.

- `pref_chore_selector_column_count` (default: `3`)
  - Reserved for future expanded chore-management layouts.
  - The current simplified baseline does not render inline chore chips, so this value has no visible effect yet.
  - Allowed: integer `1+`.

- `pref_chore_action_column_count` (default: `4`)
  - Reserved for future expanded chore-management action layouts.
  - The current simplified baseline does not render the action grid, so this value has no visible effect yet.
  - Allowed: integer `1+`.

- Chore management behavior
  - The Chore Management card currently provides a stable baseline shell for the shared admin chore workflow.
  - It depends on the selected profile from the Admin target selector and uses that profile's `chore_select_eid` helper.
  - Its collapse state follows the currently selected user, so each user can keep an independent open or closed state.
  - The header follows the same clickable summary pattern as the Approval Center and Management section.
  - When expanded, the section renders only the selected profile's chore selector entity.
  - If no profile is selected, the card renders a single guidance card instead of broken child cards.
  - If a selected profile does not expose a chore selector helper, the card renders a single configuration-error message instead of cascading broken cards.
  - The removed detail and action flows are intentionally deferred until the simpler selector baseline is confirmed stable.

Recommended ranges:

- `0` = no primary tint in collapsed state
- `10` to `18` = subtle themed tint
- `25+` = much stronger collapsed-state emphasis

- Approval Center header collapse state
  - The shared Approval Center header supports a persisted collapse toggle.
  - The template uses the branch from `pref_ui_control_key_root` and stores the state at `header-collapse` under that root.
  - Expanding from a stored collapsed state removes the saved override so the card falls back to the template default behavior.
  - This state is stored through `choreops.manage_ui_control` using the `shared_admin` target.
