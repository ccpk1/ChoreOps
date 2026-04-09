# user-gamification-premier-v1 preferences

`user-gamification-premier-v1` is the premier full user layout. It starts with the welcome and chores flow, then expands into rewards, badges, and other gamification views.

## Quick overview

- Feature-complete chore UX: includes shared progress context, claim-mode nuance, overdue/missed context, and claim/approve/undo controls.
- Modular shared-template architecture: standard and kids chore-row logic are sourced from `templates/shared/button_card_template_chore_row_v1.yaml` and `templates/shared/button_card_template_chore_row_kids_v1.yaml`, then composed into published runtime templates.
- Portability note: copy from composed runtime templates (vendored output), not directly from shared fragment source files.
- Friendly for drag-and-drop workflows: keep defaults for a simple setup, then tune behavior with `pref_*` values.
- This document covers the supported user-tunable `pref_*` surface for the template. Internal shared-fragment contract keys are intentionally left out.
- Supports practical organization controls (time buckets, labels, sorting, and state filtering).

## Color policy note

- This template follows the dashboard theme-first color policy.
- Home Assistant theme variables remain the default source for colors.
- The accent preferences below are intentional product-specific exceptions for chore and reward state semantics and are declared as template variables for easier long-term maintenance.

## Header tint preference

- `pref_points_precision` (default: `fixed_0`)
  - Controls how point values are formatted in the welcome card.
  - `fixed_0` shows a rounded whole-number display for compact layouts.
  - `adaptive` shows whole numbers when possible, otherwise up to 2 decimals.
  - `fixed_1` always shows 1 decimal place.
  - `fixed_2` always shows 2 decimal places.
  - Allowed: `fixed_0`, `adaptive`, `fixed_1`, `fixed_2`.

- `pref_primary_tint_mix_pct` (default: `14`)
  - Controls the percent of `var(--primary-color)` mixed into the background fill when header background fill is enabled.
  - Applies to the welcome card and the section headers for Showcase, Rewards, Cumulative, Periodic, and Achievements.
  - The Chores card uses the same preference name, but its collapsed and expanded states intentionally override some header presentation details.
  - Does not affect reward rows, chore rows, group chips, or other card surfaces.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Controls whether the welcome card and the main section headers render a background fill.
  - When `false`, those surfaces use a transparent background.
  - Applies to the welcome card and the section headers for Showcase, Rewards, Cumulative, Periodic, and Achievements.
  - The Chores card uses the same preference name, but its collapsed and expanded states intentionally override some header presentation details.
  - Does not affect reward rows, chore rows, group chips, or other card surfaces.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Controls whether the thin outer border line is shown on the welcome card and the main section headers.
  - When `false`, only the thin line is removed.
  - Left and bottom accent borders on section headers remain visible.
  - Applies to the welcome card and the section headers for Showcase, Rewards, Cumulative, Periodic, and Achievements.
  - The Chores card uses the same preference name, but its collapsed and expanded states intentionally override some header presentation details.
  - Allowed: `true`, `false`.

Recommended ranges:

- `0` = no primary tint
- `10` to `18` = subtle themed tint
- `25+` = much stronger emphasis

## Card: Chores

- `pref_column_count_standard` (default: `1`)
  - Grid columns for chore cards when the effective row variant is `standard`.
  - Allowed: positive integer.

- `pref_column_count_kids` (default: `2`)
  - Grid columns for chore cards when the effective row variant is `kids`.
  - This also applies when the user switches variants through the Chores gear panel.
  - Allowed: positive integer.

- `pref_settings_column_count_mobile` (default: `3`)
  - Grid columns for Chores settings buttons on narrow screens.
  - Allowed: positive integer.

- `pref_settings_column_count_wide` (default: `3`)
  - Grid columns for Chores settings buttons on wide screens.
  - Allowed: positive integer.

- `pref_use_overdue_grouping` (default: `true`)
  - Shows a dedicated overdue group.
  - Allowed: `true`, `false`.

- `pref_today_grouping_mode` (default: `today_morning`)
  - Controls today grouping behavior.
  - `off` puts today chores into the fallback group.
  - `today` shows one Today group.
  - `today_morning` shows both Today and Morning grouping.
  - Allowed: `off`, `today`, `today_morning`.

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

