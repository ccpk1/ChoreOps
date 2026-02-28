# Dashboard Template Guide

**Version**: 0.5.0-beta.5 | **Last Updated**: 2026-02-27

This guide documents the rules and patterns for creating, modifying, and managing ChoreOps dashboard templates.

## Authority and source-of-truth model

Use this guide as the canonical architecture and runtime contract reference for dashboard template authoring.

Repository ownership boundaries:

- Canonical authoring source: `ccpk1/ChoreOps-Dashboards`
- Vendored runtime mirror in integration: `custom_components/choreops/dashboards`

Contribution rules:

- Submit template, registry, preference, and translation source PRs in `ccpk1/ChoreOps-Dashboards`.
- Do not submit manual source PRs against `custom_components/choreops/dashboards` in `ccpk1/ChoreOps`.
- Mirror canonical updates via `utils/sync_dashboard_assets.py`.

Decision/ratification references:

- `docs/in-process/DASHBOARD_REGISTRY_GENERATION_IN-PROCESS.md`
- `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`

---

## Architecture Overview

### Multi-View Dashboard Model

ChoreOps generates a **single dashboard** with **multiple views (tabs)**:

```
kcd-chores (Dashboard)
├── User1 (View/Tab)        ← user template rendered with user context
├── User2 (View/Tab)        ← user template rendered with user context
├── Admin (Shared, optional)← path: admin
└── Admin-<user> (optional) ← path: admin-<user-slug>
```

**Key Points**:

- One dashboard per installation (user names it, e.g., "Chores")
- URL path: `kcd-{slugified-name}` (e.g., `kcd-chores`)
- Each user gets their own view/tab
- Optional admin views based on admin layout mode (`none`, `global`, `per user`, `both`)
- Style variants are selected by `template_id` from the registry manifest

### Admin layout modes

- `none`: no admin views
- `global`: one shared admin view (`path: admin`)
- `per user`: one admin view per selected user (`path: admin-<user-slug>`)
- `both`: includes shared plus per-user admin views

### Legacy runtime key compatibility note

The dashboard system uses user-facing terminology in docs and UX, but some runtime constants/keys remain legacy for compatibility:

- Internal enum value: `per_assignee` (user-facing label: Per User)
  When authoring templates, prefer user semantics in variable names and comments.

### Canonical and vendored asset workflow

Dashboard assets use a single-source-of-truth model:

- Canonical authoring repo: `choreops-dashboards`
- Vendored runtime mirror: `custom_components/choreops/dashboards`

When you update templates, translations, preferences, or dashboard `dashboard_registry.json`:

1. Edit canonical files in `choreops-dashboards`.
2. From `choreops`, run:

```bash
python utils/sync_dashboard_assets.py
```

3. Verify drift-free parity:

```bash
python utils/sync_dashboard_assets.py --check
```

4. Commit canonical changes and vendored mirror updates together.

CI enforces this contract with the `Dashboard Asset Parity` workflow, which fails
if vendored assets drift from canonical content.

---

## Release, registry, and compatibility policy

Dashboard selection is contract-first and registry-driven.

### Source of truth order

1. Canonical manifest in `ccpk1/ChoreOps-Dashboards/dashboard_registry.json`
2. Vendored runtime manifest in `custom_components/choreops/dashboards/dashboard_registry.json`
3. Runtime merge policy: local baseline + valid remote override by `template_id`

### Compatibility source and rules

Compatibility is defined per template record in `dashboard_registry.json` via manifest fields, not by legacy integration fallback maps.

Primary fields:

- `template_id`
- `lifecycle_state`
- `min_integration_version`
- optional `max_integration_version`
- `dependencies.required[]` and `dependencies.recommended[]`

A template is selectable only when:

- manifest record is valid for supported `schema_version`
- `lifecycle_state` is selectable for runtime policy
- integration version satisfies manifest compatibility range
- required dependencies are present

### Release naming conventions

The dashboard registry repository uses SemVer-style release channels:

- Stable: `X.Y.Z`
- Beta: `X.Y.Z-beta.N`
- RC: `X.Y.Z-rc.N`

### Recovery safety net

If remote release/manifest lookup fails or returns invalid records, runtime behavior remains deterministic and falls back to vendored local registry/template assets.

