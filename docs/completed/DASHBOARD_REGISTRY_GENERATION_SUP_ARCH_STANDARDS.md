# Dashboard registry architecture standards (supporting)

## Purpose

This document defines architecture standards and decision gates for the ChoreOps dashboard registry ecosystem. It intentionally avoids implementation details so maintainers can ratify the model before coding.

## 0) Ratification decision table

| ID  | Decision                                  | Options                                                                                                  | Recommended                                                                                                                                             | Owner                             | Due date     | Status   |
| --- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | ------------ | -------- |
| D1  | Canonical template identity format        | Kebab-case string only, UUID, slug-only                                                                  | Immutable kebab-case `template_id` only; derive family key by stripping trailing `-v<major>`                                                            | Architecture                      | 0.5.0-beta.5 | Accepted |
| D2  | Manifest schema versioning policy         | Strict semver, major-only, ad-hoc                                                                        | Schema version with backward-compatible minor evolution and explicit breaking major bumps                                                               | Architecture                      | 0.5.0-beta.5 | Accepted |
| D3  | Local/remote merge precedence             | Local wins, remote wins, per-field merge                                                                 | Local baseline + remote override by `template_id` for valid records only                                                                                | Integration                       | 0.5.0-beta.5 | Accepted |
| D4  | Dependency catalog source of truth        | Registry-managed, integration-managed, mixed                                                             | Integration-managed canonical dependency keys with mirrored docs in registry repo                                                                       | Integration + DX                  | 0.5.0-beta.5 | Accepted |
| D5  | Schema-level approval governance          | Any maintainer, codeowner-only, architecture sign-off                                                    | Architecture-owner sign-off required for schema changes                                                                                                 | Maintainers                       | 0.5.0-beta.5 | Accepted |
| D6  | Deprecation window policy                 | None, fixed window, case-by-case                                                                         | Fixed minimum window with replacement guidance before archive state                                                                                     | Maintainers                       | 0.5.0-beta.5 | Accepted |
| D7  | Custom card distribution model            | Store cards in dashboard repo, separate card repos, monorepo bundle                                      | Separate frontend card repositories (dashboard repo remains template/manifest only)                                                                     | Architecture + DX                 | 0.5.0-beta.5 | Accepted |
| D8  | Supported template substitution fields    | Open/free-form, curated whitelist, no substitution                                                       | Curated whitelist contract (explicit supported fields only)                                                                                             | Architecture + Integration        | 0.5.0-beta.5 | Accepted |
| D9  | Dashboard localization source model       | Integration-local only, registry-remote only, hybrid                                                     | Hybrid: integration-local baseline + optional remote updates                                                                                            | Architecture + Integration + L10n | 0.5.0-beta.5 | Accepted |
| D10 | Template text localization model          | Literal text in YAML, inline per-template dictionaries, key-based localization contract                  | Key-based localization contract resolved via translation sensor payloads                                                                                | Architecture + DX                 | 0.5.0-beta.5 | Accepted |
| D11 | Dashboard helper lookup contract          | Name-based lookup, attribute-scoped dynamic lookup, user-id+entry-id filter, direct helper EID injection | Attribute-scoped dynamic lookup only (`purpose` + `integration.entry_id` + `user.user_id`)                                                              | Architecture + Integration        | 0.5.0-beta.5 | Accepted |
| D12 | Helper lookup optimization strategy       | Multi-attribute filter only, composite lookup key, hybrid with key as preferred                          | Use composite `dashboard_lookup_key` as primary filter (`<entry_id>:<user_id>`), keep explicit attribute filters as contract-level integrity checks     | Architecture + Integration        | 0.5.0-beta.5 | Accepted |
| D13 | Dashboard template error-handling UX      | Strict hard-fail, warning-card pattern, mixed by card type                                               | Accept warning-card pattern with actionable user guidance and minimal validation ladder (config -> lookup -> helper contract); avoid hard-fail UX in v1 | Architecture + Integration + UX   | 0.5.0-beta.5 | Accepted |
| D14 | Template preference customization model   | Backend runtime controls, template-only pref blocks, companion docs, hybrid phased model                 | v1: companion preference docs per template (no backend runtime pref engine); revisit controlled runtime presets in later phase                          | Architecture + Integration + DX   | 0.5.0-beta.5 | Accepted |
| D15 | Template composition storage model        | Full-dashboard files only, card-level registry units, hybrid authoring with dashboard-level release unit | v1: keep dashboard template as canonical release/runtime unit; allow optional card-fragment authoring assets with explicit composition order metadata   | Architecture + Integration + DX   | 0.5.0-beta.5 | Accepted |
| D16 | Registry release/channel versioning model | Tag-only releases, gitflow branches, hybrid main+release-branch policy                                   | SemVer tags for stable/beta, dev snapshots from default branch, short-lived release branches only when needed                                           | Architecture + Maintainers + DX   | 0.5.0-beta.5 | Accepted |

## 1) Architecture principles (non-negotiable)

1. **Contract-first design**
   - Runtime behavior is driven by an explicit manifest contract, not implied file naming.
   - Every user-visible template option must map to a stable manifest identity.

2. **Deterministic runtime behavior**
   - Given the same local+remote inputs, resolution must always produce the same selected template.
   - All fallback rules are explicit and testable.

3. **Offline-safe baseline**
   - Core templates and a valid manifest are always vendored in integration releases.
   - Remote fetch failure must not block dashboard generation.

4. **Low cognitive load**
   - Naming, taxonomy, and metadata should be obvious to maintainers and contributors.
   - Avoid redundant fields that create ambiguity.

5. **Scale through governance**
   - Community contributions must pass policy checks for naming, metadata, and dependencies.
   - Schema changes require stricter approval than template-only changes.

