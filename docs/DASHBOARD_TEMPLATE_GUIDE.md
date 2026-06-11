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
| `auxiliary catalogs` | `pending_approvals`, `core_sensors`, `ui_control`, `dashboard_config` | Supporting payloads that stay on the main helper in the first shard release |
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

Recommended dynamic pattern:

```jinja
{%- set dashboard_helper = config.entity -%}
{%- set dashboard_helpers = state_attr(dashboard_helper, 'dashboard_helpers') or {} -%}
{%- set ns = namespace(chore_list=(state_attr(dashboard_helper, 'chores') or [])) -%}
{%- for chore_helper in dashboard_helpers.get('chore_helper_eids', []) -%}
  {%- set ns.chore_list = ns.chore_list + (state_attr(chore_helper, 'chores') or []) -%}
{%- endfor -%}
```

Use `ns.chore_list` as the only chore source for filtering, grouping, and rendering.
This works in both inline mode and shard mode because the shard pointer list is
empty when no extra helpers are needed.

Limited legacy inline-only pattern:

```jinja
{%- set chores = state_attr(config.entity, 'chores') or [] -%}
```

This shorter pattern still works for small households and quick one-off templates,
but it is not shard-aware. Once a user reaches roughly 40 assigned chores
(depending on row size and other helper payload fields), the helper may switch to
shard-backed transport and the inline-only pattern can miss rows.

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

Practical migration guidance:

- If you want a template to stay dynamic as households grow, always merge chore
  rows from `dashboard_helpers.chore_helper_eids` into one local `chore_list`
  before rendering.
- If you intentionally want the shortest possible snippet for a smaller household,
  the inline-only `state_attr(dashboard_helper, 'chores')` pattern is still valid,
  but treat it as a limited convenience pattern rather than the long-term default.

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
            {%- set dashboard_helpers = state_attr(config.entity, 'dashboard_helpers') or {} -%}
            {%- set ns = namespace(chore_list=(state_attr(config.entity, 'chores') or [])) -%}
            {%- for chore_helper in dashboard_helpers.get('chore_helper_eids', []) -%}
            {%- set ns.chore_list = ns.chore_list + (state_attr(chore_helper, 'chores') or []) -%}
            {%- endfor -%}
            {%- for chore in ns.chore_list -%}
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

For a very small household, you can shorten the example back to a direct
`state_attr(config.entity, 'chores')` loop, but that should be treated as the
small-household shortcut only. The merged `ns.chore_list` pattern is the supported
dynamic version.

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

# Button-Card Authoring Rules & Syntax Reference

**Version**: 1.0.0 | **Added**: 2026-06-09

This section defines the complete syntax contract for `custom:button-card` in
ChoreOps dashboard templates. Every rule is derived from working patterns in the
canonical templates. Nothing here is theoretical.

---

## 1. Two-Layer Jinja Architecture

Dashboard templates use **two independent Jinja environments** that must never
be confused:

| Layer          | Delimiters              | When it runs          | Purpose                                  |
| -------------- | ----------------------- | --------------------- | ---------------------------------------- |
| **Build-time** | `<< >>`, `<% %>`, `<#-- --#>` | `render_dashboard_template()` | User name injection, snippet inclusion   |
| **HA runtime** | `{{ }}`, `{% %}`, `{# #}`            | Home Assistant dashboard render | State access, conditionals, card output  |

**Critical rule**: Cards inside `filter.template: |-` blocks are HA runtime
Jinja. All `{% %}`, `{{ }}`, and `{# #}` syntax in those blocks is evaluated
by Home Assistant, not by the build-time renderer.

```jinja
# ✅ CORRECT — HA runtime Jinja inside filter.template
filter:
  template: |-
    {%- set has_helper = dashboard_date_helper not in ['', None, 'None'] -%}
    {{ {
      'type': 'custom:button-card',
      ...
    } }},

# ❌ WRONG — build-time delimiters inside filter.template
filter:
  template: |-
    << user.name >>   {# this won't be replaced by build-time renderer #}
```

---

## 2. Card Declaration Patterns

### 2.1 Single card output

A button-card is emitted as a Jinja `{{ }}` expression containing a Python
dict literal:

```jinja
{{ {
  'type': 'custom:button-card',
  'entity': some_entity_id,
  'show_name': True,
  'icon': 'mdi:calendar-sync',
  'name': ui.get('reschedule_chores', 'err-reschedule_chores'),
  'tap_action': {'action': 'none'},
} }},
```

Note the trailing comma — cards in a list are comma-separated.

### 2.2 Conditional card output

Use `{%- if %}` around the **entire** `{{ }}` block — never inside it:

```jinja
{%- if not header_collapsed and has_selected_user -%}
{{ { 'type': 'custom:button-card', ... } }},
{%- endif -%}
```

### 2.3 Inline conditional on a single property