### Generator release execution contract (runtime)

The dashboard generator enforces a deterministic release contract:

1. Step 1 resolves selected release behavior to one concrete `effective_release_ref`.
2. Step 1 prepares release assets (registry, templates, translations, preferences).
3. Prepared assets are applied to local vendored runtime files and become the
  baseline for generation/runtime lookups.
4. Step 3 generation consumes the prepared release context rather than re-resolving
  release selection.

Selection mode rules:

- Explicit tag selected: strict-pin behavior (no silent downgrade)
- Latest stable/latest compatible: resolve once in Step 1 and pin that ref
- Current installed: execute against local `release_version`

### Dependency review UX contract (Step 4)

Dependency review always renders two translated section headers:

- Missing required dependencies
- Missing recommended dependencies

Missing dependency items are shown as link rows prefixed with `❌`.
Required dependency bypass remains an explicit acknowledge action.

---

## Template File Structure

### Canonical and vendored locations

```
choreops-dashboards/templates/
├── user-gamification-v1.yaml
├── user-minimal-v1.yaml
├── admin-shared-v1.yaml
└── admin-peruser-v1.yaml

custom_components/choreops/dashboards/templates/
├── user-gamification-v1.yaml
├── user-minimal-v1.yaml
├── admin-shared-v1.yaml
└── admin-peruser-v1.yaml
```

### Output Format (CRITICAL)

**All templates must output a SINGLE VIEW object, not a full dashboard.**

```yaml
# ✅ CORRECT - Single view (list item)
- max_columns: 4
  title: << user.name >> Chores
  path: << user.slug >>
  sections:
    - type: grid
      cards: [...]

# ❌ WRONG - Full dashboard with views wrapper
views:
  - max_columns: 4
    title: << user.name >> Chores
    ...
```

The builder combines multiple single-view outputs into `{"views": [...]}`.

---

## Jinja2 Delimiter System (Dual-Layer)

Templates use **two different Jinja2 syntaxes** for different purposes:

### Build-Time (Python Jinja2) - `<< >>`

Processed by the integration when generating the dashboard.

| Delimiter   | Purpose             | Example                              |
| ----------- | ------------------- | ------------------------------------ |
| `<< >>`     | Variable injection  | `<< user.name >>`, `<< user.slug >>` |
| `<% %>`     | Block statements    | `<% if condition %>...<%endif%>`     |
| `<#-- --#>` | Comments (stripped) | `<#-- This is removed --#>`          |

**Available Context Variables** (user templates):

```python
{
    "user": {
      "name": "Alice",               # Display name from storage
      "slug": "alice",               # URL-safe slugified name
      "user_id": "<uuid-string>"     # Stable identity for lookup scoping
    },
    "integration": {
      "entry_id": "<config-entry-id>" # Required for multi-instance lookup scoping
    }
}
```

Admin templates can be shared-selector or per-user-tab models, but all helper lookup logic must still use identity-scoped contracts (`integration.entry_id` + `user.user_id`).

### Runtime (Home Assistant Jinja2) - `{{ }}`

Preserved in output, evaluated by HA when rendering the dashboard.

| Delimiter | Purpose                     | Example                                      |
| --------- | --------------------------- | -------------------------------------------- |
| `{{ }}`   | HA state/attribute access   | `{{ states('sensor.kc_alice_points') }}`     |
| `{%- -%}` | HA template logic (trimmed) | `{%- for item in items -%}...{%- endfor -%}` |
| `{# #}`   | HA template comments        | `{# This stays in output #}`                 |

Use whitespace-trimmed HA Jinja tags by default in templates:

- Prefer `{%- ... -%}` for control flow and `{%- set ... -%}` assignments.
- Use plain `{% ... %}` only when intentional spacing/newlines are required in rendered output.
- Keep `{{ ... }}` for expression output unless you specifically need trim behavior (`{{- ... -}}`).

### Example: Both Syntaxes Together

```yaml
- type: custom:mushroom-template-card
  primary: << user.name >>'s Points
  secondary: >-
    {{ states('sensor.kc_<< user.slug >>_points') | int }} points
```

**After build-time render** (for user "Alice"):

```yaml
- type: custom:mushroom-template-card
  primary: Alice's Points
  secondary: >-
    {{ states('sensor.kc_alice_points') | int }} points
```

