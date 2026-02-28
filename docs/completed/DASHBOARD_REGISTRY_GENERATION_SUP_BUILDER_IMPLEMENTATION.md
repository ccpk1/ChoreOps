# Dashboard registry builder implementation plan (hard-fork execution)

## Purpose

This document is the builder-facing implementation plan for moving from the current dashboard generator to the new registry/contract model defined in:

- `docs/completed/DASHBOARD_REGISTRY_GENERATION_COMPLETED.md`
- `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`

This plan is execution-oriented and assumes architecture decisions D1-D16 are already accepted and frozen for v1.

## Hard-fork implementation constraints (mandatory)

- This is a new hard fork and has not been released.
- No legacy compatibility path is required.
- No legacy fallback behavior is required.
- Remove superseded methods/constants/helpers during implementation.
- Keep codebase clean: no dead flags, no dual-mode branches, no temporary compatibility shims.

## Additional frozen implementation decisions (from final review)

### Pre-release branch policy for dashboard repo

- Until first public release, all dashboard-repo work is allowed directly on `main`.
- First release preparation must introduce release tagging discipline (`vX.Y.Z`, prerelease tags).
- Post-first-release branch hardening can be revisited, but is out of scope for this builder cycle.

### Repository ownership map (frozen)

- **Dashboard source repo (`choreops-dashboards`) owns:**
  - canonical dashboard template source files,
  - canonical dashboard translation source files,
  - template authoring/release-operation documentation,
  - canonical dashboard `dashboard_registry.json` records.
- **Integration repo (`choreops`) owns:**
  - vendored runtime mirror of dashboard assets,
  - runtime loaders/resolution logic,
  - options flow and generation behavior,
  - sync tooling and CI parity checks for vendored assets,
  - runtime architecture contracts.

### Preference documentation structure (`pref_*`) — pending (non-blocking)

- `pref_*` values are template configuration keys, not separate runtime files.
- Exact preference documentation file layout is **not frozen yet**.
- This must not block core generator migration.
- Temporary guidance until finalized:
  - keep preference guidance close to template authoring docs in `choreops-dashboards`,
  - avoid hard-coding a manifest field that may change before first release.

### Proposed new option (recommended): PR-publishable preference assets + runtime delivery

This option ensures preference guidance ships with each template PR, remains available at runtime, and can still be published to wiki without manual duplication.

#### 1) Canonical source of truth

- Canonical preference docs live in dashboard source repo assets:
  - `choreops-dashboards/preferences/<template_id>.md`
- Canonical preference summary metadata lives in `choreops-dashboards/dashboard_registry.json` per template.
- Integration vendors/syncs those assets into runtime mirror:
  - `custom_components/choreops/dashboards/preferences/<template_id>.md`

#### 2) User entry points

- In options flow template selection:
  - show concise preference summary from manifest metadata (`pref key`, default, allowed values, short description)
  - expose deterministic “View preferences” behavior with this resolution order:
    1. local vendored preference asset,
    2. downloaded remote preference asset for selected release/ref,
    3. wiki URL fallback.

#### 3) Repository mapping

- `choreops-dashboards`:
  - owns canonical preference docs and manifest metadata,
  - owns optional wiki publication automation.
- `choreops`:
  - consumes and displays metadata in options flow,
  - includes vendored runtime mirror of preference docs for offline-safe baseline.

#### 4) Maintenance model

- Single authoring source for full preference docs (`preferences/*.md`) in dashboard repo.
- PR requirement: template `pref_*` changes must update both manifest preference metadata and matching `preferences/<template_id>.md`.
- CI checks:
  - fail if template has `pref_*` usage but no manifest preference metadata,
  - fail if template has `pref_*` usage but no preference asset file,
  - fail if manifest `preferences.doc_asset_path` does not resolve.

#### 5) Minimal manifest metadata shape (v1)

- `preferences` object:
  - `summary` (array of `{ key, default, allowed, description_short }`)
  - `doc_asset_path` (string: `preferences/<template_id>.md`)
  - `wiki_url` (optional string fallback)

## Quality and professionalism requirements (mandatory)

Implementation must follow:

- `docs/DEVELOPMENT_STANDARDS.md`
- `docs/ARCHITECTURE.md`
- `docs/CODE_REVIEW_GUIDE.md`
- `docs/RELEASE_CHECKLIST.md`