Use a Python ternary expression inside the dict literal:

```jinja
# Single-line ternary
'entity': dashboard_date_helper if has_reschedule_date_helper else selected_dashboard_helper,

# Multi-line service call ternary (parenthesize the call-service dict)
'tap_action': ({
  'action': 'call-service',
  'service': 'choreops.reschedule_chores_after',
  'data': {
    'config_entry_id': integration_entry_id,
    'user_names': [selected_user_name],
    'after': after_datetime,
  }
}) if has_after_datetime else {'action': 'none'},
```

### 2.4 Inline conditional for style values

```jinja
{'display': 'none' if selected_user_paused else 'block'},
```

---

## 3. Key Naming and Quoting

### 3.1 All dict keys use single-quoted strings

Inside `{{ }}` Jinja expressions, you are writing Python dict literals:

```jinja
# ✅ CORRECT
'tap_action': {'action': 'call-service', 'service': 'choreops.pause_user_chores'}

# ❌ WRONG — unquoted keys
tap_action: {action: call-service}
```

### 3.2 Nested string quoting

Nest double quotes inside single-quoted strings:

```jinja
# ✅ CORRECT
{'grid-template-areas': '"i n . pick" "i l . pick" ". indep all ."'},

# ❌ WRONG — unescaped double quotes break the string
{'grid-template-areas': "i n . pick" "i l . pick"},
```

---

## 4. Boolean Values

### 4.1 In Jinja `{{ }}` dict expressions

Both Python `True`/`False` and Jinja `true`/`false` work because Jinja2 maps
`true` → Python `True`. YAML output always uses lowercase `true`/`false`.

```jinja
# These are equivalent in the final rendered YAML:
'show_name': True,
'show_icon': true,
```

### 4.2 In `{%- set %}` assignments

Use `true`/`false` (lowercase, Jinja native):

```jinja
{%- set has_after_datetime = after_datetime != '' -%}
{%- set skip_render = true -%}
```

### 4.3 String-to-boolean conversion

Jinja2 does **not** have a `bool()` function. Compare strings:

```jinja
{%- set pref_show_header = (pref_show_header | default('true') | string | lower) == 'true' -%}
```

### 4.4 Default-to-boolean from state attributes

```jinja
{%- set gamification_enabled = state_attr(dashboard_helper, 'gamification_enabled') | default(false, true) -%}
```

---

## 5. `custom_fields` — The Dual-Form Contract

`custom_fields` serves **two completely different purposes** depending on where
it appears. Confusing them is the single most common source of button-card bugs.

### 5.1 Form A: Embedded sub-cards (card-level `custom_fields`)

When `custom_fields` is a **direct property of a button-card**, each key maps
to a **nested button-card** wrapped in a `'card'` dict:

```jinja
{
  'type': 'custom:button-card',
  'entity': dashboard_date_helper,
  'custom_fields': {
    'pick': {
      'card': {
        'type': 'custom:button-card',
        'entity': dashboard_date_helper,
        'icon': 'mdi:calendar-search',
        'show_name': False,
        'show_icon': True,
        'tap_action': {'action': 'more-info'},
        'styles': {
          'card': [{'width': '34px'}, {'height': '34px'}],
          'icon': [{'width': '18px'}],
        }
      }
    },
    'indep': {
      'card': {
        'type': 'custom:button-card',
        'show_name': True,
        'show_state': False,
        'show_icon': True,
        'icon': 'mdi:calendar-sync-outline',
        'name': ui.get('reschedule_independent', 'err-reschedule_independent'),
        'tap_action': ({...}) if condition else {'action': 'none'},
        'styles': { ... }
      }
    },
  }
}
```

Rules for Form A:
- Every key **must** have a `'card'` sub-dict with `'type': 'custom:button-card'`.
- Each embedded card gets its own `'styles'`, `'tap_action'`, `'entity'`.
- The outer card's `'entity'` **does not** propagate — set it explicitly.
- Field names (`'pick'`, `'indep'`) must match the `grid-template-areas` names.

### 5.2 Form B: Layout slot styles (`styles.custom_fields`)

When `custom_fields` appears **inside** `'styles'`, each key is a **list of
CSS style dicts** for that grid slot:

```jinja
'styles': {
  'card': [
    {'padding': '12px 14px'},
    {'border-radius': '14px'},
  ],
  'grid': [
    {'grid-template-areas': '"i n . pick" "i l . pick" ". indep all ."'},
    {'grid-template-columns': '26px 1fr 1fr 34px'},
    {'grid-template-rows': 'min-content min-content auto'},
  ],
  'custom_fields': {
    'pick': [
      {'justify-self': 'end'},
      {'align-self': 'center'},
    ],
    'indep': [
      {'justify-self': 'stretch'},
      {'align-self': 'stretch'},
    ],
    'all': [
      {'justify-self': 'stretch'},
      {'align-self': 'stretch'},
    ],
  }
}
```

