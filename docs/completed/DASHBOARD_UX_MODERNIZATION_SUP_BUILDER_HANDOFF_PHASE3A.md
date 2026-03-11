# Builder handoff: Dashboard UX modernization (Phase 3A composition parity)

## Handoff purpose

This document is the execution handoff for Builder to complete Phase 3A safely and then finalize `user-chores-v1` on the correct architecture.

Primary intent:

1. Eliminate divergence between **local sync** and **remote release-download apply** paths.
2. Keep runtime generator behavior deterministic (runtime consumes fully composed templates only).
3. Finalize full-featured chores template after composition parity is proven.

## Scope and boundaries

### In scope

- Define and implement a shared-template composition contract.
- Apply composition in both asset ingestion paths:
  - Local canonical -> vendored sync flow.
  - Remote prepared release asset apply flow.
- Add tests that prove parity and fail-fast behavior.
- Finalize `user-chores-v1` against the new composition contract.

### Out of scope

- New custom card development.
- Changes to dashboard multi-view assembly model (`views` contract remains).
- Admin v2 template modernization (Phase 4).
- Broad options flow redesign.

## Current state snapshot (as of this handoff)

- `user-chore-essentials-v1` is implemented and registered.
- `user-chores-v1` draft exists and carries PoC2 behavior, but architectural alignment is not complete.
- Local sync currently performs direct copy only (`utils/sync_dashboard_assets.py`).
- Remote prepared release apply currently writes provided assets directly (`_replace_managed_dashboard_assets_from_release`).

Implication: if shared fragments are introduced without a unified composition contract, local and remote generated dashboards can diverge.

## Non-negotiable architectural decisions

1. Runtime generator consumes **fully composed templates only**.
2. Composition is a **pre-runtime asset concern**, not part of `render_dashboard_template` behavior.
3. Unresolved include markers are **hard failures** in both sync and release-apply paths.
4. Composition must preserve existing path-guard and managed-directory overwrite safety behavior.

## Source/published asset model

### Source authoring assets (canonical)

- Canonical repo: `choreops-dashboards`
- Proposed source directories:
  - `templates/` (template shells)
  - `templates/shared/` (shared fragments)

### Published runtime assets (vendored and release payload)

- Must remain fully composed in:
  - `custom_components/choreops/dashboards/templates/*.yaml`
- No unresolved composition tokens are allowed in published runtime templates.

## Composition contract proposal (Builder to implement)

### Marker syntax

Use a strict marker syntax in template shells:

- `<< template_shared.<fragment_id> >>`

Examples:

- `<< template_shared.chore_row_poc2_v1 >>`
- `<< template_shared.chore_row_actions_poc2_v1 >>`

### Fragment naming

- Pattern: `<domain>_<purpose>_v<version>`
- Example initial fragment:
  - `chore_row_poc2_v1`

### Resolution rules

1. Markers map to fragment files under `templates/shared/`.
2. Missing fragment -> hard fail.
3. Duplicate/recursive expansion -> hard fail.
4. Final output must contain zero unresolved `template_shared` markers.

## File-level execution plan

### Step A: Add composition utility and integrate local sync path

Files:

- `utils/sync_dashboard_assets.py`
- Optional helper module under `utils/` if needed for readability.

Tasks:

1. Add composition stage before copy/parity comparison.
2. Ensure parity check compares composed canonical outputs with vendored outputs.
3. Preserve current behavior for translations/preferences/manifest copy and hash checks.
4. Keep CLI contract stable (`--check` behavior remains consistent).

### Step B: Integrate composition in remote release-apply path

Files:

- `custom_components/choreops/helpers/dashboard_helpers.py`

Targets:

- `_replace_managed_dashboard_assets_from_release`
- `async_apply_prepared_dashboard_release_assets`

Tasks:

1. Compose template assets from prepared payload before writing to disk.
2. Apply identical marker resolution rules as sync path.
3. Preserve path traversal protections and managed-folder clean replace behavior.
4. Keep manifest/template cache priming and translation cache reset behavior unchanged.

### Step C: Add parity and safety tests

Files:

- `tests/test_dashboard_release_asset_apply.py`
- `tests/test_dashboard_template_contract.py`
- Add new focused test module(s) as needed for composition contract.

Minimum tests:

1. Missing fragment marker fails in sync path.
2. Missing fragment marker fails in release-apply path.
3. Same template shell + fragment set produces byte-identical composed template in both paths.
4. Existing path-escape protections remain enforced.

### Step D: Finalize chores template on composed architecture

Files:

- `choreops-dashboards/templates/user-chores-v1.yaml`
- `choreops-dashboards/templates/shared/*` (new)
- `choreops-dashboards/preferences/user-chores-v1.md`
- `choreops-dashboards/dashboard_registry.json`
- `choreops-dashboards/translations/en_dashboard.json` (if new keys required)

Tasks:

1. Replace inline-heavy repeated row logic with shared marker inclusion.
2. Keep header/snippet contracts and metadata stamp placement intact.
3. Confirm dependency declarations remain accurate for all `custom:*` usage.
4. Re-run parity and dashboard test gates.

## Validation commands (required)

Run in `choreops` repo unless noted.

1. `python utils/sync_dashboard_assets.py`
2. `python utils/sync_dashboard_assets.py --check`
3. `./utils/quick_lint.sh --fix`
4. `python -m pytest tests/test_dashboard_template_render_smoke.py tests/test_dashboard_manifest_dependencies_contract.py tests/test_dashboard_template_contract.py -v --tb=line`
5. `python -m pytest tests/test_dashboard_release_asset_apply.py tests/test_dashboard_manifest_runtime_policy.py -v --tb=line`
6. `python -m pytest tests/test_dashboard_helper_size_reduction.py -v --tb=line`

If broader suite is needed after major helper changes:

- `python -m pytest tests/test_dashboard_* -v --tb=line`

## Acceptance criteria (Builder must confirm explicitly)

1. Composition contract is implemented in both sync and release-apply paths.
2. Runtime templates are fully composed (no unresolved shared markers).
3. Local sync and remote release-apply produce byte-identical composed template outputs for the same source inputs.
4. Existing release-apply guardrails and cache refresh behavior remain intact.
5. `user-chores-v1` is finalized on shared composition architecture and passes render/contract/dependency/size checks.

## Known traps and mitigations

### Trap 1: One-path composition

- Risk: local looks right, remote differs.
- Mitigation: parity tests must exercise both paths and compare outputs.

### Trap 2: Runtime fragment leakage

- Risk: unresolved markers hit dashboard generation and fail at render time.
- Mitigation: hard-fail marker scan post-compose in both paths.

### Trap 3: Safety regression in apply path

- Risk: path normalization checks weakened by new composition logic.
- Mitigation: keep existing `_resolve_dashboard_asset_target_path` guarantees and add regression tests.

### Trap 4: Generated vs source edit confusion

- Risk: contributors edit vendored generated outputs directly.
- Mitigation: document source-of-truth and composition lifecycle in guide updates.

## Opportunities to capture while implementing

1. Add concise composition diagnostics (missing marker, source template path) to reduce triage time.
2. Keep composition utility pure/testable so future templates can adopt shared blocks safely.
3. Build one-fragment migration first (chore row) before expanding shared blocks.

## Builder handoff completion template

When Builder finishes this handoff, report back in this structure:

1. **What changed** (files and summary)
2. **Composition parity proof** (test output + byte-identity evidence)
3. **Guardrail verification** (path safety/cache behavior)
4. **Template finalization status** (`user-chores-v1`)
5. **Open follow-ups** (if any)
