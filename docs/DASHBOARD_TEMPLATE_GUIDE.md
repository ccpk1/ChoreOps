# Dashboard Template Guide

**Version**: 1.0.1 | **Last Updated**: 2026-03-12

This guide documents the rules and patterns for creating, modifying, and managing ChoreOps dashboard templates.

## Companion design guideline

For visual consistency standards (typography, state colors, icon semantics, and card behavior), use this guide together with `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`.

## Authority and source-of-truth model

Use this guide as the canonical architecture and runtime contract reference for dashboard template authoring.

Repository ownership boundaries:

- Canonical authoring source: `ccpk1/ChoreOps-Dashboards`
- Vendored runtime mirror in integration: `custom_components/choreops/dashboards`

Contribution rules:

- Submit template, registry, preference, and translation source PRs in `ccpk1/ChoreOps-Dashboards`.
- Do not submit manual source PRs against `custom_components/choreops/dashboards` in `ccpk1/ChoreOps`.
- Mirror canonical updates via `utils/sync_dashboard_assets.py`.

Translation source rules:

- Dashboard translation source edits are made only in `choreops-dashboards/translations/en_dashboard.json`.
- Non-English dashboard translation files are pipeline-managed artifacts and must not be manually edited.

### Execution boundary contract (guide vs agent)

To keep agent instructions concise and token-efficient, use this boundary split:

| Location                                                    | Owns                                                   | Should include                                                                                                            | Should avoid                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `docs/DASHBOARD_TEMPLATE_GUIDE.md`                          | Durable dashboard architecture and authoring contracts | Source-of-truth rules, template structure, Jinja contracts, dependency policy, sync/parity workflow, canonical references | Step-by-step phase execution behavior tied to one initiative |
| `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`                     | Durable UX semantics                                   | State communication, typography, color semantics, icon mapping, card behavior conventions                                 | Runtime flow mechanics and release-selection internals       |
| Agent file (`.github/agents/dashboard-ux-builder.agent.md`) | Operational execution behavior                         | Minimal workflow loop, critical guardrails, validation commands, handoffs, pointers to docs                               | Full architecture duplication from guides                    |

Agent design principle:

- Keep agent files short and high-signal.
- Put stable, detailed guidance in docs and reference those docs from the agent.

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

### Required workflow for testable changes

When canonical dashboard changes must be available to integration runtime for testing:

1. Update canonical assets in `choreops-dashboards/*`.
2. Run `python utils/sync_dashboard_assets.py` from `choreops`.
3. Run `python utils/sync_dashboard_assets.py --check`.
4. Run relevant dashboard tests in `choreops`.

### Shared-template contract (hard fork)

Shared fragments are authoring-only source assets under:

- `choreops-dashboards/templates/shared/*.yaml`

Include markers in non-shared templates use this syntax:

- `<< template_shared.<fragment_id> >>`

`fragment_id` mapping rules:

- Relative path from `templates/shared/` without `.yaml`
- Examples:
  - `templates/shared/chore_row_user_chores_v1.yaml` → `<< template_shared.chore_row_user_chores_v1 >>`
  - `templates/shared/rows/chore/action_v1.yaml` → `<< template_shared.rows/chore/action_v1 >>`

Naming/version conventions:

- Use descriptive snake_case ids with explicit suffixes for versioned contract blocks (for example `_v1`, `_v2`).
- Treat shared fragments as reusable source modules; do not write business logic variants that differ only by whitespace or formatting.

Runtime and sync rules:

- Canonical and vendored template assets are kept byte-identical by sync/parity checks.
- `templates/shared/*` is part of the vendored runtime mirror and must be present on disk.
- Marker composition happens in generator/runtime compile paths (prepared-assets compile and local template fetch), not during sync or release-apply writes.
- Missing or circular fragment references are hard failures in compile paths.

Registry contract fields for shared fragments (Phase 3C):

- `shared_contract_version`: contract parser version for shared fragment metadata.
- `shared_fragments_required`: required fragment ids used for release-prepare closure checks.
- `shared_fragments_optional`: optional fragment ids reserved for non-blocking governance.

Field rules:

- The shared contract object is optional for legacy templates (backward compatible).
- When any shared contract field is present, `shared_contract_version` must be `1`.
- Fragment ids must match the same marker id namespace as `template_shared.<id>`.
- Duplicate ids and overlap between required/optional sets are invalid.

### Color authoring contract (required)

Dashboard template color usage is governed by a strict default/exception model:

- Default requirement: use Home Assistant theme variables for color sourcing.
- Exception requirement: if a product-specific non-theme color is intentionally
  needed, declare it as a named template variable before use.

Authoring rules:

- Prefer existing Lovelace/Home Assistant variables such as
  `var(--primary-color)`, `var(--warning-color)`, `var(--error-color)`,
  `var(--success-color)`, `var(--primary-text-color)`,
  `var(--secondary-text-color)`, `var(--divider-color)`, and
  `var(--card-background-color)`.
- Do not scatter direct hex, rgb, rgba, or `color-mix(...)` literals based on
  raw hex values throughout templates when a theme variable already expresses
  the intended semantic meaning.
- If a non-theme accent is required for ChoreOps-specific semantics, it must be
  declared once near the template's user-configuration block or in a shared
  template variable contract, then referenced by semantic name everywhere else.
- Semantic variable names are required. Use names such as `pref_claim_accent`,
  `pref_due_accent`, `pref_overdue_accent`, `pref_steal_accent`, or another
  clearly scoped product-purpose name.
- Repeated non-theme colors must never be duplicated as inline literals across
  multiple style blocks, card definitions, or HTML fragments.

Allowed exception examples:

- Chore state accents
- Reward request/claim accents
- Other explicitly product-owned accent semantics that should remain stable
  independent of the active HA theme

Maintenance rule:

- If a color might need coordinated future updates across multiple dashboards or
  shared fragments, it must be managed through a declared variable rather than
  a direct literal.

### Optional local preload loop (UX iteration)

When iterating on dashboard UX and you need realistic local test data quickly:

1. Validate scenario and intended load operations only:

```bash
python utils/load_test_scenario_to_live_ha.py --dry-run
```

2. Load scenario data into a local Home Assistant dev instance:

```bash
HASS_TOKEN="<token>" python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_full.yaml --ha-url http://localhost:8123
```

For dashboard UX state testing (for example waiting/due/overdue), use the UX driver scenario:

```bash
HASS_TOKEN="<token>" python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_ux_states.yaml --ha-url http://localhost:8123 --reset --seed-states
```

If you prefer not to export `HASS_TOKEN`, pass the token directly for a one-off local run:

```bash
python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_ux_states.yaml --ha-url http://localhost:8123 --reset --seed-states --token "<token>"
```

3. For a clean reload cycle, reset transactional data first:

```bash
HASS_TOKEN="<token>" python utils/load_test_scenario_to_live_ha.py --reset
```

Notes:

- This utility is for local development only (not CI, not production).
- It uses current `choreops` options-flow contracts and menu keys.
- Scenario `due_date` fields support now-relative values (`now`, `now+1m`, `now+3h`, `now+7d`) for repeatable UX state windows.

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

### Custom card knowledge references (for builders and agents)

Use these as authoritative references for syntax/capability checks:

- Button card docs: `https://custom-cards.github.io/button-card/`
- Button card repository: `https://github.com/custom-cards/button-card`
- Auto-entities repository/docs: `https://github.com/thomasloven/lovelace-auto-entities`
- Home Assistant dashboards: `https://www.home-assistant.io/dashboards/`
- Home Assistant templating: `https://www.home-assistant.io/docs/configuration/templating/`

---

## Template File Structure

### Canonical and vendored locations

```
choreops-dashboards/templates/
├── user-chores-essential-v1.yaml
├── user-chores-standard-v1.yaml
├── user-gamification-premier-v1.yaml
├── user-kidschores-classic-v1.yaml
├── admin-shared-v1.yaml
├── admin-peruser-v1.yaml
├── admin-shared-kidschores-classic.yaml
└── admin-peruser-kidschores-classic.yaml

custom_components/choreops/dashboards/templates/
├── user-chores-essential-v1.yaml
├── user-chores-standard-v1.yaml
├── user-gamification-premier-v1.yaml
├── user-kidschores-classic-v1.yaml
├── admin-shared-v1.yaml
├── admin-peruser-v1.yaml
├── admin-shared-kidschores-classic.yaml
└── admin-peruser-kidschores-classic.yaml
```