Rules for Form B:
- Each key is a **list** of single-key style dicts.
- Key names must match the area names from `grid-template-areas`.
- These control CSS grid placement — not card content.
- There is **no** `'card'` wrapper in Form B.

**Do not confuse the two forms.** If you put a `'card'` wrapper inside
`styles.custom_fields`, or bare style arrays at the card-level `custom_fields`,
the card will not render correctly.

---

## 6. Styles Format

All styles use **lists of single-key dicts**. Each list item is a dict with
exactly one key:

```jinja
'styles': {
  'card': [
    {'padding': '12px 14px'},
    {'border-radius': '14px'},
    {'box-shadow': 'none'},
    {'border': '1px solid var(--divider-color)'},
    {'background-color': 'var(--card-background-color)'},
  ],
  'grid': [
    {'grid-template-areas': '"i n . pick" "i l . pick" ". indep all ."'},
    {'grid-template-columns': '26px 1fr 1fr 34px'},
    {'grid-template-rows': 'min-content min-content auto'},
    {'column-gap': '10px'},
    {'row-gap': '8px'},
    {'align-items': 'center'},
  ],
  'icon': [
    {'width': '20px'},
    {'height': '20px'},
    {'color': 'var(--primary-color)'},
  ],
  'name': [
    {'justify-self': 'start'},
    {'font-size': '13px'},
    {'font-weight': '700'},
    {'line-height': '1.2'},
  ],
  'label': [
    {'justify-self': 'start'},
    {'font-size': '12px'},
    {'color': 'var(--secondary-text-color)'},
  ],
}
```

### 6.1 Recognized style scopes

| Scope    | What it styles                             |
| -------- | ------------------------------------------ |
| `card`   | The card container (padding, border, background) |
| `grid`   | CSS grid layout (areas, columns, rows, gaps) |
| `icon`   | The card's main icon                       |
| `name`   | The primary text label                     |
| `label`  | The secondary text label                   |

### 6.2 `grid-template-areas` contract

Grid area strings use **double-quoted** row definitions. Each row is a
space-separated list of area names. Python concatenates adjacent string
literals, so all rows can sit on one line:

```jinja
{'grid-template-areas': '"i n . pick" "i l . pick" ". indep all ."'},
```

- `"i n . pick"` = row 1: icon area, name area, empty slot, picker area
- `"i l . pick"` = row 2: icon area, label area, empty slot, picker area
- `". indep all ."` = row 3: empty, indep button, all button, empty

Every area name requires:
1. A matching key in `custom_fields` (Form A) defining the sub-card, AND
2. A matching key in `styles.custom_fields` (Form B) defining the grid slot.

If either is missing, the field silently disappears.

### 6.3 Color values

Always use theme variables. Never hardcode hex/rgb values:

```jinja
# ✅ CORRECT
'var(--primary-color)'
'var(--card-background-color)'
'color-mix(in srgb, var(--primary-color) 18%, var(--divider-color))'

# ❌ WRONG
'#4CAF50'
'rgba(76, 175, 80, 0.5)'
```

Exception: product-specific accent colors must be declared as semantic
template variables (see DASHBOARD_UI_DESIGN_GUIDELINE § Color sourcing policy).

---

## 7. `tap_action` and Service Calls

### 7.1 No-op

```jinja
'tap_action': {'action': 'none'},
```

### 7.2 More-info with conditional

```jinja
'hold_action': {'action': 'more-info'} if has_reschedule_date_helper else {'action': 'none'},
```

### 7.3 Service call

```jinja
'tap_action': {
  'action': 'call-service',
  'service': 'choreops.pause_user_chores',
  'data': {
    'config_entry_id': integration_entry_id,
    'user_name': selected_user_name,
    'paused': true,
  }
},
```

### 7.4 Conditional service call

```jinja
'tap_action': ({
  'action': 'call-service',
  'service': 'choreops.pause_user_chores',
  'data': {
    'config_entry_id': integration_entry_id,
    'user_name': selected_user_name,
    'paused': true,
    'paused_until': after_datetime,
  }
}) if has_after_datetime else {'action': 'none'},
```

---

## 8. Translation Lookups

All user-visible strings use `ui.get()`:

```jinja
'name': ui.get('pause_chores', 'err-pause_chores'),
```

Keys come from `translations/en_dashboard.json`. The `ui` dict is resolved
from the translation sensor in the admin/user setup snippets.

---

## 9. Named `button_card_templates`

Defined at the dashboard root level using YAML syntax (not Jinja `{{ }}`):

```yaml
button_card_templates:
  chore_row_v1:
    type: custom:button-card
    show_name: true
    show_icon: true
    tap_action:
      action: more-info
    name: '[[[ ... JavaScript template ... ]]]'
    icon: '[[[ return entity.attributes.icon || ''mdi:broom''; ]]]'
    styles:
      card:
        - padding: 6px 8px
        - border-radius: 10px
    custom_fields:
      due:
        - justify-self: start
        - font-size: 11px
      btn_action:
        card:
          type: custom:button-card
```