6. **Observable behavior**
   - Runtime decisions should be explainable via structured logs and diagnostics.
   - Users should be informed when dependency requirements block template usage.

## 2) Explicit non-goals (for this initiative)

- Defining a new visual design system for dashboards.
- Rewriting Home Assistant Lovelace internals.
- Supporting arbitrary remote code execution or dynamic scripts.
- Building a full template marketplace UI in this phase.

## 3) Manifest contract standards (v1 target)

## Required identity fields

- `template_id` (immutable canonical key)
- `display_name`
- `lifecycle_state` (`active`/`deprecated`/`archived`)

## Required compatibility fields

- `min_integration_version`
- `max_integration_version` (optional if open-ended)
- `schema_version` (manifest schema version)

## Required asset fields

- `source.type` (`vendored`/`remote`)
- `source.path` (for vendored)
- `source.ref` (for remote ref when applicable)

## Required dependency fields

- `dependencies.required[]`
- `dependencies.recommended[]`
- Dependency entries should be machine-readable with stable IDs and optional human labels.

### Dependency contract behavior (frozen)

- `dependencies.required[]`
  - Missing required dependency is a hard block for template selection/generation.
  - Runtime must return a deterministic, user-visible blocking reason.
- `dependencies.recommended[]`
  - Missing recommended dependency is non-blocking.
  - Runtime should emit a warning and allow continue behavior.
- Dependency IDs must be stable, machine-readable keys so runtime checks and CI
  validations are deterministic across releases.

### Dependency identifier standard for future ChoreOps-specific cards

- Frontend card dependencies must reference separate card repositories (not the
  dashboard registry repository).
- Dependency ID format is namespace-scoped and stable:
  - `ha-card:<package_name>` for Home Assistant card package identity
  - optional source metadata can include canonical repository pointer
    (for example `ccpk1/choreops-card-<name>`).
- Dependency IDs are immutable once published for a template major line; any
  replacement uses explicit migration guidance via lifecycle/deprecation notes.

## Required metadata fields

- `category` (e.g., `family`, `admin`, `minimal`)
- `audience` (e.g., `user`, `approver`, `mixed`)
- `maintainer` (or ownership pointer)

## Optional manifest fields (v1)

- `description` (short user-facing summary)
- `tags[]` (discovery/filter metadata)
- `notes` (maintainer-facing release/context notes)
- `replaces[]` (deprecated template migration hints)
- `preferences` (template preference metadata/doc pointers)
- `translations` (translation asset metadata)

`preferences` metadata purpose:

- provide user-facing documentation pointers for supported `pref_*` knobs
- remain informational only; never runtime state or runtime truth

## Manifest validation rules (v1)

- Reject records with missing or empty required fields.
- Reject duplicate `template_id` values in a single manifest.
- Validate `template_id` against canonical format `<audience>-<intent>-v<major>`.
- Require `schema_version` compatibility with loader-supported major version.
- Validate `lifecycle_state` against allowed enum values.
- Validate dependency IDs for machine-readable format and uniqueness per list.
- Reject persisted manifest `slug` fields; family key must be derived from `template_id`.
- Reject persisted per-template `template_version` fields.

## 4) Naming and organization standards

- Template file naming should be deterministic and variant-safe.
- `template_id` is immutable; display names can evolve.
- Variant naming must use explicit suffix conventions (e.g., `-compact`, `-minimal`) rather than overloaded labels.
- Deprecated templates must keep discoverable aliases until retirement period ends.

### Frozen naming standard (v1)

- Canonical `template_id` format: `<audience>-<intent>-v<major>` (kebab-case, immutable).
- Canonical filename format: `templates/<template_id>.yaml`.
- Template family key is derived by stripping trailing `-v<major>` from `template_id`.
- `display_name` and `description` are curated, user-facing labels and may evolve.

Current v1 canonical IDs:

- `user-gamification-v1`
- `user-minimal-v1`
- `admin-shared-v1`
- `admin-peruser-v1`

### D1 clarification: who names what

#### Field ownership model

- `template_id` (maintainer-owned, immutable):
  - Canonical identity key used for merge, overrides, and saved selections.
  - Never shown as primary end-user label.
- `filename` (maintainer-owned, operational):
  - Physical YAML path in repo for storage and tooling.
  - Can be deterministic from `template_id` and variant, but not user-facing.
- `display_name` (curated user-facing):
  - Main label shown in options flow/template picker.
  - Can evolve for clarity without breaking saved references.
- `description` (curated user-facing):
  - Short explanation in picker/details (for example: who the template is for and card requirements).
- `derived_family_key` (computed, not stored):
  - Derived from `template_id` by removing trailing `-v<major>` for docs/grouping/migration hints.

#### Practical mapping example

```json
{
  "template_id": "user-daily-focus-v1",
  "display_name": "Daily focus (User)",
  "description": "Single-user dashboard focused on today's chores and progress.",
  "source": {
    "type": "vendored",
    "path": "templates/user-daily-focus-v1.yaml"
  }
}
```

In this example:

- Maintainer controls `template_id` and file path.
- User sees `display_name` and `description`.
- If `display_name` changes later (for clearer wording), saved selections still resolve by `template_id`.
- Docs/grouping can use derived family key `user-daily-focus` from `template_id`.

#### Shared/admin versus per-user naming

- Audience is represented by metadata (`audience`: `user`, `admin`, `mixed`), not by filename alone.
- Admin/shared templates can use the same identity model (`template_id` + display metadata) without special-case naming rules.
- `approver` is a valid audience value for templates targeting approver workflows.

### Admin mode standards (shared selector + per-user tab)

To avoid ambiguity in generator behavior and template authoring, admin views are standardized into two explicit runtime modes.

#### Mode A: shared admin view with user selector