Platinum expectations for this initiative:

- Complete type hints and docstrings for all added/changed public methods
- No hardcoded user-facing strings (constants + translation keys)
- Lazy logging only
- Boundary rules respected (`utils/engines` purity, manager write ownership)
- Test coverage added for each new contract branch (especially D11/D12/D13)

## Current implementation touchpoints (from codebase)

Core implementation files:

- `custom_components/choreops/helpers/dashboard_builder.py`
- `custom_components/choreops/helpers/dashboard_helpers.py`
- `custom_components/choreops/managers/ui_manager.py`
- `custom_components/choreops/options_flow.py`
- `custom_components/choreops/templates/dashboard_minimal.yaml`
- `custom_components/choreops/templates/dashboard_full.yaml`
- `custom_components/choreops/templates/dashboard_admin.yaml`
- `custom_components/choreops/sensor.py`
- `custom_components/choreops/select.py`

Current test touchpoints:

- `tests/test_dashboard_builder_release_fetch.py`
- `tests/test_dashboard_template_release_resolution.py`
- `tests/test_options_flow_dashboard_release_selection.py`
- `tests/validate_system_dashboard_select.py`

## Gap-closure addendum (2026-02-27)

The implementation is materially advanced but not complete. The following items are mandatory before this effort can be considered done.

### A) Template lookup migration completion

- All assignee and admin templates must use instance-safe lookup contracts.
- Legacy helper discovery by assignee display-name scan is not sufficient for multi-instance determinism.
- Required outcome:
  - templates resolve helper targets through integration-scoped lookup identity and direct helper pointers,
  - no remaining template blocks rely on legacy name-only discovery.

### B) Dashboard helper sensor contract completion

- Dashboard helper payload must expose stable lookup identity attributes needed by templates and troubleshooting.
- Required contract additions:
  - integration entry identity field,
  - deterministic lookup key field,
  - existing helper pointer payload must remain backward-safe during migration.

### C) Release selection parity (create vs update)

- Dashboard generator behavior must be consistent for create and update flows.
- Required outcome:
  - pinned release and prerelease policy values are passed to both create and update builder paths,
  - tests verify parity and no silent fallback to defaults on create.

### D) Dashboard provenance metadata stamping

- Generated dashboard config must include troubleshooting provenance metadata.
- Required metadata contract (minimum):
  - selected template ID,
  - source type (local vendored vs remote release),
  - selected release/ref when remote applies,
  - generation timestamp,
  - integration entry ID.
- Metadata placement must be deterministic and documented (for example under dashboard-level metadata keys and/or standardized top-level markdown/comment header card).

### E) Acceptance tests required for addendum

- Template contract tests verifying lookup identity behavior for all shipped templates.
- Sensor attribute tests verifying presence and shape of new lookup identity fields.
- Options-flow tests proving create/update both honor pinned release + prerelease flags.
- Dashboard generation tests proving provenance metadata is stamped and preserved/updated correctly.

### F) Manifest contract parity gaps (standards section 3)

- Current manifest records do not yet satisfy the full ratified v1 runtime contract fields.
- Required parity work:
  - add explicit custom-card dependency declarations per template (`dependencies.required[]`, `dependencies.recommended[]`),
  - add required compatibility fields (`min_integration_version`, `max_integration_version` as applicable),
  - add explicit source contract fields (`source.type`, `source.ref` when remote applies),
  - add dependency contract structure (`dependencies.required`, `dependencies.recommended`),
  - add ownership metadata field(s) per standards.
- Validation required:
  - schema validator and tests must fail on missing contract-required fields.

### G) Runtime contract parity gaps (standards section 5.5)

- Remote manifest merge contract (local baseline + validated remote override by `template_id`) is not fully implemented.
- Dependency enforcement contract is incomplete:
  - required dependencies must block generation with deterministic reason,
  - recommended dependencies must warn and continue.
- Lifecycle-state selection filtering (`active`/`deprecated`/`archived`) needs explicit enforcement in selection pipeline.
- Remote payload cache/refresh policy (TTL, stale-safe fallback, rate-limit-aware behavior) requires implementation and tests.

