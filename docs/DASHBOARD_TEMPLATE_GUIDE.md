# Dashboard Template Guide

**Version**: v0.5.0-beta4 | **Last Updated**: 2026-02-15

This guide documents the rules and patterns for creating, modifying, and managing ChoreOps dashboard templates.

---

## Architecture Overview

### Multi-View Dashboard Model

ChoreOps generates a **single dashboard** with **multiple views (tabs)**:

```
kcd-chores (Dashboard)
├── Assignee1 (View/Tab)    ← assignee template rendered with assignee context
├── Assignee2 (View/Tab)    ← assignee template rendered with assignee context
├── Admin (Shared, optional)← path: admin
└── Admin-<assignee> (optional)  ← path: admin-<assignee-slug>
```

**Key Points**:

- One dashboard per installation (user names it, e.g., "Chores")
- URL path: `kcd-{slugified-name}` (e.g., `kcd-chores`)
- Each assignee gets their own view/tab
- Optional admin views based on admin layout mode (`none`, `global`, `per_kid`, `both`)
- Style (full/minimal/compact) applies to all assignee views

### Admin layout modes

- `none`: no admin views
- `global`: one shared admin view (`path: admin`)
- `per_kid`: one admin view per selected assignee (`path: admin-<assignee-slug>`)
- `both`: includes shared plus per-assignee admin views

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

## Release compatibility policy (Phase 1)

Dashboard template release selection uses a strict compatibility gate to prevent
installing incompatible dashboard templates for a given integration version.

### Source of truth order

1. **Dashboard release metadata manifest** (future target in dashboard repo)
2. **Integration-side fallback map** in [custom_components/choreops/const.py](../custom_components/choreops/const.py):

- `DASHBOARD_RELEASE_MIN_INTEGRATION_BY_TAG`
- `DASHBOARD_RELEASE_MIN_COMPAT_TAG`

### Compatibility evaluation

A dashboard release is selectable only if:

- release tag matches supported parser contract (see accepted formats below)
- release is not below minimum compatibility floor
- installed integration version satisfies release minimum requirement

### Accepted release tag formats (current)

The integration now accepts these release tag patterns:

- `KCD_vX.Y.Z`
- `KCD_vX.Y.Z_betaN`
- `KCD_vX.Y.Z-betaN`
- `vX.Y.Z`
- `vX.Y.Z-betaN`
- `X.Y.Z`

This allows currently published dashboard releases that use `v...` naming to be discovered without renaming historical tags.

### What is required for remote dashboard download

For a remote release template to be downloaded and used, all of the following must be true:

1. GitHub Releases API is reachable for `ccpk1/choreops-ha-dashboard`.
2. The selected release tag matches one of the accepted tag formats above.
3. The tag passes compatibility filtering:

- not below `DASHBOARD_RELEASE_MIN_COMPAT_TAG`
- satisfies `DASHBOARD_RELEASE_MIN_INTEGRATION_BY_TAG` (if mapped)

4. Template files exist in that tagged commit at:

- `templates/dashboard_full.yaml`
- `templates/dashboard_minimal.yaml`
- `templates/dashboard_admin.yaml` (when admin views are enabled)

If any requirement fails, generator behavior falls back to bundled local templates.

### Where metadata can be added

Current implementation supports compatibility metadata in integration constants:

- File: `custom_components/choreops/const.py`
- Keys:
  - `DASHBOARD_RELEASE_MIN_COMPAT_TAG`
  - `DASHBOARD_RELEASE_MIN_INTEGRATION_BY_TAG`

Template-file metadata can be placed in template header comments for human documentation, but release selection/compatibility logic currently reads from release tags + integration constants (not template headers).

### Example

- `KCD_v0.5.4` requires integration `0.5.2+`
- integration `0.5.1` → release excluded from selector
- integration `0.5.2+` → release available and can be selected

### Recovery safety net

If release lookup or compatibility filtering fails, the generator must fall back
to bundled local templates shipped with the integration package.

---

## Template File Structure

### Location

```
custom_components/choreops/templates/
├── dashboard_full.yaml      # Full-featured kid dashboard
├── dashboard_minimal.yaml   # Essential features only
└── dashboard_admin.yaml     # Parent administration view
```

### Output Format (CRITICAL)

**All templates must output a SINGLE VIEW object, not a full dashboard.**

```yaml
# ✅ CORRECT - Single view (list item)
- max_columns: 4
  title: << kid.name >> Chores
  path: << kid.slug >>
  sections:
    - type: grid
      cards: [...]

# ❌ WRONG - Full dashboard with views wrapper
views:
  - max_columns: 4
    title: << kid.name >> Chores
    ...
```