- One admin tab is generated.
- The tab includes a selector control for switching the target user context.
- Jinja/runtime lookup must resolve helper pointers from selected user identity using the same D11/D12 contract (`purpose` + `dashboard_lookup_key`).
- Selector state drives downstream cards; it must not bypass helper lookup contract checks.

#### Mode B: per-user admin tab

- One admin tab is generated per selected user.
- Each tab is fixed to that user context and does not require selector-driven context switching.
- Jinja/runtime lookup still uses D11/D12 identity-scoped helper resolution; the user identity comes from injected template context for that tab.

#### Admin Jinja alignment requirement (v1)

- Admin templates must use a canonical identity-first lookup pattern equivalent to the D11/D12 helper lookup standards.
- Shared-selector and per-user-tab templates may differ in where `user.user_id` is sourced (selector state vs injected tab context), but both must:
  - compute `lookup_key = integration.entry_id + ':' + user.user_id`,
  - resolve dashboard helper via `dashboard_lookup_key` + `purpose`,
  - apply D13 validation ladder (`E01`/`E02`/`E03`) before card rendering.

#### Required manifest/admin metadata clarity

- Admin-capable templates must explicitly describe mode intent in metadata (for example via `audience` + description text and/or explicit mode field in future schema revisions).
- Variant naming should remain explicit and deterministic (for example suffix conventions such as `-admin-shared` and `-admin-per-user`).

### Manifest topology (authoritative source)

- Use **one canonical registry manifest** that contains records for all templates.
- Each submitted template adds/updates a record in that manifest plus its YAML asset file.
- Per-template manifest files are out of scope for v1 to avoid drift and parsing complexity.
- If contributors submit template YAML without manifest updates, CI/review should fail until canonical manifest entries are added.

#### Practical submission model

- Contributor PR includes:
  - template YAML file under `templates/`
  - one new/updated record in the single canonical `dashboard_registry.json`
- Maintainers review and merge both together so registry metadata and asset content remain synchronized.

## 5) Runtime resolution model standards

1. Local vendored manifest loads first.
2. Remote manifest fetch is attempted with timeout budget.
3. Merge is by `template_id` with remote override on valid records only.
4. Invalid remote records are ignored and logged; local baseline remains authoritative.
5. Selection engine filters by lifecycle state, compatibility, and dependency policy.
6. Generator resolves to one explicit source asset and records why that source won.

## 5.5) Runtime resolution contract (phase 3 frozen)

### 5.5.1) Source precedence and merge semantics

- Local vendored manifest is always loaded first and acts as offline-safe baseline.
- Remote manifest fetch is optional and bounded by timeout budget; remote unavailability must never block generation.
- Remote manifest is accepted only when manifest-level schema major is supported.
- Merge key is `template_id` only.
- Merge behavior:
  - begin with local baseline map keyed by `template_id`,
  - apply remote override only for valid remote records,
  - include valid remote-only records as additional candidates.
- Invalid remote records (missing required fields, unsupported schema major, invalid dependency contract) are ignored and logged.
- Deterministic ordering:
  - preserve local manifest order for local template IDs,
  - append remote-only template IDs in stable lexicographic `template_id` order.

### 5.5.2) Template selection algorithm contract

- Inputs:
  - requested `template_id` (optional),
  - integration version,
  - lifecycle policy,
  - dependency availability state.
- Filter pipeline (required order):
  1. record validity,
  2. lifecycle (`active`/`deprecated` selectable, `archived` excluded from new selection),
  3. integration compatibility (`min_integration_version`/`max_integration_version`),
  4. dependency checks (`required` hard-block, `recommended` warning).
- Selection precedence:
  1. requested `template_id` if it passes all required filters,
  2. configured default template if it passes all required filters,
  3. first compatible `active` template in deterministic order,
  4. first compatible `deprecated` template in deterministic order.
- If no candidate passes required filters, generation returns a deterministic blocking result with user-actionable reason.

### 5.5.3) Caching and refresh behavior

- Local vendored manifest has no TTL and is always immediately available.
- Remote manifest cache:
  - in-memory TTL cache,
  - default TTL: 30 minutes,
  - stale entries may be served while background refresh attempts run.
- Refresh triggers:
  - initial load (best effort),
  - explicit manual refresh action,
  - TTL expiry.
- Remote fetch timeout is bounded and non-blocking for generation path.
- On fetch/rate-limit/parse failure, runtime uses last known valid remote cache if present; otherwise local baseline only.

### 5.5.4) Failure-mode matrix

| Failure case                         | Runtime behavior                                 | User impact                                  | Logging/diagnostics                        |
| ------------------------------------ | ------------------------------------------------ | -------------------------------------------- | ------------------------------------------ |
| Remote manifest unavailable/timeout  | Use local baseline only                          | Non-blocking; generation continues           | Log fetch failure reason and fallback path |
| Remote manifest malformed            | Ignore remote payload                            | Non-blocking; generation continues           | Log parse/validation failure               |
| Unsupported schema major             | Ignore remote payload                            | Non-blocking; generation continues           | Log schema incompatibility                 |
| Invalid remote template record       | Ignore only invalid records                      | Non-blocking unless all candidates invalid   | Log record-level validation failures       |
| Selected template missing asset path | Block generation for selected template           | Blocking with remediation message            | Log missing asset and template ID          |
| Required dependency missing          | Block selection/generation for affected template | Blocking with actionable dependency guidance | Log missing dependency IDs                 |
| Recommended dependency missing       | Allow selection/generation                       | Non-blocking warning                         | Log missing recommended dependency IDs     |

### 5.5.5) User-facing dependency UX rules

- `dependencies.required[]`:
  - missing required dependency blocks template selection/generation,
  - user message must name missing dependency IDs and required installation action,
  - no silent fallback to incompatible template without explicit selection resolution path.