### H) Substitution contract migration gaps (standards section 5.1 + D8)

- Templates still use legacy `assignee.*` user-facing injection in multiple locations.
- Required migration:
  - converge user-facing template contract to `user.*` keys,
  - keep only explicit whitelist substitutions from ratified contract,
  - remove ad-hoc user-facing substitution aliases after migration window.

### I) Source-of-truth sync automation gaps (dual-repo operations)

- Sync topology requires one-way canonical flow: `choreops-dashboards` -> `choreops` vendored mirror.
- Required implementation:
  - add/finish explicit sync tooling in integration repo,
  - add CI parity validation between canonical assets and vendored assets,
  - document and enforce “no direct template authoring” under vendored mirror paths.
- Builder acceptance must include reproducible sync command and parity test evidence.

## Phase 0 — Asset topology migration (required first)

### Goal

Move dashboard assets to the new repository/source layout, rename templates to contract-based filenames, and repoint integration loaders/helpers to the new directories.

### Phase status

- **Completion:** 100%
- **Execution status:** Completed

### Source-of-truth and vendored mirror model

- Source-of-truth repository for dashboard assets:
  - `/workspaces/choreops-dashboards/templates/`
  - `/workspaces/choreops-dashboards/translations/`
  - `/workspaces/choreops-dashboards/preferences/`
- Vendored integration mirror (offline-safe runtime baseline):
  - `custom_components/choreops/dashboards/templates/`
  - `custom_components/choreops/dashboards/translations/`
  - `custom_components/choreops/dashboards/preferences/`

### Sync topology (frozen)

- Sync direction is one-way: `choreops-dashboards` -> `choreops` vendored mirror.
- Sync execution point is integration repo tooling (`scripts/sync_dashboards.py`).
- Builder must not implement manual/implicit sync behavior.

### Template filename migration contract (frozen for build)

- Template filenames must be contract-based and deterministic.
- Runtime/template asset filenames should match `template_id`.
- Naming format for v1: `<template_id>.yaml`.
- Legacy-style filenames (for example `dashboard_full.yaml`, `dashboard_minimal.yaml`) are removed after migration.

### Translation filename and directory contract (frozen for build)

- Dashboard translation files move to `dashboards/translations` directories (source + vendored mirror).
- Keep existing language suffix model for dashboard translation files:
  - `<lang>_dashboard.json`
- Remove superseded translation asset paths once loaders are repointed.

### Required migration checklist

- [x] Create/confirm new source directories in dashboard repo:
  - `/workspaces/choreops-dashboards/templates/`
  - `/workspaces/choreops-dashboards/translations/`
  - `/workspaces/choreops-dashboards/preferences/`
- [x] Create/confirm vendored mirror directories in integration:
  - `custom_components/choreops/dashboards/templates/`
  - `custom_components/choreops/dashboards/translations/`
  - `custom_components/choreops/dashboards/preferences/`
- [x] Define and commit a template file rename map from old names to `<template_id>.yaml`
- [x] Move template source files into dashboard repo `templates/` using renamed filenames
- [x] Move dashboard translation source files into dashboard repo `translations/`
- [x] Move/add preference docs source files into dashboard repo `preferences/`
- [x] Vendor sync copies from dashboard repo into integration mirror directories
- [x] Repoint integration loaders/helpers to read from new integration mirror paths
- [x] Remove obsolete old-path template/translation files from integration repo

### Committed template rename map

- `dashboard_full.yaml` -> `full.yaml`
- `dashboard_minimal.yaml` -> `minimal.yaml`
- `dashboard_admin.yaml` -> `admin.yaml`

### Files (expected)

- `custom_components/choreops/helpers/dashboard_builder.py`
- `custom_components/choreops/helpers/translation_helpers.py`
- `custom_components/choreops/managers/ui_manager.py`
- `custom_components/choreops/options_flow.py`
- `custom_components/choreops/dashboards/templates/*`
- `custom_components/choreops/dashboards/translations/*`
- `custom_components/choreops/dashboards/preferences/*`
- `/workspaces/choreops-dashboards/templates/*`
- `/workspaces/choreops-dashboards/translations/*`
- `/workspaces/choreops-dashboards/preferences/*`

## Critical traps and mitigations (review findings)