- `pref_exclude_blocked` (default: `false`)
  - Hides blocked-result chores.
  - If set to `true`, `completed_by_other`, `not_my_turn`, and `missed` are automatically added to `pref_exclude_states` when missing.
  - Allowed: `true`, `false`.

- `pref_exclude_states` (default: `[]`)
  - Excludes chores by state.
  - Example: `['completed', 'completed_by_other', 'not_my_turn', 'missed']`.
  - Allowed: array of lowercase state strings.

- `pref_exclude_group_list` (default: `[]`)
  - Excludes one or more rendered chore groups from the card.
  - Allowed values: `overdue`, `today_morning`, `today`, `this_week`, `later`.
  - Exclusions apply after the dashboard resolves which groups exist.
  - If a listed group does not exist in the current configuration, it is ignored.
  - Example: `['later']` hides the Later bucket.
  - Example: `['later', 'this_week']` hides the Later and Due This Week buckets.
  - In `today_morning` mode, excluding `today` hides only the later-today bucket. Exclude both `today_morning` and `today` to hide all today chores.

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

- `pref_claim_accent` (default: `#a957fa`)
  - Accent color used for claimed and in-progress chore-state treatments.
  - Applies to shared chore-row variants that opt into the shared accent contract.

- `pref_due_accent` (default: `#ff9800`)
  - Accent color used for due-state highlights.
  - Applies to shared chore-row border, icon, and supporting state treatments.

- `pref_overdue_accent` (default: `#ff4444`)
  - Accent color used for overdue and missed-state highlights.
  - Applies to shared chore-row border, icon, and overdue action affordances.

- `pref_steal_accent` (default: `#F2C94C`)
  - Accent color used for `steal_available` treatments.
  - Applies to shared chore-row supporting text and action-affordance emphasis.

- `pref_ui_control_key_root` (default: `gamification/chores`)
  - Sets the `ui_control` branch used by this chores card inside the Gamification Premier template.
  - Override this when you want multiple chore-card instances for the same user to keep different saved settings.
  - Example custom values: `gamification/chores`, `gamification/chores_compact`, `dashboards/user_main/gamification_premier_chores`.
  - Use slash-delimited segments without relying on a leading slash.

- `pref_chore_row_variant` (default: `standard`)
  - Selects which shared chore row template the Chores card uses.
  - `standard` uses `chore_row_v1`.
  - `kids` uses `chore_row_kids_v1`.
  - Allowed: `standard`, `kids`.

- Chores header gear panel
  - When the Chores header is expanded, a gear button appears in the header.
  - The gear toggles a small configuration panel that stores per-user choices in `ui_control` under the branch defined by `pref_ui_control_key_root`.
  - Current panel controls:
    - `row_variant` to switch between `standard` and `kids`
    - `exclude_completed` to add or remove `completed` from the effective exclusion list
    - `exclude_blocked` to add or remove `completed_by_other`, `not_my_turn`, and `missed` from the effective exclusion list
    - `sort_within_groups` to cycle through all supported chore sort modes
  - These settings override the template defaults only for the current user.
  - Removing the stored key falls back to the template preferences again.

- Blocked-state exclusion behavior
  - `pref_exclude_states` remains the template-authored base exclusion list.
  - The gear-panel blocked toggle only manages whether `completed_by_other`, `not_my_turn`, and `missed` are effectively included for the current user.
  - It does not overwrite the rest of `pref_exclude_states`.

- Sort override behavior
  - The gear-panel sort control cycles through `default`, `name_asc`, `name_desc`, `date_asc`, `date_desc`, and `by_state_and_date`.
  - The selected mode is stored per user in `ui_control`.
  - When the cycle returns to the template-authored `pref_sort_within_groups`, the stored override is removed.

- `pref_default_header_collapsed` (default: `false`)
  - Sets the default Chores header state when no persisted UI override exists.
  - `false` means expanded by default.
  - `true` means collapsed by default.
  - Allowed: `true`, `false`.

- `pref_primary_tint_mix_pct` (default: `14`)
  - Sets the tint strength used by the main Chores section header when that header is collapsed.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Currently kept in place for compatibility, but the Chores header now overrides this behavior.
  - Collapsed state always shows the tinted header background.
  - Expanded state always suppresses the header background.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Currently kept in place for compatibility, but the Chores header now overrides this behavior.
  - Collapsed state always shows the thin full outer border.
  - Expanded state suppresses only that thin outer border.
  - The left and bottom accent borders remain visible in both states.
  - Allowed: `true`, `false`.