- `dependencies.recommended[]`:
  - missing recommended dependency never blocks selection/generation,
  - user sees warning with impact summary and optional install guidance.
- Runtime warning/error copy may evolve, but required-vs-recommended behavior is contract-locked.

## 5.2) Dashboard helper lookup contract (critical)

### Current pattern observed in templates

- Templates currently discover `dashboard_helper` via `integration_entities('choreops')` and filter by:
  - `attributes.purpose == purpose_dashboard_helper`
  - `attributes.user_name == name`
- This helper is the root pointer for:
  - `core_sensors.*` entity IDs,
  - `dashboard_helpers.translation_sensor_eid`,
  - and other runtime dashboard dependencies.

### Risk in multi-instance deployments

- Name-based lookup is vulnerable when two ChoreOps instances contain users with the same display name.
- In that scenario, `| first` can resolve the wrong helper, producing cross-instance pointers.

### Option comparison

1. **Name-based lookup (current style)**
   - Pros: simple and readable in template.
   - Cons: not deterministic across multi-instance + duplicate names.

2. **Attribute-scoped dynamic lookup (proposed primary dynamic model)**
   - Pattern: discover helper dynamically from `integration_entities('choreops')`, but filter by:
     - `attributes.purpose == purpose_dashboard_helper`
     - `attributes.integration_entry_id == integration.entry_id`
     - `attributes.user_id == user.user_id`
   - Pros:
     - keeps rename resilience (entity_id/display-name changes do not break lookup),
     - remains dynamic (no hardcoded/helper-specific EID in template),
     - deterministic across multi-instance when attributes are present.
   - Cons:
     - requires helper attributes to expose `integration_entry_id` and `user_id`,
     - still performs entity scan/filter in template runtime.

3. **Filter lookup by `integration.entry_id` + `user.user_id` via context-only criteria**
   - Pros: deterministic and identity-safe.
   - Cons: requires these attributes/values to be present in template context and/or helper attributes.

4. **Direct helper EID injection**
   - Pros: deterministic, minimal template logic, avoids expensive entity scanning.
   - Cons: adds stronger coupling between generator contract and template payload; requires reliable regeneration when pointer context changes.

### Recommended standard

- Primary: attribute-scoped dynamic lookup using `purpose + integration.entry_id + user.user_id`.
- No fallback lookup modes are part of the contract.
- Name-based lookup and legacy compatibility paths are explicitly out of scope.

### Required helper attributes for D11 model

- `purpose` (existing)
- `integration_entry_id` (new explicit attribute for instance scoping)
- `user_id` (new explicit attribute for identity scoping)
- `user_name` (existing display-oriented attribute; not sufficient as sole identity key)

### Performance and robustness recommendations (D11/D12)

#### Optimization goal

- Keep dynamic lookup behavior while reducing expensive per-card filter passes.

#### Preferred optimization

- Add helper attribute `dashboard_lookup_key` with format `<integration_entry_id>:<user_id>`.
- Use this key as the primary equality filter to reduce multiple `selectattr` passes.
- Keep `purpose` filter in place to constrain entity intent.

#### Canonical lookup snippet (authoring standard)

```jinja
{%- set user_name = '<< user.name >>' -%}
{%- set user_id = '<< user.user_id >>' -%}
{%- set entry_id = '<< integration.entry_id >>' -%}
{%- set lookup_key = entry_id ~ ':' ~ user_id -%}

{%- set dashboard_helper = integration_entities('choreops')
   | select('search', '^sensor\\.')
   | list
   | expand
   | selectattr('attributes.purpose', 'eq', 'purpose_dashboard_helper')
   | selectattr('attributes.dashboard_lookup_key', 'eq', lookup_key)
   | map(attribute='entity_id')
   | first
   | default("err-dashboard_helper_missing", true) -%}
```

#### Filter-order rationale

1. `integration_entities('choreops')` bounds search to integration entities.
2. Domain pre-filter (`^sensor\\.`) trims payload before `expand` fan-out use.
3. `purpose` check removes non-helper sensors quickly.
4. Single-key equality (`dashboard_lookup_key`) resolves to target helper efficiently.

#### Integrity checks

- Runtime must enforce uniqueness of helper by lookup key (`<entry_id>:<user_id>`).
- Runtime must detect missing identity inputs (`entry_id`, `user_id`) and missing helper resolution.

#### Error handling scope (ratified)

- D13 is accepted: use card-level warning rendering with actionable user guidance.
- For missing configuration or unresolved helper lookups, render a markdown warning card that explains the issue and how to fix it.
- Do not hard-fail dashboard rendering in v1 for these configuration errors.
- Lookup correctness and required attributes remain contract-level requirements; UX wording can evolve while preserving this behavior.

#### D13 minimal contract for enhanced helper lookups

Keep the current strengths (clear user message + fix guidance) and add only lightweight checks needed for the new lookup model.

Validation ladder (required order):

1. **Configuration preflight**

- Validate required template inputs exist (`user.name`, `user.user_id`, `integration.entry_id`).
- If missing, render warning card with actionable fix guidance and stop card rendering.

2. **Helper resolution check**

- Resolve helper using D11/D12 contract (`purpose` + `dashboard_lookup_key`).
- If helper is unresolved/`unknown`/`unavailable`, render warning card with instance-safe troubleshooting guidance.

3. **Helper contract check**

- Validate required helper payload pointers are present before downstream lookups:
  - `core_sensors`
  - `dashboard_helpers.translation_sensor_eid` (or equivalent agreed translation pointer)
- If required pointers are missing, render warning card describing incomplete helper payload.

Implementation constraints (anti-overengineering):

- Keep rendering mechanism as a single markdown warning-card pattern.
- Do not add a separate runtime error framework, modal system, or cross-card exception bus for v1.
- Standardize only a small error taxonomy for diagnostics/review consistency:
  - `D13-E01`: missing required template inputs
  - `D13-E02`: helper not resolved
  - `D13-E03`: helper payload missing required pointers