This section captures high-risk misses that can derail implementation quality even with correct architecture decisions.

### Trap 1: Path contract drift across docs/manifests/loaders

- Risk: Some references still use legacy-style `templates/...` paths while migration targets `dashboards/templates/...`.
- Mitigation:
  - Define one canonical path contract constant set in integration code.
  - Reject PRs where manifest `source.path` does not match canonical layout.

### Trap 2: Filename migration ambiguity (`dashboard_full.yaml` vs `<template_id>.yaml`)

- Risk: Builder renames files inconsistently or leaves mixed naming in tree.
- Mitigation:
  - Commit a single authoritative rename map before moving files.
  - Add CI check that all template filenames match `template_id` exactly.

### Trap 3: Dual-source translation confusion

- Risk: translations load from old path in some codepaths and new path in others.
- Mitigation:
  - Centralize translation base-path resolution in one helper.
  - Remove all direct string-literal path usage after migration.

### Trap 4: Helper payload contract not atomically upgraded

- Risk: templates expect `dashboard_lookup_key`/new pointers before helper entities expose them.
- Mitigation:
  - Sequence implementation: helper attributes first, templates second.
  - Add guard tests that fail if required helper attributes are missing.

### Trap 5: Selection/options flow still coupled to legacy template profile constants

- Risk: options flow uses old style/profile constants not aligned with new `template_id` contract.
- Mitigation:
  - Route selection state by canonical `template_id` values.
  - Remove/reduce implicit mapping layers where possible.

### Trap 6: Incomplete dead-code removal after hard-fork migration

- Risk: stale constants/helpers remain and create hidden alternate paths.
- Mitigation:
  - Require explicit “deleted artifacts” list in PR description.
  - Add final grep audit for legacy names/paths.

### Trap 7: Remote/local precedence regressions

- Risk: migration accidentally flips precedence or accepts invalid remote records.
- Mitigation:
  - Lock precedence tests: local baseline + remote valid override only.
  - Add negative tests for malformed manifest/template records.

### Trap 8: Release channel leakage

- Risk: stable integration consumes beta/dev dashboard artifacts unintentionally.
- Mitigation:
  - Enforce explicit channel gate in loader/options selection path.
  - Add tests that stable flow rejects non-stable tags unless opt-in flag is set.

### Trap 11: Missing sync automation between source repo and vendored mirror

- Risk: manual sync causes manifest/template drift and release mismatch.
- Mitigation:
  - Add mandatory sync tool (`scripts/sync_dashboards.py`) for integration repo.
  - Sync tool responsibilities:
    - fetch selected dashboard repo ref/tag,
    - purge and repopulate `custom_components/choreops/dashboards/`,
    - verify manifest/template file parity,
    - validate schema version compatibility expectations.

### Trap 12: GitHub API rate limiting during repeated options-flow fetches

- Risk: unauthenticated GitHub API calls can hit 60/hr limit and degrade UX.
- Mitigation:
  - Add in-memory TTL cache for remote manifest/release payloads in dashboard builder.
  - Suggested TTL window: 15-60 minutes (default 30 minutes).
  - On rate limit (`403`) or timeout/error, immediately fall back to local baseline without blocking.

### Trap 13: False positives in custom-card installation checks (YAML mode)

- Risk: cards installed manually via `/local/` or filesystem may be flagged missing if not present in UI resource registry.
- Mitigation:
  - Extend `check_custom_cards_installed` to include filesystem presence checks when resource registry check fails.
  - Check expected card asset locations under `www/community/` (and mapped `/local/` paths where applicable).
  - Keep warning behavior conservative: if any trusted signal confirms presence, do not show missing-card warning.

### Trap 14: New template ships before integration release and translation keys are missing

- Risk: users can fetch a new dashboard template, but required translation keys are unavailable until next integration release.
- Mitigation:
  - Add remote translation bundle retrieval keyed by selected dashboard release/ref.
  - Cache translation bundles by release/ref (TTL) to avoid API pressure.
  - Validate translation payload schema/language metadata before use.
  - Fall back immediately to local vendored translations when fetch or validation fails.

### Trap 9: D13 warning behavior inconsistency between templates