Key differences from inline cards in `filter.template`:
- Uses **YAML syntax** (not Python dict literals).
- JavaScript templates use `[[[ ... ]]]` delimiters.
- `styles` keys are YAML lists (use `- key: value` not `{'key': 'value'}`).
- `custom_fields` uses the same dual-form but with YAML syntax.
- Booleans are YAML: `true`/`false` (lowercase, no quotes).

---

## 10. Common Traps

| # | Trap | Why it fails | Fix |
|---|------|-------------|-----|
| 1 | `{% if %}` inside `{{ }}` dict expression | Jinja cannot nest block tags inside expression tags. Produces `unexpected '%'` or similar syntax errors. | Use inline ternary: `'key': value if cond else other`. Never put `{% %}` inside `{{ }}`. |
| 2 | `bool(value)` in Jinja `{%- set %}` | `bool()` is not a standard Jinja2 global and caused `unexpected '%'` at runtime. Zero uses of `bool()` exist in the working template base — it is never the correct pattern. | Use `(value) == true` comparison. Example: `{%- set paused = (state_attr(helper, 'attr') if guard else false) == true -%}`. The `== true` comparison works because Jinja uses Python equality semantics. Also valid: `\| default(false, true)` for attribute fallbacks. |
| 13 | `unexpected '}'` | Unbalanced braces in a `{{ }}` dict expression — typically a missing `{` or `}` at one of the nesting levels (main card dict, `custom_fields` sub-dict, `styles` sub-dict, `data` sub-dict). | Trace brace pairs from the `{{ {` opening to the `} }}` closing. Each `{` must have a matching `}` at the same indentation level. Verify: main card `{...}`, each `custom_fields.*.card` `{...}`, each `styles` `{...}`, each `data` `{...}`. |
| 3 | Confusing Form A and Form B `custom_fields` | Form A expects `{'card': {...}}`, Form B expects `[{...}]`. Using the wrong shape silently breaks rendering. | Card-level `custom_fields` = Form A (with `card:`). `styles.custom_fields` = Form B (style lists). |
| 4 | Mismatched `grid-template-areas` and `custom_fields` keys | Button-card silently drops fields whose names don't match any grid area. | Every area name in `grid-template-areas` must be a key in both `custom_fields` forms. |
| 5 | Missing `'type': 'custom:button-card'` on Form A sub-cards | Sub-cards without explicit type render but lose click/interaction behavior. | Always include `'type': 'custom:button-card'` in every `custom_fields.*.card`. |
| 6 | `'entity'` not set on Form A sub-cards | The outer card's `'entity'` does not automatically propagate to embedded sub-cards. | Set `'entity'` explicitly on each `custom_fields.*.card`. |
| 7 | Hardcoded hex/rgb colors | Bypasses the theme system and creates maintenance burden across template variants. | Use `var(--*)` or `color-mix(...)` with theme variables. |
| 8 | `'display': 'none'` on wrong level | On Form A sub-cards, put `'display'` in the sub-card's `styles.card`. On Form B, put it in the slot's style list. Hiding the wrong container leaves blank space. | Trace which container you need to hide: the sub-card (Form A) or the grid slot (Form B). |
| 9 | Consecutive card outputs with no `{% %}` block between them | When one card's `}},` is immediately followed by another card's `{{` with only whitespace (newline, spaces) between, the auto-entities card's `render_template` result is split by `/[\s,]+/`. That regex consumes the whitespace as a separator, creating an unwanted split boundary that breaks card boundary detection and produces configuration errors. This pattern is **unique** in the template base — every other card transition has a `{% %}` block (`{%- endif -%}`, `{%- set ... -%}`, `{%- if ... -%}`) between them that naturally consumes the whitespace. | **🚨 STANDARDIZED FIX (REQUIRED)**: Insert a `{#- card_gap -#}` comment between consecutive card outputs:\n\n```\n  }}},\n  {#- card_gap -#}\n  {{\n    {\n```\n\n**Why this works**: `{#- card_gap -#}` is a Jinja2 comment with whitespace stripping on both sides. `{#-` strips all whitespace (including newlines) before the comment, and `-#}` strips whitespace after. The result is that `}},`, the newline, and `{{` are joined without any whitespace in the output — exactly like `}},{{` on one line, but readable.\n\n**Why `card_gap`**: The comment text makes the marker clearly intentional, preventing accidental cleanup. It follows the existing `{#-- ===== ... ===== --#}` section comment style used throughout the template.\n\n**Rule**: Two consecutive card outputs (no `{% %}` block between them) **MUST** have a `{#- card_gap -#}` comment between them. This is the only approved pattern for this situation. |
| 10 | `%` in date format strings | `'%a, %b %d'` inside Jinja string literals is safe — `%` is only special in Jinja block/comment delimiters, not in strings. | No fix needed — this is a false alarm. |
| 11 | Unquoted keys in `{{ }}` dicts | Python dict literals require quoted string keys. | Always quote: `'key': value`. |
| 12 | `'data'` used as a card property name | `'data'` is reserved for `tap_action` service data payloads. Using it at the card level overwrites the action data. | Only use `'data'` inside `'tap_action'`. |
| 13 | `unexpected '}'` | Missing dict-close `}` before the Jinja `}}` close. When `{{ {` opens the expression and dict on the same line, the close must be `}}},` (3 braces: 1 dict close + 2 Jinja close) or split across lines: `}\n}},`. Having only `}},` (2 braces) leaves the dict unclosed because the first `}` becomes part of `}}`. | Count braces: `{{ {` = 3 opens (2 Jinja + 1 dict). Closer needs 3 closes. Either use `}}},` on one line, or `}` on one line followed by `}},` on the next. Always match the existing pattern used by sibling cards in the same template. |
| 14 | **Lowercase `none` instead of `None`** | Inside `{{ }}` expressions, unquoted lowercase `none` is evaluated as an *undefined variable name* — it is **not** Python's `NoneType`. In strict Jinja environments this throws a render error; in lenient environments it evaluates to empty string `""`, silently breaking conditional exclusion checks like `x not in ['', none]`. | Use capitalized `None` inside `{{ }}` blocks: `integration_entry_id not in ['', None]`. The existing template base correctly uses `['', None, 'None']` everywhere — the `'None'` string catches cases where the variable serialized to the string `"None"` (which HA states often do), while bare `None` catches actual Python `NoneType`. Never write bare lowercase `none` without quotes. |
| 15 | **Chained inline ternaries with complex dict expressions** | A pattern like `'tap_action': ({...}) if cond1 else ({...}) if cond2 else {...}` inside `{{ }}` causes Jinja's parser to lose track of expression boundaries. The structural braces `{}` of the nested dicts overlap with Jinja's expression syntax, producing `unexpected '%'` or similar parse failures. This is distinct from Trap 1 (which bans `{% %}` inside `{{ }}`) — here, even a syntactically valid inline ternary fails when the branches are large dicts. | **Never use chained inline ternaries for complex dict-valued `tap_action` (or similar) logic.** Extract the value into a `{%- set %}` block with explicit `{%- if %}`/`{%- elif %}`/`{%- else -%}` branches before the card dict, then reference the set variable:\n\n```jinja\n{#-- Build tap_action using set blocks to avoid ternary precedence issues --#}\n{%- set my_tap_action = {'action': 'none'} -%}\n{%- if integration_entry_id not in ['', None] and selected_user_id not in ['', None] -%}\n  {%- if not all_chores_expanded -%}\n    {%- set my_tap_action = {\n      'action': 'call-service',\n      'service': 'choreops.manage_ui_control',\n      'data': { ... }\n    } -%}\n  {%- else -%}\n    {%- set my_tap_action = {\n      'action': 'call-service',\n      'service': 'choreops.manage_ui_control',\n      'data': { ... }\n    } -%}\n  {%- endif -%}\n{%- endif -%}\n```\n\nThen reference it simply: `'tap_action': my_tap_action,`. Simple ternaries (single line, no nested dicts) remain safe. |