- Chores header collapse state
  - The Chores section header supports a persisted per-user collapse toggle.
  - The template uses the branch from `pref_ui_control_key_root` and stores the header state at `header_collapse` under that root.
  - Default behavior comes from `pref_default_header_collapsed` when no stored override exists.
  - Expanding again removes the stored override so the card falls back to the template default state.

- Completed exclusion behavior
  - `pref_exclude_states` remains the template-authored base exclusion list.
  - The gear-panel completed toggle only manages whether `completed` is effectively included in that exclusion list for the current user.
  - It does not overwrite the rest of `pref_exclude_states`.

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

- `pref_claim_accent` (default: `#a957fa`)
  - Accent color used for requested reward-state treatments.
  - Applies to requested reward row icon, border, background, and primary action emphasis.
  - This is a product-specific reward accent exception and should be managed through this variable rather than repeated inline literals.

- `pref_primary_tint_mix_pct` (default: `14`)
  - Sets the tint strength used by the main Rewards section header when that header is collapsed.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Currently kept in place for compatibility, but the Rewards header now overrides this behavior.
  - Collapsed state always shows the tinted header background.
  - Expanded state always suppresses the header background.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Currently kept in place for compatibility, but the Rewards header now overrides this behavior.
  - Collapsed state always shows the thin full outer border.
  - Expanded state suppresses only that thin outer border.
  - The left and bottom accent borders remain visible in both states.
  - Allowed: `true`, `false`.

- Rewards header collapse state
  - The Rewards section header supports a persisted per-user collapse toggle.
  - The template uses `ui_control_key_root = gamification/rewards` and stores the header state at `header_collapse` under that root.
  - Default behavior comes from `pref_default_header_collapsed` when no stored override exists.
  - Expanding again removes the stored override so the card falls back to the template default state.

- `pref_default_header_collapsed` (default: `false`)
  - Sets the default Rewards header state when no persisted UI override exists.
  - `false` means expanded by default.
  - `true` means collapsed by default.
  - Allowed: `true`, `false`.

## Card: Showcase

- `pref_hide_penalties` (default: `false`)
  - Hides the penalties card and allows the bonus card to span the full adjustment row.
  - Allowed: `true`, `false`.

- `pref_hide_overviews` (default: `false`)
  - Hides the rank, quest, achievement, bonus, and penalty overview sections while keeping the top showcase summary and earned badges row visible.
  - Allowed: `true`, `false`.

- `pref_primary_tint_mix_pct` (default: `14`)
  - Sets the tint strength used by the Showcase section header.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Controls whether the Showcase section header renders a background fill.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Controls whether the thin outer border line is shown on the Showcase section header.
  - Allowed: `true`, `false`.

- Showcase gear panel
  - The showcase card has a gear button in the top-right corner.
  - The gear toggles a small configuration panel that stores per-user choices in `ui_control` under `gamification/showcase`.
  - Current panel controls:
    - `hide_penalties` to hide the penalties card and let the bonus card span the full row
    - `hide_overviews` to hide ranks, quests, achievements, bonus, and penalty sections while keeping the showcase summary and all earned badges visible
  - These settings override the template defaults only for the current user.
  - Removing the stored key falls back to the template preferences again.

## Card: Cumulative badges

- `pref_show_next_higher_badge` (default: `true`)
  - Controls whether the next higher cumulative badge card is shown.
  - Allowed: `true`, `false`.

- `pref_show_next_lower_badge` (default: `true`)
  - Controls whether the next lower earned cumulative badge card is shown.
  - Allowed: `true`, `false`.

- `pref_primary_tint_mix_pct` (default: `14`)
  - Sets the tint strength used by the main Cumulative section header when that header is collapsed.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Currently kept in place for compatibility, but the Cumulative header now overrides this behavior.
  - Collapsed state always shows the tinted header background.
  - Expanded state always suppresses the header background.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Currently kept in place for compatibility, but the Cumulative header now overrides this behavior.
  - Collapsed state always shows the thin full outer border.
  - Expanded state suppresses only that thin outer border.
  - The left and bottom accent borders remain visible in both states.
  - Allowed: `true`, `false`.