Optional resilience behavior:

- If translation pointer is unavailable but primary helper resolves, cards may fall back to default/English labels where feasible.
- This fallback must not mask a hard helper-resolution failure (`D13-E02`).

#### Canonical D13 Jinja block (locked for v1 authoring)

Use this exact logic pattern in templates that depend on dashboard helper pointers.

```jinja
{%- set user_name = '<< user.name >>' -%}
{%- set user_id = '<< user.user_id >>' -%}
{%- set entry_id = '<< integration.entry_id >>' -%}
{%- set lookup_key = entry_id ~ ':' ~ user_id -%}

{%- set missing_input =
    (user_name | trim == '')
    or (user_id | trim == '')
    or (entry_id | trim == '') -%}

{%- if missing_input -%}
  {{
    {
      'type': 'markdown',
      'content': "⚠️ **Dashboard Not Configured**\n\nMissing required dashboard inputs (`user.name`, `user.user_id`, or `integration.entry_id`).\n\n**Fix:** Rebuild this dashboard from ChoreOps dashboard generation so required identity fields are injected."
    }
  }},
  {%- set skip_render = true -%}
{%- else -%}
  {%- set dashboard_helper = integration_entities('choreops')
      | select('search', '^sensor\\.')
      | list
      | expand
      | selectattr('attributes.purpose', 'eq', 'purpose_dashboard_helper')
      | selectattr('attributes.dashboard_lookup_key', 'eq', lookup_key)
      | map(attribute='entity_id')
      | first
      | default('err-dashboard_helper_missing', true) -%}

  {%- if states(dashboard_helper) in ['unknown', 'unavailable'] -%}
    {{
      {
        'type': 'markdown',
        'content': "⚠️ **Dashboard Configuration Error**\n\nCannot resolve dashboard helper for lookup key `" ~ lookup_key ~ "`.\n\n**Fix:** Confirm the ChoreOps integration entry and user identity match this dashboard, then regenerate if needed."
      }
    }},
    {%- set skip_render = true -%}
  {%- else -%}
    {%- set core_sensors = state_attr(dashboard_helper, 'core_sensors') or {} -%}
    {%- set helper_pointers = state_attr(dashboard_helper, 'dashboard_helpers') or {} -%}
    {%- set translation_sensor = helper_pointers.get('translation_sensor_eid') -%}

    {%- if (core_sensors | count == 0) or (translation_sensor | default('', true) | trim == '') -%}
      {{
        {
          'type': 'markdown',
          'content': "⚠️ **Dashboard Helper Incomplete**\n\nDashboard helper `" ~ dashboard_helper ~ "` is missing required pointers (`core_sensors` or `translation_sensor_eid`).\n\n**Fix:** Reload/regenerate ChoreOps dashboard helpers for this integration entry."
        }
      }},
      {%- set skip_render = true -%}
    {%- else -%}
      {%- set skip_render = false -%}
    {%- endif -%}
  {%- endif -%}
{%- endif -%}
```

Notes:

- Warning card copy can be localized/wordsmith-refined, but the validation order and stop-render behavior must remain consistent.
- Keep this as a card-local pattern; do not introduce a separate runtime error framework for v1.

#### Why this is stronger than name-only

- Preserves rename resilience (entity IDs and display names can change).
- Eliminates duplicate-name collisions across multi-instance setups.
- Reduces per-template lookup overhead versus chaining many attribute filters.

### Practical examples

#### Example A: duplicate user names across instances

- Instance A has user display name `Alex`.
- Instance B also has user display name `Alex`.
- Name-based `| first` may bind to wrong instance helper.
- Attribute-scoped dynamic lookup (`entry_id` + `user_id`) or direct `dashboard.helper_eid` binds correctly every time.

#### Example B: user renamed from `Max` to `Maxwell`

- Name-based lookup can break until templates/variables align.
- Attribute-scoped lookup with `user_id` remains stable because identity did not change.

#### Example C: localization and helper chain

- Wrong helper selection means wrong `translation_sensor_eid`, which can surface wrong language strings.
- Instance-safe helper selection keeps translation pointer chain correct.

## 5.1) Template substitution contract standards

### Policy

- Substitution fields are explicitly whitelisted by contract; free-form variable injection is not supported.
- Templates must remain valid and useful even when optional substitution fields are unavailable.
- User-facing substitutions should prefer stable identifiers in runtime logic and display labels only for presentation.

### v1 supported substitution fields (proposed)

- `user.name` (display name, example: user name in view title)
- `user.slug` (URL-safe segment)
- `user.user_id` (stable HA user linkage when available)
- `dashboard.title` (selected dashboard title)
- `dashboard.url_path` (resolved URL path)
- `integration.entry_id` (config entry id for exact instance scoping)
- `integration.entry_title` (config entry title/name for display and scoping hints)
- `integration.instance_id` (config-entry scoped identifier)
- `template.id` (canonical selected template identity)

### Multi-instance scoping standard

- Templates must be instance-safe in multi-instance deployments.
- Template runtime lookup patterns should prioritize `integration.entry_id` (or derived scoped helpers) over name-only matching.
- `integration.entry_title` is display-friendly and may be used as a secondary hint, but it is not a primary unique key.

### Backward compatibility note

- Existing backend/internal `assignee.*` references may continue during transition, but user-facing template contract keys standardize on `user.*`.
- Any legacy `assignee.*` contract aliases must be documented as transitional and removed in a planned deprecation window.

### Explicit exclusions for v1

- No direct arbitrary entity-id injection from user input.
- No free-form expression evaluation through substitution values.
- No substitution that requires secrets or privileged backend-only values.

### Future expansion rule