### Output Format (CRITICAL)

**All templates must output a full dashboard document.**

```yaml
# ✅ CORRECT - Full dashboard document
button_card_templates:
  << template_shared.button_card_template_user_chores_row_v1 >>
views:
  - max_columns: 4
    title: << user.name >> Chores
    path: << user.slug >>
    sections:
      - type: grid
        cards: [...]

# ❌ WRONG - Bare top-level single-view list item
- max_columns: 4
  title: << user.name >> Chores
  path: << user.slug >>
  sections: [...]
```

### YAML anchors and responsive column controls

Use YAML anchors when they improve readability for repeated static maps, but keep responsive column behavior explicit and preference-driven.

YAML anchor rules:

- Allowed: standard YAML anchor/alias/merge syntax (`&anchor`, `*anchor`, `<<: *anchor`) inside template files.
- Scope: treat anchors as local-document helpers; keep anchor names descriptive and close to where they are used.
- Prefer anchors for static style/map reuse only (for example shared style blocks), not for dynamic runtime state logic.
- Do not replace shared fragment contracts (`templates/shared/*` + `<< template_shared.* >>`) with anchors; anchors are complementary, not a substitute for shared-template reuse.

Responsive column control rules:

- Prefer two explicit user-configurable prefs in chore/grid cards:
  - `pref_column_count_mobile` (for narrow screens)
  - `pref_column_count_wide` (for wider screens)
- Render separate grid cards using screen conditionals:
  - mobile: `(max-width: 768px)`
  - wide: `(min-width: 769px)`
- Keep both branches functionally equivalent except for column count.

Reference pattern:

```jinja
{%- set pref_column_count_mobile = 1 -%}
{%- set pref_column_count_wide = 3 -%}
{%- set pref_column_count_mobile = pref_column_count_mobile | int(default=1) -%}
{%- set pref_column_count_wide = pref_column_count_wide | int(default=3) -%}

{{
  {
    'type': 'vertical-stack',
    'cards': [
      {
        'type': 'conditional',
        'conditions': [{'condition': 'screen', 'media_query': '(max-width: 768px)'}],
        'card': {'type': 'grid', 'columns': pref_column_count_mobile, 'square': false, 'cards': ns.group_cards}
      },
      {
        'type': 'conditional',
        'conditions': [{'condition': 'screen', 'media_query': '(min-width: 769px)'}],
        'card': {'type': 'grid', 'columns': pref_column_count_wide, 'square': false, 'cards': ns.group_cards}
      }
    ]
  }
}},
```

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

### Metadata stamp and reusable snippet contract

Templates now receive two additional build-time context objects:

- `dashboard_meta` for per-render metadata values
- `template_snippets` for canonical reusable setup/validation blocks

#### `dashboard_meta` fields

```python
{
  "dashboard_meta": {
    "integration_entry_id": "<config-entry-id>",
    "template_id": "<template-id>",
    "effective_ref": "<resolved-release-ref-or-none>",
    "release_version": "<local-release-version-or-none>",
    "generated_at": "<iso-utc-timestamp>"
  }
}
```

#### `template_snippets` keys (canonical)

- `template_snippets.user_setup`
- `template_snippets.user_validation`
- `template_snippets.user_override_helper`
- `template_snippets.admin_setup_shared`
- `template_snippets.admin_setup_peruser`
- `template_snippets.admin_validation_missing_selector`
- `template_snippets.admin_validation_invalid_selection`
- `template_snippets.meta_stamp`

Required usage rules:

1. Use canonical snippet keys only (no ad-hoc snippet variants).
2. Keep card header comment first, then place snippet insertions.
3. Keep numbered section order (configuration before validation, then render/data).

Canonical insertion pattern (user cards):