---

## 11. Validation Checklist for New Button-Cards

1. **Jinja purity**: Zero `{% %}` inside any `{{ }}` block. All conditionals use inline ternaries. Exception: complex tap_action logic uses `{%- set %}` blocks (see Trap 15).
2. **`None` not `none`**: All bare NoneType comparisons use capitalized `None` inside `{{ }}`. Lowercase `none` is never used unquoted (see Trap 14).
3. **custom_fields shape**: Card-level keys have `card:` wrapper. `styles.custom_fields` keys are bare style lists.
3. **grid parity**: Every `grid-template-areas` name exists in both `custom_fields` locations.
4. **Entity on sub-cards**: Every Form A sub-card has its own `'entity'`.
5. **Booleans**: `true`/`false` for Jinja `set` and service data; `True`/`false` or `true`/`false` both OK in `{{ }}`.
6. **Colors**: Zero bare hex/rgb values. All colors use `var(--*)` or declared template variables.
7. **Translations**: All user-visible strings use `ui.get('key', 'err-key')` with the `err-` prefix on fallbacks.
8. **Commas**: Every card output ends with `}},`.
9. **Sync**: `python utils/sync_dashboard_assets.py && python utils/sync_dashboard_assets.py --check`.

---

## 12. JavaScript Template Patterns (`[[[ ]]]`)