The builder combines multiple single-view outputs into `{"views": [...]}`.

---

## Jinja2 Delimiter System (Dual-Layer)

Templates use **two different Jinja2 syntaxes** for different purposes:

### Build-Time (Python Jinja2) - `<< >>`

Processed by the integration when generating the dashboard.

| Delimiter   | Purpose             | Example                            |
| ----------- | ------------------- | ---------------------------------- |
| `<< >>`     | Variable injection  | `<< kid.name >>`, `<< kid.slug >>` |
| `<% %>`     | Block statements    | `<% if condition %>...<%endif%>`   |
| `<#-- --#>` | Comments (stripped) | `<#-- This is removed --#>`        |

**Available Context Variables** (kid templates only):

```python
{
    "kid": {
        "name": "Alice",     # Display name from storage
        "slug": "alice"      # URL-safe slugified name
    }
}
```

Admin templates receive empty context `{}`.

### Runtime (Home Assistant Jinja2) - `{{ }}`

Preserved in output, evaluated by HA when rendering the dashboard.

| Delimiter | Purpose                   | Example                                  |
| --------- | ------------------------- | ---------------------------------------- |
| `{{ }}`   | HA state/attribute access | `{{ states('sensor.kc_alice_points') }}` |
| `{% %}`   | HA template logic         | `{% for item in items %}...{% endfor %}` |
| `{# #}`   | HA template comments      | `{# This stays in output #}`             |

### Example: Both Syntaxes Together

```yaml
- type: custom:mushroom-template-card
  primary: << kid.name >>'s Points
  secondary: >-
    {{ states('sensor.kc_<< kid.slug >>_points') | int }} points
```

**After build-time render** (for kid "Alice"):

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
<#-- Integration: v0.5.0-beta3 (Schema 43)         --#>
<#-- ============================================= --#>
<#--                                               --#>
<#-- [Brief description of this template]          --#>
<#-- OUTPUT: Single view object (combined by builder) --#>
<#--                                               --#>
<#-- Injection variables (Python Jinja2 << >>):    --#>
<#--   << kid.name >> - Child's display name        --#>
<#--   << kid.slug >> - URL-safe slug for path      --#>
<#--                                               --#>
<#-- All HA Jinja2 {{ }} syntax is preserved as-is --#>
<#-- ============================================= --#>

- max_columns: 4
  title: ...