- Risk: one template uses canonical D13 ladder while others retain old logic.
- Mitigation:
  - Treat canonical D13 Jinja as mandatory include-pattern for all supported templates.
  - Add snapshot/assertion tests per template profile for E01/E02/E03 behavior.

### Trap 10: Documentation authority drift after move

- Risk: implementers update one repo docs but leave conflicting instructions in the other.
- Mitigation:
  - Require cross-repo doc link verification in PR checklist.
  - Keep runtime contracts in integration docs, authoring/release ops in dashboard repo docs.

## Pre-implementation verification questions (must be answered in kickoff)

- [ ] What is the exact filename rename map (`old_name -> <template_id>.yaml`)?
- [ ] Which exact constants are removed, and what replaces them?
- [ ] Which loader/helper methods are deleted vs refactored?
- [ ] What is the one canonical template base path constant?
- [ ] What is the one canonical translation base path constant?
- [ ] What exact channel does stable integration consume by default?
- [ ] Which tests prove D13 behavior across all supported templates?
- [ ] Is `preferences/<template_id>.md` required for all templates using `pref_*`?
- [ ] What is the sync tool contract (`scripts/sync_dashboards.py`) and who owns it?
- [ ] What TTL value is chosen for remote manifest/release cache?
- [ ] What TTL value is chosen for remote translation bundle cache?

## Phase 1 — Contract freeze into code (no feature drift)

### Goal

Convert frozen standards into explicit in-code contracts before broader refactors.

### Checklist

- [ ] Create/confirm manifest contract types/constants in integration code
  - Required fields: `template_id`, `slug`, `display_name`, `template_version`, `lifecycle_state`
  - Compatibility fields: `min_integration_version`, `max_integration_version`, `schema_version`
  - Dependency fields: `dependencies.required[]`, `dependencies.recommended[]`
- [ ] Define explicit D11 helper attribute contract in code constants/types
  - `purpose`, `integration_entry_id`, `user_id`, `dashboard_lookup_key`
- [ ] Define D13 error taxonomy constants
  - `D13-E01`, `D13-E02`, `D13-E03`
- [ ] Freeze loader path constants for new dashboard asset layout
  - integration vendored templates: `custom_components/choreops/dashboards/templates/`
  - integration vendored translations: `custom_components/choreops/dashboards/translations/`
  - remote/source templates: dashboard repo `templates/`
  - remote/source translations: dashboard repo `translations/`
- [ ] Remove superseded name-only lookup constants/helpers
- [ ] Remove legacy compatibility toggles and old fallback branches related to dashboard lookup mode

### Files (expected)

- `custom_components/choreops/const.py`
- `custom_components/choreops/type_defs.py`
- `custom_components/choreops/helpers/dashboard_helpers.py`
- `custom_components/choreops/helpers/dashboard_builder.py`
- `custom_components/choreops/helpers/translation_helpers.py`

## Phase 2 — Dashboard helper lookup and context model upgrade

### Goal

Implement D11/D12 in runtime lookup and generator context assembly.

### Checklist

- [ ] Ensure helper generation/exposure includes required attributes:
  - `integration_entry_id`
  - `user_id`
  - `dashboard_lookup_key = <entry_id>:<user_id>`
- [ ] Update helper lookup internals to prefer `dashboard_lookup_key` with `purpose` filter
- [ ] Enforce uniqueness expectation for helper resolution key
- [ ] Ensure missing identity inputs are surfaced as explicit errors (for D13 handling)
- [ ] Remove name-only lookup paths and dead code

### Files (expected)

- `custom_components/choreops/helpers/dashboard_helpers.py`
- `custom_components/choreops/helpers/dashboard_builder.py`
- `custom_components/choreops/managers/ui_manager.py`

## Phase 3 — Template contract migration (D13 canonical Jinja)

### Goal

Update templates to canonical D13 Jinja pattern and new substitution keys.

### Checklist

- [ ] Apply canonical D13 Jinja block to template entry sections that resolve dashboard helper pointers
- [ ] Add canonical admin Jinja alignment for both admin modes:
  - shared admin view uses selector-driven user context, then resolves helper via `dashboard_lookup_key`
  - per-user admin tab uses injected tab user context, then resolves helper via `dashboard_lookup_key`
  - both modes enforce D13 validation ladder (`E01`/`E02`/`E03`) before rendering cards