```jinja
{#-- ===== <CARD NAME> CARD ===== --#}
<< template_snippets.meta_stamp >>

{#-- 1. User Configuration --#}
<< template_snippets.user_override_helper >>

{#-- 2. Dynamic Lookups & Validations --#}
<< template_snippets.user_setup >>
<< template_snippets.user_validation >>
```

Canonical insertion pattern (admin cards):

```jinja
{#-- ===== <CARD NAME> CARD ===== --#}
<< template_snippets.meta_stamp >>

{#-- 1. User Configuration --#}
<< template_snippets.user_override_helper >>

{#-- 2. Dynamic Lookups & Validations --#}
<< template_snippets.admin_setup_shared >>
<< template_snippets.admin_validation_missing_selector >>
<< template_snippets.admin_validation_invalid_selection >>
```

#### Metadata stamp format and placement

Stamp format is canonical and compact:

- `META STAMP: {template_id} • {release} • {generated_at}`

Placement rule:

- Put `template_snippets.meta_stamp` as the first inserted line inside each card template block, directly under the card header comment.

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
<#-- Integration: 1.0.0 (Schema 100)               --#>
<#-- ============================================= --#>
<#--                                               --#>
<#-- [Brief description of this template]          --#>
<#-- OUTPUT: Full dashboard document with root keys --#>
<#--                                               --#>
<#-- Injection variables (Python Jinja2 << >>):    --#>
<#--   << user.name >> - User display name           --#>
<#--   << user.slug >> - URL-safe slug for path      --#>
<#--   << user.user_id >> - User identity UUID       --#>
<#--   << integration.entry_id >> - Instance scope ID --#>
<#--                                               --#>
<#-- All HA Jinja2 {{ }} syntax is preserved as-is --#>
<#-- ============================================= --#>

button_card_templates:
  << template_shared.<fragment_id> >>
views:
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

template_path = Path("custom_components/choreops/dashboards/templates/user-gamification-premier-v1.yaml")
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
if isinstance(config, dict) and isinstance(config.get("views"), list) and len(config["views"]) > 0:
  print(f"✅ Valid: Parsed as dashboard dict, root keys: {list(config.keys())[:5]}")
else:
  print(f"❌ Invalid: Expected dict with views list, got {type(config)}")