- New substitution fields require:
  - schema update,
  - compatibility statement,
  - test coverage,
  - ratification update in the decision table (D8).

## 5.3) Template preference customization strategy (`pref_*`)

### Problem statement

- Current templates include useful `pref_*` knobs (sorting, grouping, labels, columns).
- Today, users must edit YAML after generation to use non-default values.
- On dashboard rebuild, manual edits can be overwritten.

### Option comparison

1. **Backend/runtime preference engine**
   - Pros: best UX, no YAML editing required.
   - Cons: high implementation and maintenance complexity; large surface area for per-template custom logic.

2. **Template-only pref blocks (current)**
   - Pros: simple and flexible for template authors.
   - Cons: discoverability is poor; many users never find or understand preferences.

3. **Companion preference docs per template (recommended for v1)**
   - Pros: low complexity, high clarity, preserves backend simplicity.
   - Cons: still manual YAML changes for advanced customization.

4. **Hybrid phased model**
   - v1: companion docs + clear rebuild warnings.
   - v2+: optional small set of standardized runtime presets only (not arbitrary per-template runtime parameters).

### Recommended v1 model

- Do not build a backend runtime preference engine for 0.5.0-beta.5.
- Require each template to publish companion preference guidance (README/metadata block) that includes:
  - list of supported `pref_*` keys,
  - default values,
  - allowed values/ranges,
  - practical examples,
  - rebuild overwrite behavior note.

### Suggested manifest metadata (for discoverability)

- `preferences_doc_path`: link/path to template preference instructions.
- `supports_runtime_preferences`: `false` for v1.
- `preference_groups`: optional high-level tags (e.g., `sorting`, `grouping`, `layout`).

### Practical example

- `dashboard_minimal` chore card supports:
  - `pref_sort_within_groups`
  - `pref_use_label_grouping`
  - `pref_column_count`
- Companion docs explain what each setting does and note that full rebuild may reapply template defaults unless customization is remerged.

## 5.4) Template composition and storage strategy

### Problem statement

- We want to improve maintainability and reuse across templates without introducing a fragile runtime composition engine.
- Card-level modularization can reduce duplication, but it can also complicate ordering, compatibility, and debugging if it becomes a runtime requirement.

### Option comparison

1. **Full-dashboard template files only**

- Pros: simplest runtime model; easiest to reason about generated output.
- Cons: higher duplication across templates; weaker card-level reuse.

2. **Card-level registry units as runtime source of truth**

- Pros: maximal reuse and composability.
- Cons: significantly higher complexity for ordering, compatibility, validation, and migration.

3. **Hybrid authoring model (recommended for v1)**

- Keep full-dashboard template as the canonical runtime/release artifact.
- Allow optional card-fragment files for maintainers to compose a template during authoring/CI.
- Persist explicit composition order metadata in manifest/authoring contract.
- Pros: better maintainability without runtime complexity.
- Cons: requires light authoring discipline and validation tooling.

### Recommended v1 model

- **Runtime unit remains full dashboard template** (single assembled YAML artifact per `template_id`).
- **Authoring may be modular** using optional card fragments, but assembly must happen before release publishing (not at end-user runtime).
- Define deterministic `card_order` semantics for authoring assembly to avoid implicit ordering.

### Governance guardrails

- Fragment-level reuse must not bypass template-level dependency declarations.
- Published template output must remain parseable as a standalone dashboard template without additional remote card-fragment fetches.
- If fragment assembly fails in CI, publish is blocked.

## 6) Dependency handling policy

- **Required dependency missing**
  - Template selection is blocked.
  - User receives clear remediation guidance.

- **Recommended dependency missing**
  - Selection allowed.
  - User receives warning with impact summary.

- **Unknown dependency keys**
  - Treated as validation errors in registry CI.

## 6.1) Custom card strategy (explicit position)

### Product position

- ChoreOps dashboards are a **base layer accelerator**, not a lock-in UI system.
- The core value proposition remains: users can build high-quality dashboards directly from native ChoreOps entities (sensors, buttons, selects, services) without backend modifications.
- Custom cards are an enhancement path, not the architectural foundation.

### Registry responsibility boundary

- `choreops-dashboards` is a **template registry**, not a frontend-card monorepo.
- Dashboard templates may declare card dependencies, but card source code is out of scope for this repository.

### Future ChoreOps-specific card policy

- If ChoreOps-specific custom cards are created, each card should be maintained in its own dedicated repository (or a dedicated frontend bundle repository), not in the dashboard template registry.
- Rationale:
  - Aligns with HACS frontend distribution expectations and independent release cadence.
  - Keeps template governance and frontend build governance decoupled.
  - Enables isolated issue tracking, versioning, CI, and ownership for each card project.

### Dependency declaration policy for templates

- Templates must declare dependencies by stable, machine-readable identifiers (e.g., HACS repository key or canonical package ID), not prose-only names.
- Templates can depend on:
  - widely used third-party cards,
  - future ChoreOps-specific cards that are distributed from separate card repositories.
- Dependency class behavior:
  - `required`: block generation when missing.
  - `recommended`: allow generation with warning.

### Long-term maintainability rule

- No template in the registry may assume a private, unversioned, or registry-local card implementation.
- All card dependencies must have explicit public source and version compatibility metadata.

## 6.2) Localization strategy (explicit position)

### Problem statement

- Dashboard templates evolve independently, and translation strings evolve independently.
- We need a model that supports ongoing translation updates without breaking offline safety.

### Source-model options

1. **Integration-local only**
   - Keep dashboard translations only in integration repo assets (current-style baseline).
   - No online translation updates.

2. **Registry-remote only**
   - Keep dashboard translations only in dashboard registry and always fetch at runtime.
   - Fast updates, but weaker offline guarantees.