- [ ] Migrate template files to renamed contract filenames (`<template_id>.yaml`) in new template directories
- [ ] Replace `assignee.*` user-facing substitutions with `user.*` contract fields
- [ ] Ensure templates use:
  - `<< user.name >>`
  - `<< user.user_id >>`
  - `<< integration.entry_id >>`
- [ ] Ensure D13 validation ladder is present and ordered:
  - E01 missing required template inputs
  - E02 helper unresolved/unknown/unavailable
  - E03 helper payload incomplete (missing `core_sensors` / translation pointer)
- [ ] Ensure warning-card behavior sets stop-render flag consistently
- [ ] Remove old name-only helper lookups and stale template comments

### Files (expected)

- `/workspaces/choreops-dashboards/templates/*.yaml` (source)
- `custom_components/choreops/dashboards/templates/*.yaml` (vendored mirror)

## Phase 4 — Generator/options flow alignment with registry model

### Goal

Align dashboard generation and options flow with frozen release/channel and manifest policies.

### Checklist

- [ ] Enforce frozen release tag conventions (`vX.Y.Z`, prerelease variants)
- [ ] Ensure release channel handling aligns with D16 (`dev`/`beta`/`stable`)
- [ ] Implement pre-release dashboard repo branch policy assumptions (direct `main` flow until first release)
- [ ] Enforce dependency behavior:
  - `required` blocks selection/generation
  - `recommended` warns and continues
- [ ] Ensure compatibility filtering uses manifest compatibility fields
- [ ] Repoint template loading logic to new template directories and contract filenames
- [ ] Repoint translation loading logic to `dashboards/translations` directories
- [ ] Add remote translation-bundle update support for selected template release/ref:
  - in-memory TTL cache (default 30 minutes)
  - payload schema/language validation before merge/use
  - fallback to local vendored translations on fetch/validation failure
- [ ] Add custom-card check fallback path in `check_custom_cards_installed`:
  - resource registry check first
  - filesystem checks under `www/community/` (and mapped `/local/` references) if registry signal is missing
- [ ] Add remote manifest/release caching to reduce GitHub API pressure:
  - in-memory TTL cache (default 30 minutes)
  - immediate local-baseline fallback on `403` rate limit/timeouts
- [ ] Remove superseded release selection branches not needed in hard-fork model

### Files (expected)

- `custom_components/choreops/helpers/dashboard_builder.py`
- `custom_components/choreops/helpers/translation_helpers.py`
- `custom_components/choreops/options_flow.py`

## Phase 5 — Dead code and constant cleanup

### Goal

Finish hard-fork cleanup by removing unused code introduced by migration.

### Checklist

- [ ] Remove unused methods replaced by D11/D12/D13 flow
- [ ] Remove unused constants no longer referenced after template/helper migration
- [ ] Remove stale docs/comments that describe old lookup behavior
- [ ] Remove obsolete old template directory usage (`custom_components/choreops/templates/`) if no longer referenced
- [ ] Remove obsolete old translation directory usage for dashboard assets if no longer referenced
- [ ] Verify no orphan imports remain
- [ ] Remove manual vendoring instructions once sync tooling is in place

## Phase 5.1 — Sync automation and CI guardrails

### Goal

Eliminate human-sync drift between dashboard source repo and integration vendored mirror.

### Checklist

- [ ] Add `scripts/sync_dashboards.py` to integration repo
- [ ] Support sync by explicit ref/tag input
- [ ] Purge and repopulate vendored dashboard asset directory atomically
- [ ] Validate manifest-to-file parity after sync
- [ ] Validate schema compatibility expectations during sync
- [ ] Add CI check that fails when manifest declares missing template files

### Files (expected)

- `scripts/sync_dashboards.py`
- CI workflow/config files in integration repo
- `docs/RELEASE_CHECKLIST.md` (sync step linkage)

## Phase 5.2 — Preference docs finalization (non-blocking)

### Goal

Finalize preference documentation delivery and publishing workflow without blocking core runtime migration.

### Checklist