EOF
```

### 3. View Structure Check

Ensure output has required keys:

- `views` - Top-level list of rendered views
- optional `button_card_templates` - Top-level template contract block

- `title` - View tab title
- `path` - URL path segment (unique per view)
- `sections` or `cards` - Content

---

## Chore Attributes Reference

### State/status source-of-truth precedence (required)

Use backend-provided attributes as the canonical source whenever available.

1. Prefer `state_attr(chore.eid, 'global_state')` for shared/global status display
   (`completed_in_part`, `claimed_in_part`, etc.).
2. Use chore `state` as fallback when `global_state` is unavailable.
3. Use blocker attributes (`can_claim`, `block_reason`) for claim-action gating and
   blocked-state messaging.
4. Derive values only when no canonical attribute exists (for example, shared-all
   progress ratio from `assigned_user_names` + `completed_by`).

Authoring rule:

- Do not override canonical backend state with frontend heuristics when a matching
  attribute is already provided by the sensor/helper payload.

### Dashboard helper chore fields

The dashboard helper resolved via `dashboard_lookup_key = <integration.entry_id>:<user.user_id>` provides enriched chore data with these attributes:

#### Current helper field classes (v1 contract baseline)

Treat the current dashboard-helper surface as four field classes when evaluating
sharding behavior:

| Class | Current fields | Notes |
| ----- | -------------- | ----- |
| `row data` | `chores`, `rewards`, `badges`, `bonuses`, `penalties`, `achievements`, `challenges`, `points_buttons` | Lists consumed directly by dashboard cards |
| `derived indexes` | `chores_by_label` | Transitional backend convenience index scheduled for removal from transport |
| `auxiliary catalogs` | `pending_approvals`, `core_sensors`, `ui_control` | Supporting payloads that stay on the main helper in the first shard release |
| `plumbing/meta` | `dashboard_helpers`, `user_name`, `user_id`, `integration_entry_id`, `dashboard_lookup_key`, `language`, `gamification_enabled` | Lookup, identity, and helper-pointer fields |

Authoring rule:

- Treat `chores` as the canonical chore transport surface.
- Do not build new template dependencies on `chores_by_label`; it is being removed
  from backend transport for the shard contract.

#### Shared snippet lookup and caching contract

Maintained chore dashboards are expected to follow this sequence once per card:

1. Resolve `dashboard_helper` from `dashboard_lookup_key`.
2. Resolve `dashboard_helpers` from the main helper.
3. Read `dashboard_helpers.chore_helper_eids` once and default it to `[]`.
4. Read all referenced shard helpers once and merge their `chores` rows into one
   in-memory `chore_list`.
5. Perform grouping, filtering, sorting, and label reconstruction from the merged
   in-memory list instead of calling `state_attr()` repeatedly inside loops.

Authoring rules:

- `dashboard_helpers.chore_helper_eids` is always present and always a list.
- Below the shard threshold, use the inline `chores` list from the main helper and
  expect `dashboard_helpers.chore_helper_eids == []`.
- Above the shard threshold, expect shard-backed `chores` transport and do not rely
  on a parallel inline compatibility slice.
- Resolve shard helper payloads once per card and cache the merged result in local
  Jinja namespace variables.
- Do not impose a template-side cap on resolved shard helpers in v1; consume the
  full ordered pointer list exactly once per card.

#### Core Chore Fields (v0.4.x)

| Field      | Type   | Description                            | Example                   |
| ---------- | ------ | -------------------------------------- | ------------------------- |
| `eid`      | string | Entity ID of the chore status sensor   | `sensor.kc_alice_chore_1` |
| `name`     | string | Human-readable chore name              | `"Wash Dishes"`           |
| `state`    | string | Current chore state                    | `"pending"`, `"claimed"`  |
| `labels`   | list   | Categorization tags                    | `["kitchen", "daily"]`    |
| `grouping` | string | UI grouping hint                       | `"morning"`, `"evening"`  |
| `is_am_pm` | bool   | Whether chore uses 12-hour time format | `true`, `false`           |

#### Canonical chore sensor attributes used by templates

When rendering row state/status for a chore card, prefer sensor attributes sourced
from `chore.eid`:

| Field          | Type         | Use for                                               |
| -------------- | ------------ | ----------------------------------------------------- |
| `global_state` | string\|null | Canonical global/shared status (`*_in_part` included) |
| `can_claim`    | bool         | Claim action enable/disable                           |
| `block_reason` | string\|null | Canonical blocker reason label/icon selection         |
| `state`        | string       | Fallback status when `global_state` is unavailable    |

#### Rotation and restriction fields

Note: Some runtime payload keys still use legacy names for backward compatibility. In this guide, treat those fields as user-scoped semantics.

| Field            | Type         | Description                                                | Example                                  |
| ---------------- | ------------ | ---------------------------------------------------------- | ---------------------------------------- |
| `lock_reason`    | string\|null | Why chore is locked (null = not locked)                    | `"waiting"`, `"not_my_turn"`, `"missed"` |
| `turn_user_name` | string\|null | Current turn holder user name                              | `"Bob"`, `null`                          |
| `available_at`   | string\|null | ISO timestamp when chore becomes available (waiting state) | `"2026-02-10T17:30:00Z"`, `null`         |

#### Shard helper contract (v1)

When shard mode activates, the main helper remains the canonical dashboard entry
point and exposes shard pointers at `dashboard_helpers.chore_helper_eids`.

Main-helper contract additions:

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `dashboard_helpers.chore_helper_eids` | list[string] | Ordered shard helper entity IDs; always present, `[]` when no shards exist |

Shard-helper payload contract:

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `purpose` | string | Typed purpose marker for chore shard helpers |
| `chores` | list[dict] | Chore rows for this shard only |
| `shard_index` | int | 1-based shard position |
| `shard_count` | int | Total shard count for the user |
| `helper_contract_version` | int | Shard contract version for template compatibility |

Lifecycle and mode contract:

- Shard mode is runtime-owned by `ui_manager`.
- The transport mode is mutually exclusive: either inline `chores` on the main
  helper or shard-backed `chores`, not both in parallel for the same user state.
- Shard mode enters at or above 14 KB of accepted serialized helper size and exits
  only at or below 12 KB.
- Dashboards consume shard helpers only through
  `dashboard_helpers.chore_helper_eids`.

Naming contract:

- Backend unique IDs are deterministic, typed chore-shard identifiers with an
  explicit shard index.
- Human-facing names follow the equivalent of `Chore List 1`, `Chore List 2`, and
  so on.

Diagnostics contract:

- Keep shard-helper diagnostics minimal: `purpose`, `shard_index`, `shard_count`,
  and `helper_contract_version`.
- Keep current mode, resolved shard helper entity IDs, last accepted serialized
  size, and last reconciliation outcome on the main helper runtime diagnostic
  surface.

#### Label reconstruction contract

`chores_by_label` is removed from backend transport in the shard contract.
Templates must rebuild label groups from the merged in-memory `chore_list`.

Authoring rules:

- Reconstruct label groups after the full merged `chore_list` is available.
- Apply label ordering and exclusions to reconstructed groups, not to backend index
  data.
- Treat label reconstruction as a shared-snippet responsibility for maintained
  chore dashboards.

#### Legacy and partial-failure handling

Maintained shard-aware snippets should treat missing or unavailable chore shard
helpers as contributing zero rows to the merged `chore_list` and continue
rendering the data that is available.

Authoring rules:

- Inspect `shard_runtime` on the main helper for diagnostics only; do not require
  per-shard recovery logic in dashboard cards.
- Legacy dashboards that read only `state_attr(dashboard_helper, 'chores')`
  continue to work for inline mode, but they do not automatically merge shard
  helpers after threshold-triggered sharding activates.
- Maintained shared snippets are the only supported automatic merge path for
  shard-backed chore transport.

#### Compatibility matrix

| Template/profile | Shard-aware shared snippet path required | Extended-scale target |
| ---------------- | ---------------------------------------- | --------------------- |
| `user-gamification-premier-v1` | Yes | Yes |
| `user-chores-standard-v1` | Yes | Yes |
| `user-chores-essential-v1` | Yes, for compatibility with `chores_by_label` removal | No |

Compatibility rules:

- `user-gamification-premier-v1` and `user-chores-standard-v1` are maintained
  scale targets and must support the shard contract.
- `user-chores-essential-v1` must remain functionally compatible with the removal
  of `chores_by_label`, but it is not an extended-scale acceptance target.
- Legacy dashboards that read `state_attr(dashboard_helper, 'chores')` directly do
  not receive automatic shard merging and should be treated as fallback/legacy
  consumers.

#### Worked examples

Small household example:

- User with 20 chores: main helper carries inline `chores`; `dashboard_helpers`
  includes `chore_helper_eids: []`.

Large household example:

- User with 120 chores: main helper remains the canonical lookup surface;
  `dashboard_helpers.chore_helper_eids` contains ordered chore shard helper entity
  IDs and maintained templates merge shard `chores` rows into one local
  `chore_list` before rendering.

#### Future typed-family example

The reusable shard pattern is documented for chores now and rewards next.
Future payload families should reuse the same lifecycle and pointer pattern while
keeping public helper surfaces typed by family.

### Dashboard helper UI control fields

The dashboard helper also exposes the persisted per-user UI control payload for
dashboard rendering:

| Field        | Type | Description                                                  |
| ------------ | ---- | ------------------------------------------------------------ |
| `ui_control` | dict | Resolved per-user UI control payload for dashboard rendering |

Authoring rules:

- Read this surface with `state_attr(dashboard_helper, 'ui_control')`.
- Treat it as read-only.
- Treat missing keys as the default UI state.
- A blank-key `remove` call to `choreops.manage_ui_control` clears all persisted UI preferences for the targeted user, so helper consumers naturally fall back to dashboard defaults on the next refresh.
- Keep key naming stable within the template/profile that owns the control.
- Do not read or rely on backend storage outside this helper attribute.

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

---