3. **Hybrid (recommended)**
   - Keep integration-local translation baseline (vendored fallback).
   - Optionally fetch remote translation bundles and merge/override valid keys.
   - If remote fails, local baseline remains authoritative.

### Recommended path

- Use **Hybrid** localization:
  - Local fallback directory in integration (proposed: `custom_components/choreops/dashboards/translations/`).
  - Optional remote translation bundle source aligned to dashboard registry lifecycle.
  - Deterministic merge: local baseline + valid remote override by language/key.

### Practical examples (what changes in real usage)

#### Example A: typo hotfix in Spanish

- **Integration-local only**: User waits for next ChoreOps release to get corrected text.
- **Registry-remote only**: Fix appears immediately, but dashboards lose translation updates if remote unavailable.
- **Hybrid**: Fix appears quickly when online; if offline, user still has valid local text.

#### Example B: new language added (`pl`)

- **Integration-local only**: `pl` unavailable until next integration release.
- **Registry-remote only**: `pl` can appear immediately, but availability depends on remote health.
- **Hybrid**: Existing languages always work locally; `pl` activates when remote bundle is available and valid.

#### Example C: malformed remote translation payload

- **Integration-local only**: Not applicable.
- **Registry-remote only**: Dashboards risk broken/missing UI labels.
- **Hybrid**: Invalid remote payload is ignored; local baseline continues to serve UI labels.

### Text-model options

1. **Literal text in YAML templates**
   - Fast authoring, but poor localization and high duplication.

2. **Per-template inline translation dictionaries**
   - Better locality, but large templates and duplicated key management.

3. **Key-based localization contract (recommended)**
   - Templates use stable keys (e.g., `ui["weekly_completed"]`), resolved from translation sensor payloads.
   - Centralized translation management with schema-validation and fallback behavior.

### Naming/organization recommendation

- Adopt integration-local baseline path: `custom_components/choreops/dashboards/translations/`.
- Keep language file format consistent: `{lang}_dashboard.json` for dashboard UI keys.
- Support key-level fallback to English when a translated key is missing.
- Do not require per-template `translations.path` in manifest records when
  runtime translation resolution is language-sensor-driven.

### Governance requirements

- Translation bundles must include schema version and language code metadata.
- Remote translation updates must be validated before merge.
- Unknown keys are allowed only if backward-compatible; key removals require deprecation notice.

## 7) Submission and review model

## Submission requirements

- Manifest record with complete required fields.
- YAML asset parseable and mapped to a valid `template_id`.
- Dependencies declared with stable keys.
- Changelog/notes for behavioral differences.

### Template submission workflow (v1)

1. Author adds/updates template asset(s) and manifest record(s) in
   `choreops-dashboards`.
2. Author completes submission checklist in PR description:

- `template_id` follows canonical format and remains immutable for published
  major lines,
- `source.path` exists and YAML parses cleanly,
- compatibility/dependency metadata is complete,
- lifecycle state and migration notes are provided when relevant.

3. CI validates manifest schema, naming/taxonomy, dependency identifiers, and
   YAML parseability.
4. Maintainers perform contract review and merge when all gates pass.

### Minimum acceptance bar (v1)

- No schema violations or naming drift.
- No unresolved dependency identifier errors.
- No missing/invalid template assets for manifest references.
- Clear release notes for user-visible behavior changes.

## Review gates

- Schema validation pass.
- Naming policy pass.
- Dependency key validation pass.
- Asset existence and parse validation pass.
- Compatibility metadata present and valid.

### CI/review quality gates (required)

- Manifest contract validator passes (required/optional fields and enum rules).
- `template_id` naming policy validator passes (`<audience>-<intent>-v<major>`).
- Dependency ID validator passes (stable machine-readable IDs, no duplicates).
- YAML parse/structure validator passes for every referenced template source.
- Lifecycle metadata validator passes (`active`/`deprecated`/`archived` only).
- Pull request must include compatibility note entry for integration-range impact.

## Approval rules

- Template-only PR: normal maintainer approval.
- Manifest schema change: architecture-owner approval required.

## 8) Lifecycle governance

- **Active**: available for selection.
- **Deprecated**: available with warning; replacement guidance required.
- **Archived**: hidden from new selections; retained for migration/backward compatibility window.

Deprecation must include a minimum communication window and explicit replacement path.

### Deprecation and retirement process (v1)

1. Mark template `lifecycle_state` as `deprecated` and provide replacement
   guidance via manifest notes/replaces metadata.
2. Keep template selectable during the deprecation window with explicit warning
   behavior in docs/release notes.
3. Maintain compatibility metadata until retirement threshold is reached.
4. Move template to `archived` only after minimum deprecation window and after
   replacement path has been communicated.
5. Preserve archived template references for migration/backward compatibility
   semantics; hide from new default selections.

## 8.1) Registry release versioning and channel strategy (`choreops-dashboards`)

### Problem statement

- We need predictable release channels for template consumers while preserving fast iteration for contributors.
- Versioning and branch policy must clearly distinguish stable releases, beta previews, and dev snapshots.

### Scope separation (critical)

- `manifest.schema_version`: contract/schema compatibility indicator (independent from release cadence).
- Registry release version: repository-level distribution/version marker for the template set.

### Version semantics (big-picture contract)

- `manifest.schema_version`
  - Purpose: parser/contract compatibility for manifest structure.
  - Meaning: can this integration understand this manifest shape.
  - Change trigger: schema field/rule changes.
- Integration version (`custom_components/choreops`)
  - Purpose: integration runtime version.
  - Meaning: what loader/runtime/features are available in the installed integration.
  - Relationship: template selection must satisfy compatibility guards (`min_integration_version`/`max_integration_version`).