Named `button_card_templates` use JavaScript templates delimited by `[[[ ... ]]]`.
These are evaluated at render time by the button-card frontend, not by Jinja.

### 12.1 Escape to True JavaScript Variables

When writing complex conditional logic in `[[[ ]]]` blocks, **do not chain nested
ternary operators**. They become unreadable and impossible to debug. Instead,
declare local variables with `let`:

```javascript
# ❌ WRONG — nested ternaries, impossible to debug
return entity.state === 'overdue' ? 'var(--error-color)'
  : entity.state === 'due' ? 'var(--warning-color)'
  : entity.state === 'claimed' ? '#a957fa'
  : 'var(--primary-text-color)';

# ✅ CORRECT — local variables, debuggable, readable
let state = entity.state;
let claimAccent = variables.pref_claim_accent || '#a957fa';
let dueAccent = variables.pref_due_accent || '#ff9800';
let overdueAccent = variables.pref_overdue_accent || '#ff4444';
if (['overdue', 'missed'].includes(state)) return overdueAccent;
if (state === 'due') return dueAccent;
if (state === 'claimed') return claimAccent;
return 'var(--primary-text-color)';
```

This pattern is used extensively in `templates/shared/button_card_template_chore_row_v1.yaml`
— study that file as the canonical example for state-driven JS styling, icon
selection, and HTML content generation inside button-card templates.

Key rules for JS templates:
- Variables from the Jinja context arrive via the `variables` object (e.g., `variables.pref_claim_accent`).
- Entity state and attributes are on `entity` (e.g., `entity.state`, `entity.attributes.chore_name`).
- HTML content in `custom_fields` values can return HTML strings directly.
- Always provide fallback defaults with `||` for variables that may be undefined.
- Use `typeof` guards before accessing nested properties: `typeof variables.pref_claim_accent === 'string'`.

### 12.2 The "One-Percent" Rule

Never build a complex button-card directly inline in a dashboard view. If a card
uses `custom_fields`, grid positioning, or heavy JS scripting, place **99% of its
code** inside a named `button_card_templates` entry. The inline card reference
should contain only the `entity` and the `template` pointer (the remaining 1%).

```yaml
# ✅ CORRECT — template at root, minimal inline reference
button_card_templates:
  my_complex_card:
    type: custom:button-card
    # ... 99% of the logic here ...
views:
  - cards:
      - type: custom:button-card
        entity: sensor.my_sensor
        template: my_complex_card  # 1% inline

# ❌ WRONG — all logic inline, fragile
views:
  - cards:
      - type: custom:button-card
        entity: sensor.my_sensor
        # 200 lines of styles, custom_fields, JS ...
```

ChoreOps already follows this rule: the chore row templates live in
`templates/shared/button_card_template_chore_row_v1.yaml` and are referenced
by name from every user chore dashboard.

### 12.3 Template Chaining

Button-card supports template inheritance via arrays. Templates are resolved
left-to-right; properties in later templates override earlier ones:

```yaml
button_card_templates:
  base_style:
    styles:
      card:
        - padding: 8px
        - border-radius: 12px
  active_glow:
    styles:
      card:
        - box-shadow: 0 0 8px var(--primary-color)
views:
  - cards:
      - type: custom:button-card
        template:
          - base_style      # applied first
          - active_glow     # overrides / extends
```

Chain from abstract (base styles) to specific (state variant). This eliminates
repetitive CSS grid logic across entity domains.

The UI-Lovelace-Minimalist framework uses this pattern pervasively: every card
template begins with `template: ["ulm_language_variables"]` to inherit
translation support, then chains additional templates for behavior.

### 12.4 The `variables` Contract

Named `button_card_templates` accept configuration through a `variables` block.
This is how parameterized templates receive per-instance data without
duplicating template code:

```yaml
button_card_templates:
  card_light:
    variables:
      ulm_card_light_enable_slider: false
      ulm_card_light_enable_color: false
    # ... template uses variables.ulm_card_light_enable_slider in JS blocks

views:
  - cards:
      - type: custom:button-card
        template: card_light
        entity: light.kitchen
        variables:
          ulm_card_light_enable_slider: true   # overrides default
```

Rules:
- Template defaults go in the `variables` block of the template definition.
- Per-instance overrides go in the `variables` block of the card reference.
- Inside `[[[ ]]]` JS blocks, access them via `variables.ulm_*` or `variables.pref_*`.
- Always guard with `typeof` checks and provide fallback defaults with `||`.
- ChoreOps convention: use `pref_*` prefix for preference variables (e.g., `variables.pref_claim_accent`).

### 12.5 `triggers_update: "all"`

For complex cards with deeply nested `custom_fields`, add this to force a full
re-render whenever any entity state changes:

```yaml
button_card_templates:
  my_card:
    triggers_update: "all"
    # ... template definition
```

