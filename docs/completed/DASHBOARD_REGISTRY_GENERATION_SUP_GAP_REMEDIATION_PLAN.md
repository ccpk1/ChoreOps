# Dashboard registry gap remediation plan

## Purpose

This document is the execution plan for closing remaining gaps against:

- `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
- `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_BUILDER_IMPLEMENTATION.md`

It defines:

1. full gap list from the wider audit,
2. where template edits must happen to keep repositories synchronized,
3. an ordered remediation plan with validation gates.

## Execution updates

- 2026-02-27: Began Phase R5 full regression and closeout validation.
  - Validation gates executed:
    - `./utils/quick_lint.sh --fix` → passed
    - `mypy custom_components/choreops/` → passed (0 errors)
    - full test suite (`runTests`) → passed (1524/1524)
  - Immediate follow-up required before archival:
    - Reconcile stale `Audit matrix`/`Full gap list` entries that still show previously remediated items as partial or missing.
    - Confirm owner approval and completion/archive workflow.

- 2026-02-27: Implemented template-aware missing dependency helper flow (UX refinement).
  - Replaced static first-screen card list with a dedicated post-template-selection helper step for missing required dependencies.
  - Added manifest dependency metadata support (`name`, `url`) so helper output can show dynamic dependency labels and links per selected user/admin templates.
  - Added explicit bypass acknowledgement path in options flow before continuing generation when required dependencies are missing.
  - Validation evidence:
    - `./utils/quick_lint.sh --fix` → passed
    - `python -m pytest tests/test_options_flow_dashboard_release_selection.py tests/test_dashboard_manifest_runtime_policy.py tests/test_dashboard_manifest_dependencies_contract.py tests/test_dashboard_custom_card_detection.py -v --tb=line` → passed (27/27)

- 2026-02-27: Completed Phase R4 sync automation and CI parity slice.
  - Added deterministic canonical-to-vendored sync and parity utility:
    - `utils/sync_dashboard_assets.py`
    - sync command: `python utils/sync_dashboard_assets.py`
    - parity command: `python utils/sync_dashboard_assets.py --check`
  - Added CI parity enforcement workflow:
    - `.github/workflows/dashboard-asset-parity.yaml`
    - checks vendored assets against `ccpk1/ChoreOps-Dashboards` on dashboard-related PR changes.
  - Added contributor workflow documentation in:
    - `docs/DASHBOARD_TEMPLATE_GUIDE.md`
  - Validation evidence:
    - `python utils/sync_dashboard_assets.py` → passed
    - `python utils/sync_dashboard_assets.py --check` → passed
    - `./utils/quick_lint.sh --fix` → passed

- 2026-02-27: Dashboard provenance constant taxonomy alignment cleanup.
  - Renamed provenance keys from `ATTR_DASHBOARD_PROVENANCE*` to dashboard metadata keys:
    - `DASHBOARD_CONFIG_KEY_PROVENANCE`
    - `DASHBOARD_PROVENANCE_KEY_*`
  - Moved these constants under Dashboard Generator constants in `const.py` to reflect non-attribute usage.
  - Updated runtime/test call sites to consume the new names.
  - Validation evidence:
    - `./utils/quick_lint.sh --fix` → passed
    - `python -m pytest tests/test_dashboard_provenance_contract.py tests/test_options_flow_dashboard_release_selection.py tests/test_dashboard_manifest_runtime_policy.py -v --tb=line` → passed (24/24)

- 2026-02-27: Completed Phase R3 manifest/runtime policy enforcement slice.
  - Runtime policy behavior shipped:
    - lifecycle-aware template selectability is enforced during dashboard create/update.
    - dependency contract behavior is enforced (`required` blocks, `recommended` warns).
    - deterministic local+remote manifest merge helpers are active with invalid-record isolation.
  - Type-safety and runtime guardrail fixes:
    - hardened nullable HA user-name normalization in auth helper matching.
    - resolved selector option typing for weekday multi-select schemas.
    - tightened service approve flow ID resolution guard (`chore_id` must resolve).
  - Validation evidence:
    - `./utils/quick_lint.sh --fix` → passed
    - `mypy custom_components/choreops/` → passed (0 errors)
    - `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py tests/test_dashboard_manifest_runtime_policy.py tests/test_options_flow_dashboard_release_selection.py -v --tb=line` → passed (25/25)

- 2026-02-27: Completed Phase R2 template contract migration slice.
  - Canonical template migration (`choreops-dashboards/templates`):
    - migrated user templates from legacy `assignee.*` substitutions to `user.*`.
    - migrated helper lookup filtering from `attributes.user_name` to `attributes.dashboard_lookup_key`.
    - injected `user.user_id` and `integration.entry_id` context usage in user template lookup blocks.
  - Runtime plumbing for identity substitution contract:
    - `build_dashboard_context` now injects `user` and `integration` context payloads.
    - options flow now passes selected assignee ID mapping to builder create/update paths.
  - Canonical-to-vendored sync:
    - mirrored updated canonical user templates into `custom_components/choreops/dashboards/templates`.
  - Validation evidence:
    - `runTests` on
      - `tests/test_options_flow_dashboard_release_selection.py`
      - `tests/test_dashboard_provenance_contract.py`
      - `tests/test_dashboard_custom_card_detection.py`
        → passed (22/22)
    - `./utils/quick_lint.sh --fix` → passed

- 2026-02-27: Completed Phase R1 contract plumbing and release parity slice.
  - Create/update flow parity:
    - `options_flow` now forwards `pinned_release_tag` and `include_prereleases` for create and update paths.
  - Helper identity contract:
    - dashboard helper sensor now exposes `integration_entry_id`, `user_id`, and `dashboard_lookup_key`.
  - Provenance metadata:
    - dashboard builder now stamps `dashboard_provenance` into generated dashboard config with template/source/ref/time and prerelease flag.
  - Added focused tests:
    - `tests/test_dashboard_provenance_contract.py`
    - extended `tests/test_options_flow_dashboard_release_selection.py` with create-flow release parity assertion.
  - Validation evidence:
    - `python -m pytest tests/test_dashboard_provenance_contract.py tests/test_options_flow_dashboard_release_selection.py -k "create_passes_release_parity_args_to_builder or dashboard_helper_includes_lookup_identity_contract or build_multi_view_dashboard_stamps_provenance" -v --tb=line` → passed (3/3)
    - `./utils/quick_lint.sh --fix` → passed

- 2026-02-27: Implemented initial dependency declaration slice.
  - Added `dependencies.required[]` / `dependencies.recommended[]` to template records in:
    - `choreops-dashboards/dashboard_registry.json`
    - `custom_components/choreops/dashboards/dashboard_registry.json`
  - Added contract tests in `tests/test_dashboard_manifest_dependencies_contract.py` to ensure:
    - dependency fields exist with valid `ha-card:*` IDs,
    - manifest required dependencies cover all `custom:*` cards used in template YAML.
  - Validation evidence:
    - `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py -v --tb=line` → passed
    - `./utils/quick_lint.sh --fix` → passed (ruff/mypy/boundary checks)

- 2026-02-27: Implemented dependency enforcement placement refactor (post-template-selection).
  - Reused and extended dashboard helper card detection utilities to evaluate manifest dependency IDs for selected templates.
  - Moved dependency evaluation into dashboard configure flow after template IDs are known.
  - Enforced behavior:
    - missing `required` dependencies block generation,
    - missing `recommended` dependencies warn and allow generation.
  - Added focused options-flow coverage for required-block and recommended-continue paths.
  - Validation evidence:
    - `python -m pytest tests/test_options_flow_dashboard_release_selection.py -k "missing_required_template_dependencies or only_recommended_dependencies_missing" -v --tb=line` → passed
    - `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py tests/test_options_flow_dashboard_release_selection.py -k "dashboard_manifest_dependencies_contract or missing_required_template_dependencies or only_recommended_dependencies_missing" -v --tb=line` → passed
    - `./utils/quick_lint.sh --fix` → passed

## Audit matrix (standards vs current implementation)

| Area                                | Standards reference        | Current status              | Gap                                                                                                      |
| ----------------------------------- | -------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------- |
| Template identity naming            | D1, section 4              | Mostly aligned (`*-v1` IDs) | Complete after sync, maintain via CI parity                                                              |
| Manifest required contract fields   | section 3                  | Complete                    | Runtime contract fields validated and covered by manifest contract tests                                 |
| Remote/local manifest merge         | D3, section 5.5.1          | Complete                    | Deterministic merge + invalid-remote-record isolation implemented and tested                             |
| Dependency contract behavior        | D4, section 3 + 5.5.5      | Complete                    | `required` blocks and `recommended` warns are enforced in selection/generation path                      |
| Lifecycle selection behavior        | section 5.5.2              | Complete                    | Non-selectable lifecycle templates are filtered/blocked consistently in runtime options flow             |
| Helper lookup contract              | D11, section 5.2           | Partial                     | Admin templates use entry-scoped lookup; assignee templates still rely on name-based discovery           |
| Lookup optimization key             | D12, section 5.2           | Missing/partial             | `dashboard_lookup_key` and helper identity payload not fully stamped/exposed                             |
| Error handling UX ladder            | D13                        | Partial                     | Warning-card pattern exists, but not fully standardized around D11/D12 identity checks for all templates |
| Template preference docs model      | D14                        | Mostly aligned              | Keep docs + metadata parity checks and validation gates                                                  |
| Release/channel policy              | D16                        | Partial                     | Update flow supports release selection; create flow does not consistently pass pinned/prerelease options |
| Source-of-truth sync topology       | Phase 0 standards          | Complete                    | Canonical-to-vendored sync tool and CI parity gate are active                                            |
| Troubleshooting provenance metadata | runtime diagnostics intent | Missing                     | Generated dashboards do not stamp template source/version/ref metadata contract                          |
| Substitution whitelist contract     | D8 + section 5.1           | Partial                     | user-facing templates still use legacy `assignee.*` conventions in many blocks                           |
| Caching/refresh/rate-limit behavior | section 5.5.3/5.5.4        | Partial                     | No shared TTL cache for release/manifest/translation remote payloads                                     |

## Canonical template update and sync plan (single source of truth)

### Source of truth

- All template authoring changes must be made in:
  - `/workspaces/choreops-dashboards/templates/`
  - `/workspaces/choreops-dashboards/translations/`
  - `/workspaces/choreops-dashboards/preferences/`
  - `/workspaces/choreops-dashboards/dashboard_registry.json`

### Vendored runtime mirror

- Runtime copy in integration repo remains read-only from an authoring perspective:
  - `/workspaces/choreops/custom_components/choreops/dashboards/`

### Allowed update flow

1. Edit canonical files in `choreops-dashboards`.
2. Validate canonical repo artifacts (`dashboard_registry.json`, template parsing, translation naming).
3. Run sync tooling from `choreops` to mirror canonical assets into vendored runtime path.
4. Run parity check (file list + content hash/byte comparison) as a required gate.
5. Run integration tests in `choreops`.

### Guardrails

- Do not hand-edit vendored template YAML in `custom_components/choreops/dashboards/templates/`.
- Any PR with vendored changes must include either:
  - corresponding canonical changes from `choreops-dashboards`, or
  - an explicit sync-tool-generated artifact update.

## Full gap list (actionable)

1. Complete assignee-template migration from name-based helper discovery to D11/D12 identity lookup (`integration.entry_id` + `user.user_id` + `dashboard_lookup_key`).
2. Add helper sensor identity attributes required by D11/D12 (`integration_entry_id`, `user_id`, `dashboard_lookup_key`) and test shape.
3. Make create/update generator paths symmetric for `pinned_release_tag` and `include_prereleases` handling.
4. Add dashboard provenance metadata stamping contract to generated config (template ID, source type, selected ref, generated timestamp, integration entry ID).
5. Expand manifest contract fields to ratified required schema and enforce validation.
6. Add explicit per-template custom-card dependency declarations to manifest (`dependencies.required[]`, `dependencies.recommended[]`) so generator checks have canonical input.
7. Implement dependency behavior contract in runtime selection/generation (required block vs recommended warn).
8. Enforce lifecycle-state selection behavior (`active`, `deprecated`, `archived`) consistently.
9. Implement remote manifest merge contract with deterministic precedence/order and invalid-record isolation.
10. Add shared remote payload cache policy (TTL, stale-safe fallback, rate-limit resilience) for release/manifest/translation fetches.
11. Migrate user-facing substitution references from legacy `assignee.*` to ratified `user.*` contract and maintain whitelist.
12. Implement/finish sync automation command and CI parity gate for canonical -> vendored dashboard assets.
13. Add end-to-end tests proving provenance, lookup, release parity, dependency behavior, lifecycle behavior, and sync parity.

## Detailed remediation execution plan

### Phase R1 — Contract plumbing and release parity

Scope:

- Pass release parameters consistently in both create/update flows.
- Add helper identity attributes and lookup key in dashboard helper sensor payload.
- Introduce provenance metadata model in builder output.

Validation:

- `pytest tests/test_options_flow_dashboard_release_selection.py -v`
- Targeted tests for helper attribute payload and dashboard metadata stamping.
- `./utils/quick_lint.sh --fix`

Exit criteria:

- Create and update flows both honor pinned/prerelease configuration.
- Dashboard helper payload includes required identity attributes.
- Generated dashboard config contains provenance metadata.

### Phase R2 — Template contract migration

Scope:

- Update canonical templates in `choreops-dashboards` to D11/D12 identity lookup pattern and `user.*` substitution contract.
- Standardize D13 warning-card ladder checks around identity lookup in all templates.

Validation:

- Template lint/parse checks.
- Focused template contract tests in `choreops` after vendoring.
- Parity check canonical vs vendored paths.

Exit criteria:

- No remaining name-only helper lookup blocks in shipped templates.
- No remaining user-facing `assignee.*` substitution contract in runtime templates.

### Phase R3 — Manifest/runtime policy enforcement

Status: Completed (2026-02-27)

Scope:

- Expand manifest schema fields and validation.
- Populate per-template custom-card dependencies in canonical manifest records.
- Implement dependency + lifecycle filtering behavior.
- Implement local+remote manifest merge semantics with deterministic order.

Validation:

- New/updated contract tests for manifest validation and selection pipeline.
- Negative tests for malformed/invalid remote records.
- `mypy custom_components/choreops/`

Exit criteria:

- Runtime behavior matches D3/D4/5.5 contract for merge, filtering, dependency declarations, and dependency handling.

### Phase R4 — Sync automation and CI parity

Status: Completed (2026-02-27)

Scope:

- Add/finish sync tool and parity checker.
- Add CI gate that fails when vendored mirror drifts from canonical dashboard repo assets.
- Document contributor workflow.

Validation:

- Run sync command locally and verify deterministic output.
- Parity check shows no differences.
- CI workflow includes parity gate.

Exit criteria:

- Template update process is reproducible and enforced.
- No manual drift path between repos.

### Phase R5 — Full regression and closeout

Status: In progress (validation gates complete on 2026-02-27)

Scope:

- Run full validation suite for touched areas.
- Update in-process plan completion sections and evidence.

Validation gates:

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/`
- `python -m pytest tests/ -v --tb=line`

Exit criteria:

- All gap items marked complete with test evidence.
- Plan ready for owner approval and archival.

Current progress notes:

- Validation gates are complete and passing.
- Remaining closeout work is documentation reconciliation (`Audit matrix` and `Full gap list`) and owner approval/archive handoff.

## Deliverable ownership

- **Canonical dashboard content changes:** `choreops-dashboards`
- **Runtime behavior, options flow, helper sensors, tests, sync tooling:** `choreops`
- **Plan and architecture evidence updates:** `choreops/docs/in-process/`