---

## Comment Syntax Rules

### Build-Time Comments (Stripped)

```yaml
<#-- This comment is removed during template processing --#>
```

**Rules**:

1. Must have `<#--` opening and `--#>` closing on same logical block
2. Can span multiple lines BUT each line should be self-contained
3. Malformed comments cause YAML parse errors

**✅ Correct multi-line**:

```yaml
<#-- ============================================= --#>
<#-- ChoreOps Dashboard Template - FULL Style     --#>
<#-- Template Schema Version: 1                   --#>
<#-- ============================================= --#>
```

**❌ Wrong - missing closer**:

```yaml
<#-- This comment has no closing
<#-- This line starts new comment --#>
```

**❌ Wrong - double closer**:

```yaml
<#-- Comment text --#> --#>
```

### Runtime Comments (Preserved)

```yaml
{#-- This comment stays in the rendered output --#}
```

Use for HA template debugging or documentation visible in Lovelace editor.

---

## Template Header Standard

Every template MUST start with this header block:

```yaml
<#-- ============================================= --#>
<#-- ChoreOps Dashboard Template - [STYLE] Style --#>
<#-- Template Schema Version: 1                    --#>
<#-- Integration: 0.5.0-beta.5 (Schema 43)         --#>
<#-- ============================================= --#>
<#--                                               --#>
<#-- [Brief description of this template]          --#>
<#-- OUTPUT: Single view object (combined by builder) --#>
<#--                                               --#>
<#-- Injection variables (Python Jinja2 << >>):    --#>
<#--   << user.name >> - User display name           --#>
<#--   << user.slug >> - URL-safe slug for path      --#>
<#--   << user.user_id >> - User identity UUID       --#>
<#--   << integration.entry_id >> - Instance scope ID --#>
<#--                                               --#>
<#-- All HA Jinja2 {{ }} syntax is preserved as-is --#>
<#-- ============================================= --#>

- max_columns: 4
  title: ...
```

For admin templates, omit the injection variables section and note "No injection needed".

---

## Entity lookup contract (required)

When referencing ChoreOps helper and related sensors in templates, use dynamic, instance-aware lookup patterns. Never hardcode entity IDs.

```jinja
{#-- 1. User and instance context --#}
{%- set name = '<< user.name >>' -%}
{%- set user_id = '<< user.user_id >>' -%}
{%- set entry_id = '<< integration.entry_id >>' -%}
{%- set lookup_key = entry_id ~ ':' ~ user_id -%}


{#-- 2. Resolve dashboard helper dynamically --#}
{%- set dashboard_helper = integration_entities('choreops')
    | select('search', '^sensor\\.')
    | list
    | expand
    | selectattr('attributes.purpose', 'defined')
    | selectattr('attributes.purpose', 'eq', 'purpose_dashboard_helper')
    | selectattr('attributes.dashboard_lookup_key', 'eq', lookup_key)
    | map(attribute='entity_id')
    | first
    | default('err-dashboard_helper_missing', true) -%}


{#-- 3. Guard validation and graceful fallback --#}
{%- if states(dashboard_helper) in ['unknown', 'unavailable'] -%}
  {{ {'type': 'markdown', 'content': '⚠️ Dashboard configuration error'} }},
  {%- set skip_render = true -%}
{%- else -%}
  {%- set skip_render = false -%}
{%- endif -%}


{#-- 4. Normal rendering only when valid --#}
{%- if not skip_render -%}
  {{ {'type': 'markdown', 'content': '...normal content...'} }},
{%- endif -%}
```

### Graceful error-handling requirements

- Validate required entities before normal rendering (dashboard helper, translation sensor, and required core sensors)
- If validation fails, render actionable fallback guidance and set a guard flag (for example `skip_render = true`)
- Skip normal card rendering when guard validation fails
- Never hard-fail template rendering due to missing required entities

---

## Validation Checklist

Before committing template changes:

### 1. Comment Syntax Check

```bash
# Look for unclosed or malformed comments
grep -n "<#--" templates/*.yaml | grep -v "\-\-#>"
```

### 2. Template Render Test