- `pref_default_header_collapsed` (default: `false`)
  - Sets the default Cumulative header state when no persisted UI override exists.
  - `false` means expanded by default.
  - `true` means collapsed by default.
  - Allowed: `true`, `false`.

- Cumulative header collapse state
  - The Cumulative section header supports a persisted per-user collapse toggle.
  - The template uses `ui_control_key_root = gamification/cumulative` and stores the header state at `header_collapse` under that root.
  - Default behavior comes from `pref_default_header_collapsed` when no stored override exists.
  - Expanding again removes the stored override so the card falls back to the template default state.

- Cumulative header gear panel
  - When the Cumulative header is expanded, a gear button appears in the header.
  - The gear toggles a small configuration panel that stores per-user choices in `ui_control` under `gamification/cumulative`.
  - Current panel controls:
    - `show_next_higher_badge` to show or hide the next higher badge card
    - `show_next_lower_badge` to show or hide the next lower earned badge card
  - These settings override the template defaults only for the current user.
  - Removing the stored key falls back to the template preferences again.

## Card: Periodic badges

- `pref_primary_tint_mix_pct` (default: `14`)
  - Sets the tint strength used by the main Periodic section header when that header is collapsed.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Currently kept in place for compatibility, but the Periodic header now overrides this behavior.
  - Collapsed state always shows the tinted header background.
  - Expanded state always suppresses the header background.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Currently kept in place for compatibility, but the Periodic header now overrides this behavior.
  - Collapsed state always shows the thin full outer border.
  - Expanded state suppresses only that thin outer border.
  - The left and bottom accent borders remain visible in both states.
  - Allowed: `true`, `false`.

- `pref_default_header_collapsed` (default: `false`)
  - Sets the default Periodic header state when no persisted UI override exists.
  - `false` means expanded by default.
  - `true` means collapsed by default.
  - Allowed: `true`, `false`.

- Periodic header collapse state
  - The Periodic section header supports a persisted per-user collapse toggle.
  - The template uses `ui_control_key_root = gamification/periodic` and stores the header state at `header_collapse` under that root.
  - Default behavior comes from `pref_default_header_collapsed` when no stored override exists.
  - Expanding again removes the stored override so the card falls back to the template default state.

## Card: Achievements

- `pref_primary_tint_mix_pct` (default: `14`)
  - Sets the tint strength used by the main Achievements section header when that header is collapsed.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Currently kept in place for compatibility, but the Achievements header now overrides this behavior.
  - Collapsed state always shows the tinted header background.
  - Expanded state always suppresses the header background.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Currently kept in place for compatibility, but the Achievements header now overrides this behavior.
  - Collapsed state always shows the thin full outer border.
  - Expanded state suppresses only that thin outer border.
  - The left and bottom accent borders remain visible in both states.
  - Allowed: `true`, `false`.

- `pref_default_header_collapsed` (default: `false`)
  - Sets the default Achievements header state when no persisted UI override exists.
  - `false` means expanded by default.
  - `true` means collapsed by default.
  - Allowed: `true`, `false`.

- Achievements header collapse state
  - The Achievements section header supports a persisted per-user collapse toggle.
  - The template uses `ui_control_key_root = gamification/achievements` and stores the header state at `header_collapse` under that root.
  - Default behavior comes from `pref_default_header_collapsed` when no stored override exists.
  - Expanding again removes the stored override so the card falls back to the template default state.

## Practical tuning examples

- Keep it minimal: set only `pref_column_count`, leave everything else as default.
- Hide done chores: add `completed` to `pref_exclude_states` (for example `['completed']`).
- Build a label board: set `pref_use_label_grouping: true` and define `pref_label_display_order`.
- Prioritize urgent work: keep `pref_use_overdue_grouping: true` and use `pref_sort_within_groups: by_state_and_date`.
- Sort rewards by price: set `pref_sort_rewards: cost_asc`.
- Group rewards by labels: set `pref_use_label_grouping: true` and optionally define `pref_label_display_order`.
- Reduce header tint: set `pref_primary_tint_mix_pct: 8`.
- Remove welcome/header fill entirely: set `pref_show_header_background: false`.
- Keep accent borders but remove the thin line: set `pref_show_header_thin_border: false`.
