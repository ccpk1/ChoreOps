# user-chores-standard-v1 preferences

`user-chores-standard-v1` is the default chore-focused layout. It keeps the welcome summary from Chores Essential and brings over the richer production chore-row behavior.

## Quick overview

- Feature-complete chore UX: includes shared progress context, claim-mode nuance, overdue/missed context, and claim/approve/undo controls.
- Modular shared-template architecture: standard and kids chore-row logic are sourced from `templates/shared/button_card_template_chore_row_v1.yaml` and `templates/shared/button_card_template_chore_row_kids_v1.yaml`, then composed into published runtime templates.
- Portability note: copy from composed runtime templates (vendored output), not directly from shared fragment source files.
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

- `pref_chore_row_variant` (default: `standard`)
  - Selects which shared chore row template the Chores card uses.
  - `standard` uses `chore_row_v1`.
  - `kids` uses `chore_row_kids_v1`.
  - Allowed: `standard`, `kids`.

- `pref_chore_engine_layout_mode` (default: `responsive`)
  - Controls whether column counts adapt to screen width.
  - `single` uses one set of column preferences for all widths.
  - `responsive` uses separate mobile and wide column preferences.
  - Allowed: `single`, `responsive`.

- `pref_column_count_mobile_standard` (default: `1`)
  - Grid columns for chore cards on mobile-width screens when using the `standard` row variant.
  - Allowed: positive integer.

- `pref_column_count_mobile_kids` (default: `2`)
  - Grid columns for chore cards on mobile-width screens when using the `kids` row variant.
  - Allowed: positive integer.

- `pref_column_count_wide_standard` (default: `3`)
  - Grid columns for chore cards on wide screens when using the `standard` row variant.
  - Allowed: positive integer.

- `pref_column_count_wide_kids` (default: `5`)
  - Grid columns for chore cards on wide screens when using the `kids` row variant.
  - Allowed: positive integer.

- `pref_settings_column_count_mobile` (default: `3`)
  - Grid columns for Chores settings buttons on narrow screens.
  - Allowed: positive integer.

- `pref_settings_column_count_wide` (default: `8`)
  - Grid columns for Chores settings buttons on wide screens.
  - Allowed: positive integer.

### Time Buckets

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

### Exclude Filters

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
  - In `today_morning` mode, excluding `today` hides only the later-today bucket. Exclude both `today_morning` and `today` to hide all today chores.

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

- Completed exclusion behavior
  - `pref_exclude_states` remains the template-authored base exclusion list.
  - The gear-panel completed toggle only manages whether `completed` is effectively included in that exclusion list for the current user.
  - It does not overwrite the rest of `pref_exclude_states`.

- Blocked-state exclusion behavior
  - `pref_exclude_states` remains the template-authored base exclusion list.
  - The gear-panel blocked toggle only manages whether `completed_by_other`, `not_my_turn`, and `missed` are effectively included for the current user.
  - It does not overwrite the rest of `pref_exclude_states`.

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

- Sort override behavior
  - The gear-panel sort control cycles through `default`, `name_asc`, `name_desc`, `date_asc`, `date_desc`, and `by_state_and_date`.
  - The selected mode is stored per user in `ui_control`.
  - When the cycle returns to the template-authored `pref_sort_within_groups`, the stored override is removed.

### Display

- `pref_show_chore_description` (default: `false`)
  - Shows the optional description row when a chore has non-empty description text.
  - When `false`, the description row is always hidden.
  - The kids row variant keeps the simplified tile layout and may ignore description content even when enabled.
  - Allowed: `true`, `false`.

- `pref_claim_accent` (default: `#a957fa`)
  - Accent color used for claimed and in-progress chore-state treatments.
  - Applies to shared chore-row variants that opt into the shared accent contract.
### Colors & Accents

- `pref_claim_accent` (default: `#a957fa`)
  - Accent color used for claimed and in-progress chore-state treatments.
  - Applies to shared chore-row variants that opt into the shared accent contract.
  - Intended as a product-specific accent exception rather than a general theme replacement.

- `pref_due_accent` (default: `#ff9800`)
  - Accent color used for due-state highlights.
  - Applies to shared chore-row border, icon, and supporting state treatments.

- `pref_overdue_accent` (default: `#ff4444`)
  - Accent color used for overdue and missed-state highlights.
  - Applies to shared chore-row border, icon, and overdue action affordances.

- `pref_steal_accent` (default: `#F2C94C`)
  - Accent color used for `steal_available` treatments.
  - Applies to shared chore-row supporting text and action-affordance emphasis.

- `pref_standby_accent` (default: `#5B8DEF`)
  - Accent color used for `standby_available` (actionable standby) treatments.
  - Muted blue — noticeable but subdued, distinct from urgency signaling.
  - Applies to shared chore-row card background tint, due-text color, and action-affordance emphasis.

### Header & UI Control

- `pref_ui_control_key_root` (default: `chores`)
  - Sets the `ui_control` branch used by this chores card.
  - Override this when you want multiple chore-card instances for the same user to keep different saved settings.
  - Example custom values: `chores`, `chores_compact`, `dashboards/user_main/chores`.
  - Use slash-delimited segments without relying on a leading slash.

- `pref_default_header_collapsed` (default: `false`)
  - Sets the default Chores header state when no persisted UI override exists.
  - `false` means expanded by default.
  - `true` means collapsed by default.

- `pref_primary_tint_mix_pct` (default: `14`)
  - Controls the percent of `var(--primary-color)` mixed into the collapsed Chores header background.
  - Allowed: integer from `0` to `100`.

- `pref_show_header_background` (default: `true`)
  - Controls whether the collapsed Chores header renders a background fill.
  - Allowed: `true`, `false`.

- `pref_show_header_thin_border` (default: `true`)
  - Controls whether the thin outer border line is shown on the collapsed Chores header.
  - Allowed: `true`, `false`.

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

- Chores header collapse state
  - The Chores section header supports a persisted per-user collapse toggle.
  - The template uses the branch from `pref_ui_control_key_root` and stores the header state at `header_collapse` under that root.
  - Default behavior comes from `pref_default_header_collapsed` when no stored override exists.
  - Expanding again removes the stored override so the card falls back to the template default state.

## Practical tuning examples

- Keep it minimal: set only the variant-specific column preferences you care about, leave everything else as default.
- Switch to the kid-friendly tile presentation: set `pref_chore_row_variant: kids` and keep the auto-selected column defaults unless you want a denser or sparser grid.
- Hide done chores: add `completed` to `pref_exclude_states` (for example `['completed']`).
- Hide unscheduled one-off chores: set `pref_exclude_nonrecurring_no_due_date: true`.
- Hide long-range future chores: set `pref_max_due_date_days: 7`.
- Hide the Later group: add `later` to `pref_exclude_group_list` (for example `['later']`).
- Build a due-focused card: add `later` and `this_week` to `pref_exclude_group_list`.
- Build a label board: set `pref_use_label_grouping: true` and define `pref_label_display_order`.
- Build a kitchen-only card: set `pref_include_label_list: ['kitchen']` — only chores with the kitchen label appear.
- Build a card for today only (performance-focused): set `pref_include_group_list: ['today']` — skips all non-today chores early in the loop.
- Build a pending-approval card: set `pref_include_state_list: ['claimed', 'completed']` — only chores needing action.
- Combine include filters: `pref_include_group_list: ['today', 'this_week']` + `pref_include_label_list: ['kitchen', 'bathroom']` — only today/this-week chores with those labels.
- Prioritize urgent work: keep `pref_use_overdue_grouping: true` and use `pref_sort_within_groups: by_state_and_date`.