Without it, button-card may not re-evaluate `[[[ ]]]` expressions in
`custom_fields` sub-cards when referenced entities change. This is used
extensively in UI-Lovelace-Minimalist for cards with dynamic grid areas.

### 12.6 Dynamic `grid-template-areas` via JavaScript

When the number or layout of `custom_fields` slots depends on runtime state,
build the `grid-template-areas` string dynamically in a `[[[ ]]]` block:

```yaml
styles:
  grid:
    - grid-template-areas: >
        [[[
          var areas = [];
          areas.push("item1 item1");
          areas.push(". .");
          areas.push("item2 item2");
          if (variables.show_extra) areas.push("item3 item3");
          return '"' + areas.join('" "') + '"';
        ]]]
```

Rules:
- The JS expression must return a double-quoted string in the exact format
  button-card expects (e.g., `"area1 area2" "area3 area4"`).
- Use `>` (folded block scalar) or `|` (literal block scalar) in YAML for
  multi-line JS, not inline single-line.
- Treat the `[[[ ]]]` return value as a raw CSS grid-area string — no
  additional YAML quoting needed inside the return value.
- This pattern is used in `card_scenes_welcome.yaml` and
  `custom_card_neekster_update.yaml` in UI-Lovelace-Minimalist.

### 12.7 Property Ordering Convention