```bash
cd /workspaces/choreops && python3 << 'EOF'
import jinja2
import yaml
from pathlib import Path

template_path = Path("custom_components/choreops/dashboards/templates/user-gamification-v1.yaml")
template_str = template_path.read_text()

env = jinja2.Environment(
    variable_start_string="<<",
    variable_end_string=">>",
    block_start_string="<%",
    block_end_string="%>",
    comment_start_string="<#--",
    comment_end_string="--#>",
    autoescape=False,
)

context = {
  "user": {"name": "Test User", "slug": "test-user", "user_id": "test-user-id"},
  "integration": {"entry_id": "test-entry-id"},
}
template = env.from_string(template_str)
rendered = template.render(**context)

config = yaml.safe_load(rendered)
if isinstance(config, list) and len(config) > 0:
    print(f"✅ Valid: Parsed as list, first item keys: {list(config[0].keys())[:5]}")
else:
    print(f"❌ Invalid: Expected list, got {type(config)}")
EOF
```

### 3. View Structure Check

Ensure output has required keys:

- `title` - View tab title
- `path` - URL path segment (unique per view)
- `sections` or `cards` - Content

---

## v0.5.0 Chore Attributes Reference

### Dashboard helper chore fields

The dashboard helper resolved via `dashboard_lookup_key = <integration.entry_id>:<user.user_id>` provides enriched chore data with these attributes:

#### Core Chore Fields (v0.4.x)

| Field      | Type   | Description                            | Example                   |
| ---------- | ------ | -------------------------------------- | ------------------------- |
| `eid`      | string | Entity ID of the chore status sensor   | `sensor.kc_alice_chore_1` |
| `name`     | string | Human-readable chore name              | `"Wash Dishes"`           |
| `state`    | string | Current chore state                    | `"pending"`, `"claimed"`  |
| `labels`   | list   | Categorization tags                    | `["kitchen", "daily"]`    |
| `grouping` | string | UI grouping hint                       | `"morning"`, `"evening"`  |
| `is_am_pm` | bool   | Whether chore uses 12-hour time format | `true`, `false`           |

#### New v0.5.0 rotation and restriction fields

Note: Some runtime payload keys still use legacy names for backward compatibility. In this guide, treat those fields as user-scoped semantics.

| Field            | Type         | Description                                                | Example                                  |
| ---------------- | ------------ | ---------------------------------------------------------- | ---------------------------------------- |
| `lock_reason`    | string\|null | Why chore is locked (null = not locked)                    | `"waiting"`, `"not_my_turn"`, `"missed"` |
| `turn_user_name` | string\|null | Current turn holder user name                              | `"Bob"`, `null`                          |
| `available_at`   | string\|null | ISO timestamp when chore becomes available (waiting state) | `"2026-02-10T17:30:00Z"`, `null`         |

### Jinja2 Template Examples

#### Rotation Status Display

```yaml
- type: custom:mushroom-template-card
  primary: |
    {%- set chore = chores_list[0] -%}
    {%- set turn_user_name = chore.turn_user_name -%}
    {{ chore.name }}
    {%- if turn_user_name -%}
    {%- if turn_user_name == name -%}
    🎯 (Your Turn)
    {%- else -%}
    ⏳ ({{ turn_user_name }}'s Turn)
    {%- endif -%}
    {%- endif -%}
  secondary: |
    {%- set chore = chores_list[0] -%}
    {%- set turn_user_name = chore.turn_user_name -%}
    {%- if chore.lock_reason == "not_my_turn" -%}
    Wait for {{ turn_user_name }} to complete their turn
    {%- elif chore.lock_reason == "missed" -%}
    ⛔ Missed - wait for next reset
    {%- elif chore.available_at -%}
    ⏰ Available {{ chore.available_at | as_timestamp | timestamp_custom('%H:%M') }}
    {%- else -%}
    {{ chore.state | title }}
    {%- endif -%}
```

#### Availability Countdown

```yaml
- type: custom:mushroom-template-card
  primary: Due Window Status
  secondary: |
    {%- set chore = chores_list[0] -%}
    {%- if chore.lock_reason == "waiting" and chore.available_at -%}
    {%- set available_time = chore.available_at | as_timestamp -%}
    {%- set now_time = now().timestamp() -%}
    {%- if available_time > now_time -%}
    🔒 Available in {{ ((available_time - now_time) / 60) | round(0) }}m
    {%- else -%}
    ✅ Now available!
    {%- endif -%}
    {%- else -%}
    Ready to claim
    {%- endif -%}
```