- Registry release tag (`choreops-dashboards`)
  - Purpose: version of the published dashboard set snapshot.
  - Meaning: distribution bundle version for stable/beta/dev channels.
  - Relationship: may include multiple templates that share major identity lines (`*-v1`, `*-v2`) across families.

In short: schema version = contract shape, integration version = runtime capability,
and registry tag = published bundle snapshot.

### UI terminology policy

- Frontend/user-visible wording should use `user` terminology by default.
- `assignee` may remain in internal/backend transitional identifiers only where
  migration is still in progress.

### Recommended release semantics

1. **Stable channel**

- Tag format: `vX.Y.Z`.
- Intended for production/default consumption.
- Requires full validation gates and release notes.

2. **Beta channel**

- Tag format: `vX.Y.Z-beta.N`.
- Intended for early adopters and compatibility verification.
- May include new templates/features not yet promoted to stable.

3. **Dev channel**

- Snapshot format: `vX.Y.Z-dev.YYYYMMDD+<shortsha>`.
- Non-production channel for active testing and fast iteration.
- No stability guarantees beyond schema-contract validity.

### Branch strategy recommendation

- Use **single default development branch** (`main`) for normal contribution flow.
- Create **short-lived release branches** (`release/X.Y`) only when stabilization is needed for beta/stable promotion.
- Avoid long-lived parallel branch models unless maintenance burden clearly justifies them.
- Dev channel artifacts are produced from `main` snapshots; beta/stable are published from tagged commits.

### Promotion workflow (high level)

1. Merge candidate changes to `main`.
2. Publish dev snapshot for integration testing.
3. Cut `release/X.Y` if stabilization is needed; publish/update beta tags.
4. Promote to stable by tagging the validated release commit as `vX.Y.Z`.

### Integration vendoring synchronization workflow

1. Select dashboard registry artifact channel for integration release intent:

- stable integration release -> stable dashboard tag by default,
- beta integration release -> beta dashboard tag allowed,
- dev validation -> dev snapshot allowed.

2. Vendor selected registry assets into integration fallback paths.
3. Regenerate sync artifact metadata (tag, commit, channel) and include in
   release evidence.
4. Run contract validation and compatibility checks before integration release cut.
5. Record compatibility matrix entry in release notes/PR summary.
6. Block release if vendored manifest/asset contract checks fail.

### Governance constraints

- Any schema-breaking change requires a major schema/version policy review before stable promotion.
- Beta/dev channel artifacts must remain traceable to source commits and changelog entries.
- Stable tags are immutable once published.

## 9) Decision gates (must be resolved before implementation phase)

1. Canonical identity: `template_id` format and immutability rule with derived family key.
2. Schema versioning strategy: strict semver vs simplified major/minor policy.
3. Merge conflict rule: remote override always vs scoped override.
4. Dependency catalog source of truth: integration constants vs registry-maintained list.
5. Submission governance: who can approve schema-level changes.
6. Deprecation window length and enforcement process.
7. Custom card distribution model ratification: separate card repositories as default policy.
8. Template substitution field contract ratification (initial whitelist and expansion policy).
9. Localization source model ratification (local-only vs remote-only vs hybrid). ✅ Accepted: hybrid.
10. Template text localization model ratification (literal vs key-based contract). ✅ Accepted: key-based via translation sensor.
11. Dashboard helper lookup contract ratification (name-based vs identity-scoped vs direct EID injection). ✅ Accepted: attribute-scoped dynamic lookup only.
12. Helper lookup optimization strategy ratification (`dashboard_lookup_key` adoption and constraints). ✅ Accepted.
13. Dashboard template error-handling UX ratification. ✅ Accepted: warning-card pattern with actionable guidance and minimal validation ladder for enhanced helper lookup model; no hard-fail UX in v1.
14. Template preference customization model ratification. ✅ Accepted: companion preference docs for v1; no backend runtime preference engine.
15. Template composition storage model ratification (full-dashboard runtime unit vs card-level runtime composition vs hybrid authoring model). ✅ Accepted: hybrid authoring, dashboard-level runtime unit.
16. Registry release/channel versioning model ratification (`main` + tagged stable/beta + dev snapshots + optional short-lived release branches). ✅ Accepted.

## 10) Frozen defaults for builder handoff (v1)

These defaults are now frozen as the implementation baseline for v1 builder handoff.
They remain in force unless a new architecture ratification explicitly supersedes them.

- Use immutable kebab-case `template_id` values.
- Derive template family key from `template_id`; do not persist manifest `slug`.
- Do not persist per-template `template_version`; use source refs/tags for release provenance.
- Use explicit manifest schema version with backward-compatible minor evolution.
- Use local baseline + remote override by `template_id` for valid records only.
- Keep dependency key source of truth in integration constants with mirrored docs in dashboard repo.
- Require architecture-owner approval for schema changes.
- Set a defined deprecation window before archive state.
- Keep dashboard templates and custom card source code in separate repositories.
- Use hybrid localization with local baseline translations and optional validated remote overrides.
- Use key-based localization contract in templates instead of literal user-facing strings.
- Use `user.*` naming for user-facing substitution contract fields.
- Require multi-instance-safe substitution support with `integration.entry_id` as primary scope key.
- Use attribute-scoped dynamic helper lookup as required strategy.
- Keep dashboard template as canonical runtime unit; allow optional card-fragment authoring assets with explicit deterministic composition order metadata.
- Use SemVer-style registry tags for stable (`vX.Y.Z`) and beta (`vX.Y.Z-beta.N`) and publish dev snapshots from `main` (`vX.Y.Z-dev.YYYYMMDD+<shortsha>`).
- Prefer single default branch with short-lived `release/X.Y` branches only when stabilization is required.

### Freeze scope note

- Decision gates D1-D16 are accepted for v1 planning scope.
- Builder implementation should not reopen these decisions unless a blocker is found that cannot be resolved within this contract.