- [ ] Confirm `preferences/<template_id>.md` as required source asset for templates that use `pref_*`
- [ ] Confirm manifest `preferences` metadata shape and required fields (`summary`, `doc_asset_path`, optional `wiki_url`)
- [ ] Confirm options-flow/runtime preference doc resolution order (local vendored -> remote release asset -> wiki fallback)
- [ ] Confirm wiki publication automation from `preferences/*.md` (optional for runtime, required for docs UX)
- [ ] Ensure naming guidance for `pref_*` keys is documented and consistent

### Files (expected)

- `/workspaces/choreops-dashboards/README.md`
- `/workspaces/choreops-dashboards/preferences/*`
- `/workspaces/choreops-dashboards/dashboard_registry.json`

## Phase 6 — Tests and validation (builder definition of done)

### Goal

Provide proof that the new model works and legacy behavior is fully retired.

### Required tests to add/update

- [ ] D11 helper lookup tests:
  - resolves by `dashboard_lookup_key`
  - no name-only fallback
- [ ] D12 optimization/contract tests:
  - uniqueness behavior and expected failure mode on collisions
- [ ] D13 template behavior tests:
  - E01 missing inputs warning
  - E02 helper unresolved warning
  - E03 helper incomplete warning
  - success path sets `skip_render = false`
- [ ] Template path/rename migration tests:
  - source templates resolved from new filenames/layout
  - vendored mirror fallback resolved from new `dashboards/templates` path
- [ ] Translation path migration tests:
  - dashboard translations load from new `dashboards/translations` path
  - language fallback behavior preserved in new path model
- [ ] Translation bundle update tests:
  - release/ref keyed remote translation fetch success path
  - cache hit within TTL and refresh after TTL
  - fetch/schema failure fallback to local vendored translations
- [ ] Custom-card detection robustness tests:
  - resource registry only
  - filesystem fallback only
  - both missing
- [ ] Remote fetch/cache resilience tests:
  - cache hit within TTL
  - cache refresh after TTL
  - `403` rate-limit fallback to local baseline
- [ ] Manifest/dependency contract tests:
  - required dependency block behavior
  - recommended dependency warning behavior
- [ ] Preference metadata/asset contract tests:
  - template using `pref_*` requires manifest `preferences` block
  - manifest `preferences.doc_asset_path` resolves in source and vendored mirrors
- [ ] Options flow tests for release/channel behavior under D16

### Existing tests likely to update

- `tests/test_dashboard_builder_release_fetch.py`
- `tests/test_dashboard_template_release_resolution.py`
- `tests/test_options_flow_dashboard_release_selection.py`

### Validation commands (must pass)

- [ ] `./utils/quick_lint.sh --fix`
- [ ] `mypy custom_components/choreops/`
- [ ] `python -m pytest tests/ -v --tb=line`

## Builder handoff checklist

Use this checklist before implementation kickoff:

- [ ] D1-D16 snapshot attached
- [ ] Canonical D13 Jinja block linked for implementation
- [ ] Template rename map attached (old filename -> new `<template_id>.yaml`)
- [ ] Template/translation directory migration map attached (source and vendored mirror)
- [ ] Preference-doc plan attached (`preferences/<template_id>.md` + manifest `preferences` contract)
- [ ] Sync tooling contract attached (`scripts/sync_dashboards.py` usage + CI checks)
- [ ] Translation-bundle runtime update contract attached (cache TTL + fallback behavior)
- [ ] File-by-file scope confirmed
- [ ] No-legacy/no-fallback rule acknowledged
- [ ] Removal of unused methods/constants explicitly included in PR scope
- [ ] Test plan and acceptance criteria acknowledged

## PR acceptance criteria

A builder PR is complete only when:

- [ ] New lookup + error handling contract implemented (D11/D12/D13)
- [ ] Templates migrated to canonical contract fields, new filenames, and new directory layout
- [ ] Dashboard translation assets migrated to new directory layout and loader paths repointed
- [ ] Sync automation implemented and CI parity checks active
- [ ] Legacy/fallback paths removed
- [ ] Unused methods/constants removed
- [ ] All required tests added/updated and passing
- [ ] Quality gates pass with no unresolved issues
- [ ] Documentation updates included for any implementation-level contract clarifications

## Out-of-scope for this builder plan

- New dashboard visual design system work
- Runtime card composition engine
- Any compatibility shims for legacy released consumers
- Additional UX framework beyond the D13 warning-card pattern