#### Lock Reason Icon Mapping

```yaml
icon: |
  {%- set chore = chores_list[0] -%}
  {%- if chore.lock_reason == "waiting" -%}
  mdi:clock-outline
  {%- elif chore.lock_reason == "not_my_turn" -%}
  mdi:account-clock
  {%- elif chore.lock_reason == "missed" -%}
  mdi:calendar-remove
  {%- elif chore.state == "claimed" -%}
  mdi:hand-wave
  {%- elif chore.state == "approved" -%}
  mdi:check-circle
  {%- else -%}
  mdi:clipboard-list
  {%- endif -%}
icon_color: |
  {%- set chore = chores_list[0] -%}
  {%- if chore.lock_reason in ["waiting", "not_my_turn", "missed"] -%}
  red
  {%- elif chore.state == "claimed" -%}
  orange
  {%- elif chore.state == "approved" -%}
  green
  {%- else -%}
  blue
  {%- endif -%}
```

#### Multi-Chore Rotation Summary

```yaml
- type: custom:auto-entities
  card:
    type: entities
  filter:
    include:
      - entity_id: "{{ dashboard_helper }}"
        options:
          type: custom:mushroom-template-card
          primary: |
            {%- for chore in state_attr(config.entity, 'chores') -%}
            {%- set turn_user_name = chore.turn_user_name -%}
            {%- if turn_user_name -%}
            {{ chore.name }}:
            {%- if turn_user_name == '<< user.name >>' -%}
            🎯 Your turn
            {%- else -%}
            {{ turn_user_name }}'s turn
            {%- endif -%}
            {%- if not loop.last %} • {% endif -%}
            {%- endif -%}
            {%- endfor -%}
```

---

## Adding a new template variant

1. **Create template file** in `choreops-dashboards/templates/` using immutable `template_id` naming (`<audience>-<intent>-v<major>.yaml`).
2. **Add/update registry entry** in `choreops-dashboards/dashboard_registry.json`.
3. **Add/update preference doc** in `choreops-dashboards/preferences/` and link it via `preferences.doc_asset_path`.
4. **Add translation keys when required** in `choreops-dashboards/translations/en_dashboard.json`.
5. **Run sync from integration repo**: `python utils/sync_dashboard_assets.py`.
6. **Verify parity**: `python utils/sync_dashboard_assets.py --check`.

---

## Fetching Priority

Templates are fetched in this order:

1. **Selected compatible release tag** (or newest compatible when not explicitly selected)
2. **Fallback compatible release** (when selected release is unavailable)
3. **Local bundled template**: `custom_components/choreops/dashboards/templates/<template_id>.yaml`

Release-based fetch keeps template selection deterministic; local fallback preserves offline/recovery safety.

---

## Common Pitfalls

| Issue                                 | Cause                           | Solution                                             |
| ------------------------------------- | ------------------------------- | ---------------------------------------------------- |
| `mapping values are not allowed here` | Malformed comment block         | Check all `<#-- --#>` pairs                          |
| `Template did not produce valid view` | Output has `views:` wrapper     | Remove wrapper, start with `- max_columns:`          |
| Entity IDs not working                | Hardcoded/manual entity IDs     | Use dynamic helper lookup via `dashboard_lookup_key` |
| HA Jinja2 stripped                    | Used `<< >>` instead of `{{ }}` | Use `{{ }}` for runtime evaluation                   |
| Build variables not replaced          | Used `{{ }}` instead of `<< >>` | Use `<< >>` for build-time injection                 |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│ BUILD-TIME (Python)          RUNTIME (Home Assistant)   │
├─────────────────────────────────────────────────────────┤
│ << variable >>               {{ states('sensor.x') }}   │
│ <% if cond %>...<% endif %>  {%- if cond -%}...{%- endif -%}│
│ <#-- stripped comment --#>   {# preserved comment #}    │
├─────────────────────────────────────────────────────────┤
│ Context: user + integration  Context: Full HA state     │
│ When: Dashboard generation   When: Dashboard render     │
└─────────────────────────────────────────────────────────┘
```

## Chore State General UX Design

### 1. Core Chore States

These represent the standard lifecycle of an actionable chore.

| State        | Display Label | Standard Hex          | Lovelace CSS Variable       | Icon                | UI Behavior                                                  |
| ------------ | ------------- | --------------------- | --------------------------- | ------------------- | ------------------------------------------------------------ |
| **pending**  | Pending       | `#4A4A4A (Dark Grey)` | `var(--primary-text-color)` | `mdi:arrow-right`   | Neutral text. Standard interactive button.                   |
| **due**      | Due           | `#FF9800 (Orange)`    | `var(--warning-color)`      | `mdi:arrow-right`   | Border and text highlight to grab attention.                 |
| **caimed**   | Claimed       | `#9C27B0 (Purple)`    | `var(--primary-color)` \*   | `mdi:check-all`     | Button fills solid. Undo action becomes available.           |
| **approved** | Approved      | `#4CAF50 (Green)`     | `var(--success-color)`      | `mdi:check`         | Success highlight. Card flattens and action button disables. |
| **overdue**  | Overdue       | `#F44336 (Red)`       | `var(--error-color)`        | `mdi:alert-octagon` | High-alert red border and icons. Prominent display.          |