```

For admin templates, omit the injection variables section and note "No injection needed".

---

## Entity ID Pattern

When referencing ChoreOps entities in templates, use the pattern below. Never hard code entity names:

```
{#-- 1. User Configuration --#}

{%- set name = '<< kid.name >>' -%}  {#-- ⬅️ CHANGE THIS to your child's actual name #}


{#-- 2. Initialize Variables --#}
{%- set dashboard_helper = integration_entities('choreops')
    | select('search', 'ui_dashboard_helper')
    | list
    | expand
    | selectattr('attributes.purpose', 'eq', 'purpose_dashboard_helper')
    | selectattr('attributes.kid_name', 'eq', name)
    | map(attribute='entity_id')
    | first
    | default("err-dashboard_helper_missing", true) -%}
```

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

template_path = Path("custom_components/choreops/templates/dashboard_full.yaml")
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

context = {"kid": {"name": "TestKid", "slug": "testkid"}}
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

### Dashboard Helper Chore Fields

The `sensor.kc_<kid>_ui_dashboard_helper` provides enriched chore data with these attributes:

#### Core Chore Fields (v0.4.x)

| Field      | Type   | Description                                | Example                   |
| ---------- | ------ | ------------------------------------------ | ------------------------- |
| `eid`      | string | Entity ID of the chore's kid status sensor | `sensor.kc_alice_chore_1` |
| `name`     | string | Human-readable chore name                  | `"Wash Dishes"`           |
| `state`    | string | Current chore state                        | `"pending"`, `"claimed"`  |
| `labels`   | list   | Categorization tags                        | `["kitchen", "daily"]`    |
| `grouping` | string | UI grouping hint                           | `"morning"`, `"evening"`  |
| `is_am_pm` | bool   | Whether chore uses 12-hour time format     | `true`, `false`           |

#### New v0.5.0 Rotation & Restriction Fields

| Field           | Type         | Description                                                | Example                                  |
| --------------- | ------------ | ---------------------------------------------------------- | ---------------------------------------- |
| `lock_reason`   | string\|null | Why chore is locked (null = not locked)                    | `"waiting"`, `"not_my_turn"`, `"missed"` |
| `turn_kid_name` | string\|null | Current turn holder (rotation chores only)                 | `"Bob"`, `null`                          |
| `available_at`  | string\|null | ISO timestamp when chore becomes available (waiting state) | `"2026-02-10T17:30:00Z"`, `null`         |

### Jinja2 Template Examples

#### Rotation Status Display

```yaml
- type: custom:mushroom-template-card
  primary: |
    {%- set chore = chores_list[0] -%}
    {{ chore.name }}
    {%- if chore.turn_kid_name -%}
    {%- if chore.turn_kid_name == name -%}
    🎯 (Your Turn)
    {%- else -%}
    ⏳ ({{ chore.turn_kid_name }}'s Turn)
    {%- endif -%}
    {%- endif -%}
  secondary: |
    {%- set chore = chores_list[0] -%}
    {%- if chore.lock_reason == "not_my_turn" -%}
    Wait for {{ chore.turn_kid_name }} to complete their turn
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
      - entity_id: "sensor.kc_<< kid.slug >>_ui_dashboard_helper"
        options:
          type: custom:mushroom-template-card
          primary: |
            {%- for chore in state_attr(config.entity, 'chores') -%}
            {%- if chore.turn_kid_name -%}
            {{ chore.name }}:
            {%- if chore.turn_kid_name == '<< kid.name >>' -%}
            🎯 Your turn
            {%- else -%}
            {{ chore.turn_kid_name }}'s turn
            {%- endif -%}
            {%- if not loop.last %} • {% endif -%}
            {%- endif -%}
            {%- endfor -%}
```

### State to Color Mapping

Standard colors for chore states and lock reasons:

| State/Lock    | Color    | Icon Suggestion       | Meaning                            |
| ------------- | -------- | --------------------- | ---------------------------------- |
| `pending`     | `blue`   | `mdi:clipboard-list`  | Ready to claim                     |
| `claimed`     | `orange` | `mdi:hand-wave`       | Awaiting parent approval           |
| `approved`    | `green`  | `mdi:check-circle`    | Completed and approved             |
| `overdue`     | `red`    | `mdi:alert-circle`    | Past due date                      |
| `waiting`     | `red`    | `mdi:clock-outline`   | Before due window opens            |
| `not_my_turn` | `purple` | `mdi:account-clock`   | Rotation - not current turn holder |
| `missed`      | `grey`   | `mdi:calendar-remove` | Terminal state - wait for reset    |

---

## Adding a New Template Style

1. **Create template file**: `templates/dashboard_[style].yaml`
2. **Add constant**: `const.py` → `DASHBOARD_STYLE_[STYLE]`
3. **Add to style options**: `dashboard_helpers.py` → `build_dashboard_style_options()`
4. **Add translation**: `translations/en.json` → style label
5. **Test render**: Use validation script above

---

## Fetching Priority

Templates are fetched in this order:

1. **Selected compatible release tag** (or newest compatible when not explicitly selected)
2. **Fallback compatible release** (when selected release is unavailable)
3. **Local bundled template**: `custom_components/choreops/templates/dashboard_[style].yaml`

Release-based fetch keeps template selection deterministic; local fallback preserves offline/recovery safety.

---

## Common Pitfalls

| Issue                                 | Cause                           | Solution                                    |
| ------------------------------------- | ------------------------------- | ------------------------------------------- |
| `mapping values are not allowed here` | Malformed comment block         | Check all `<#-- --#>` pairs                 |
| `Template did not produce valid view` | Output has `views:` wrapper     | Remove wrapper, start with `- max_columns:` |
| Entity IDs not working                | Wrong slug format               | Use `<< kid.slug >>` not `<< kid.name >>`   |
| HA Jinja2 stripped                    | Used `<< >>` instead of `{{ }}` | Use `{{ }}` for runtime evaluation          |
| Build variables not replaced          | Used `{{ }}` instead of `<< >>` | Use `<< >>` for build-time injection        |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│ BUILD-TIME (Python)          RUNTIME (Home Assistant)   │
├─────────────────────────────────────────────────────────┤
│ << variable >>               {{ states('sensor.x') }}   │
│ <% if cond %>...<% endif %>  {% if cond %}...{% endif %}│
│ <#-- stripped comment --#>   {# preserved comment #}    │
├─────────────────────────────────────────────────────────┤
│ Context: kid.name, kid.slug  Context: Full HA state     │
│ When: Dashboard generation   When: Dashboard render     │
└─────────────────────────────────────────────────────────┘
```