For readability and consistency in `button_card_templates` definitions, follow
this property order (derived from UI-Lovelace-Minimalist's documented convention):

1. `template` — inherited templates
2. `variables` — default variable values
3. `tap_action` / `hold_action` / `double_tap_action`
4. `triggers_update`
5. `show_icon` / `show_label` / `show_name` / `show_state` / `show_units`
6. `icon` / `label` / `name` / `state` / `entity`
7. `styles` — ordered as: `icon`, `label`, `name`, `state`, `img_cell`, `grid`, `card`
8. `custom_fields` — embedded sub-cards and slot styles

This is optional but recommended; it makes template comparison and review
significantly easier.

---

## 13. Debugging Button-Card Rendering Failures

When a complex button-card blanks out or throws errors without useful log output:

1. **Browser DevTools Console**: Open your browser's Developer Tools (`F12`),
   go to the **Console** tab. Uncaught syntax errors or type errors from
   `button-card.js` will point to the exact JS line failing inside a `[[[ ]]]`
   block. Home Assistant's `home-assistant.log` will **not** show these errors.

2. **Isolate the template**: Temporarily move the card to a standalone view
   with only that card. This eliminates interference from other cards and
   auto-entities dynamic rendering.

3. **Check grid areas**: If a `custom_fields` sub-card isn't appearing, verify
   the field name exists in `grid-template-areas` AND in both `custom_fields`
   locations (Form A and Form B).

---

## 14. External Reference Architectures

For advanced button-card layout study beyond the ChoreOps codebase:

| Resource | What to study |
| -------- | ------------- |
| **UI-Lovelace-Minimalist** (`UI-Lovelace-Minimalist/UI` on GitHub) | Community framework built entirely on nested `custom:button-card` templates. Study these specific files for patterns: `custom_components/ui_lovelace_minimalist/lovelace/ulm_templates/card_templates/` (card definitions with `variables`, `triggers_update`, template chaining), `popup_templates/popups/` (dynamic JS grid areas), `internal_templates/` (icon_info_alert with `custom_fields.notification`). The `ulm_language_variables` template chain and `ulm_translation_engine` demonstrate i18n via template inheritance. |
| **Mattias Persson's hass-config** (`matt8707/hass-config` on GitHub) | ⚠️ **Archived** (replaced by ha-fusion). Still valuable for studying: centralized `button_card_templates/` folder organization, `layout-card` + `button-card` structural wrapping for responsive layouts, and browser_mod popup integration patterns. His `INSTALL.md` lists the exact dependency stack (button-card, card-mod, layout-card, swipe-card). |
| **Button-card docs** | `https://custom-cards.github.io/button-card/` — canonical reference for all template features, `[[[ ]]]` JavaScript variables, `triggers_update`, `variables` block, and live-editor workflow. |
| **Button-card repository** | `https://github.com/custom-cards/button-card` — source code, issues, and release notes. |
| **Auto-entities docs** | `https://github.com/thomasloven/lovelace-auto-entities` — filter syntax, `card_param`, and template variable injection (`config.entity`). |

---

## 15. Layer Boundary Reconciliation

The ChoreOps dashboard system has **four distinct rendering/composition layers**.
The button-card rules above span multiple layers. This section maps every concept
to its correct layer and disambiguates overloaded terminology.

### 15.1 The Four Layers

| # | Layer | When | Delimiters | Where documented |
|---|-------|------|-----------|-----------------|
| 1 | **Build-time Jinja** | `render_dashboard_template()` in Python | `<< >>`, `<% %>`, `<#-- --#>` | Original § "Jinja2 Delimiter System" + New § 1 |
| 2 | **HA runtime Jinja** | Home Assistant Lovelace render | `{{ }}`, `{% %}`, `{# #}` | Original § "Runtime (Home Assistant Jinja2)" + New § 1 |
| 3 | **Button-card JS** | Button-card frontend module | `[[[ ]]]` | New § 12.1 |
| 4 | **YAML structure** | Parsed at all stages | Standard YAML | Original § "Output Format", New § 6, § 9 |

### 15.2 Disambiguated Terms

The word **"variables"** has three meanings at different layers:

| Term | Layer | Meaning | Example |
|------|-------|---------|---------|
| Build-time context | Layer 1 | Python dict passed to `render_dashboard_template()`. Accesses via `<< user.name >>`. | `<< user.name >>`, `<< integration.entry_id >>` |
| HA Jinja `{% set %}` | Layer 2 | Home Assistant template variables set with `{%- set name = value -%}`. | `{%- set has_after_datetime = after_datetime != '' -%}` |
| Button-card `variables:` block | Layer 3 | Named template parameter defaults, accessed in `[[[ ]]]` as `variables.pref_*`. | `variables.pref_claim_accent`, `variables.ulm_card_light_enable_slider` |

These are **completely independent mechanisms**. A build-time `<< user.name >>`
is injected into the template string before HA ever sees it. A button-card
`variables.pref_claim_accent` is evaluated at render time in the browser. An
HA Jinja `{% set %}` exists in between. They do not share a namespace.

The word **"template"** has four meanings:

| Term | Layer | Meaning | Example |
|------|-------|---------|---------|
| Template file | All | A `.yaml` source file in `templates/`. | `admin-shared-v1.yaml` |
| `<< template_shared.* >>` | Layer 1 | Build-time shared fragment include. Composed before HA sees the file. | `<< template_shared.button_card_template_chore_row_v1 >>` |
| HA `filter.template` | Layer 2 | Auto-entities inner Jinja template string. Evaluated by HA at render time. | `filter: { template: \|- }` |
| Button-card `template:` | Layer 3 | Named button-card template reference or array for chaining. | `template: chore_row_v1`, `template: [base, variant]` |

All four are valid simultaneously in the same file.

### 15.3 Where New Sections Augment (Not Override) Original Rules

| Original rule | New section | Relationship |
|--------------|-------------|-------------|
| § "Output Format (CRITICAL)" — templates output full dashboard documents | § 12.2 "One-Percent Rule" | Augments: specifies WHERE within that document button-card logic should live (in `button_card_templates:` block, not inline) |
| § "YAML anchors" — anchors for static reuse, not a substitute for `<< template_shared.* >>` | § 12.3 "Template Chaining" | Complements: button-card's `template: [...]` is a Layer 3 mechanism, completely separate from YAML anchors (Layer 4) and shared fragments (Layer 1) |
| § "Color authoring contract" — use theme variables, declare non-theme accents as named variables | § 6.3 "Color values" | Reiterates and extends: same rule, with explicit `var(--*)` syntax examples for button-card context |
| § "Comment Syntax Rules" — build-time `<#-- -->` rules | § 1 "Two-Layer Jinja" — HA `{# #}` comments | Adds Layer 2 comment rules; does not modify Layer 1 rules |
| § "Common Pitfalls" table — 5 items | § 10 "Common Traps" table — 12 items | Adds button-card-specific traps; original pitfalls remain valid |
| § "Quick Reference Card" — two-column build-time/HA runtime map | § 15.1 "Four Layers" table — four-column map | Expands the two-layer model to include Layers 3 and 4; original reference card remains correct for its scope |
| § "Shared-template contract" — `<< template_shared.* >>` | § 9 "Named button_card_templates" | Layers 1 vs 3: shared fragments are composed at build-time; named templates are evaluated by button-card at render time |

### 15.4 Rules That Apply Across All Layers

1. **Never nest Layer 1 delimiters inside Layer 2 strings.** `<< >>` inside
   `filter.template: |-` will not be processed.

2. **Never nest Layer 2 block tags inside Layer 2 expression tags.** `{% if %}`
   inside `{{ }}` produces `unexpected '%'`.

3. **Layer 3 `[[[ ]]]` and Layer 2 `{{ }}` coexist safely.** They use different
   delimiters. Button-card JS expressions can reference HA state objects
   (`entity`, `states`, `hass`).

4. **Layer 4 YAML structure is authoritative for validity at all layers.**
   Malformed YAML fails before any Jinja or JS evaluation.

5. **The `button_card_templates:` root key (Layer 4) is the single home for
   named button-card definitions.** Shared fragments (`<< template_shared.* >>`)
   may inject into this block. Template chaining (`template: [...]`) resolves
   within this block at Layer 3. YAML anchors may reference within this block.
   These composition mechanisms do not conflict — they operate at different
   layers and stages.

---