\*_ Note: Home Assistant's default `var(--primary-color)` is blue. To maintain the purple aesthetic from the original setup, define a custom variable like `var(--choreops-claimed-color): #9C27B0` in your global theme._

### 2. Blocked / Exception States

These represent states where the assignee cannot take action. The UI standardizes these by dropping card opacity to `0.6`, flattening drop-shadows, and disabling the primary action button.

| State                  | Display Label      | Standard Hex            | Lovelace CSS Variable        | Icon                        | UI Behavior / Meaning                                       |
| ---------------------- | ------------------ | ----------------------- | ---------------------------- | --------------------------- | ----------------------------------------------------------- |
| **waiting**            | Waiting            | `#9E9E9E (Medium Grey)` | `var(--disabled-text-color)` | `mdi:clock-outline`         | Blocked by a dependency (e.g., sibling must finish first).  |
| **missed**             | Missed             | `#F44336 (Red)`         | `var(--error-color)`         | `mdi:lock-outline`          | Window closed. Retains red alert color, but becomes locked. |
| **completed_by_other** | Completed by Other | `#9E9E9E (Medium Grey)` | `var(--disabled-text-color)` | `mdi:account-check-outline` | A shared chore claimed and finished by a sibling.           |
| **not_my_turn**        | Not My Turn        | `#9E9E9E (Medium Grey)` | `var(--disabled-text-color)` | `mdi:lock-outline`          | Rotating chore currently assigned to someone else.          |

### 3. UI Modifiers & Badges

These are appended inline to chore names or meta-text to provide immediate context without requiring the user to open a detail view.

| Modifier Type      | Description                     | Standard Hex            | Lovelace CSS Variable        | Icon                                     | Location                    |
| ------------------ | ------------------------------- | ----------------------- | ---------------------------- | ---------------------------------------- | --------------------------- |
| **Shared (All)**   | All assignees must complete     | `#9E9E9E (Medium Grey)` | `var(--disabled-text-color)` | `mdi:account-group`                      | Appended to Name            |
| **Shared (First)** | First assignee to claim wins    | `#9E9E9E (Medium Grey)` | `var(--disabled-text-color)` | `mdi:flag-checkered`                     | Appended to Name            |
| **Rotating**       | Assignment shifts on a schedule | `#9E9E9E (Medium Grey)` | `var(--disabled-text-color)` | `mdi:account-sync`                       | Appended to Name            |
| **Recurring**      | Chore repeats automatically     | `#9E9E9E (Medium Grey)` | `var(--disabled-text-color)` | `mdi:repeat`                             | Prepended to Frequency Text |
| **Bonus**          | Admin-awarded positive points   | `#4CAF50 (Green)`       | `var(--success-color)`       | `mdi:star-plus` / `mdi:gift`             | Admin Action Grids          |
| **Penalty**        | Admin-awarded negative points   | `#F44336 (Red)`         | `var(--error-color)`         | `mdi:alert-circle` / `mdi:alert-octagon` | Admin Action Grids          |

---
