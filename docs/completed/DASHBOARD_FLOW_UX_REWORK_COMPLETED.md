# Initiative plan

## Initiative snapshot

- **Name / Code**: Dashboard generator hard-fork implementation / DASHBOARD-GENERATOR-HARDFORK
- **Target release / milestone**: Next dashboard-generator release window (hard fork)
- **Owner / driver(s)**: ChoreOps maintainers
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                                | Description                                                                | % complete | Quick notes                                                              |
| ------------------------------------------- | -------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| Phase 0 – Hard-fork guardrails              | Lock no-compatibility boundaries and scope                                 | 100%       | Compatibility code is explicitly out of scope                            |
| Phase 1 – Data contracts                    | Define registry/provenance contracts and release metadata                  | 100%       | `release_version` decision locked                                        |
| Phase 2 – Flow redesign                     | Implement owner-approved 4-step UX                                         | 100%       | 4-step behavior implemented and validated                                |
| Phase 3 – Asset pipeline                    | Release asset fetch/caching/error routing                                  | 100%       | Step-1 prep, session cache, and failure routing validated                |
| Phase 4 – Update UX enhancements            | Friendly dashboard labels + icon default preload                           | 100%       | Friendly labels + duplicate disambiguation + icon preload validated      |
| Phase 5 – Optimization cleanup              | Remove unnecessary code/paths/constants                                    | 100%       | Dead template-details path/constants/strings removed; full gates green   |
| Phase 5B – Cohesive processing architecture | Replace MVP patchwork with single authoritative release execution pipeline | 100%       | Cohesive release pipeline and dependency-review UX refinements validated |
| Phase 6 – Platinum verification             | Lint/type/test/docs gates and release readiness                            | 100%       | Full quality gates + TODO/compat sweep complete; owner sign-off recorded |

1. **Key objective** – Deliver first-time hard-fork dashboard generator implementation with no backward compatibility code, strict adherence to development standards, and platinum-level quality gates.
2. **Summary of recent work** – Phase 5B completed, including cohesive release application behavior and dependency-review UX hardening.
3. **Next steps (short term)** – Archived to `docs/completed`.
4. **Risks / blockers** – Network fetch variability, possible dead-code residue from old flow variants, and scope creep during refactor.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/QUALITY_REFERENCE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `tests/AGENT_TESTING_USAGE_GUIDE.md`
   - `custom_components/choreops/options_flow.py`
   - `custom_components/choreops/helpers/dashboard_helpers.py`
   - `custom_components/choreops/helpers/dashboard_builder.py`
   - `choreops-dashboards/dashboard_registry.json`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Hard fork: no compatibility code or compatibility branches.
     - Registry contract adds top-level `release_version`; top-level `schema_version` remains.
     - Fetch selected release assets on Step 1 submit; failures return to Step 1 with actionable local/current guidance.
     - Step 3 is shared between create/update.
     - Step 4 always shows dependency review and controls submit routing.
     - Update selector must be friendly-name-first; URL path is internal value and only shown for disambiguation.
     - Update flow preloads icon default from selected dashboard.

- **Completion confirmation**: `[x]` All phase gates and platinum checks pass before owner sign-off.

## Tracking expectations

- **Summary upkeep**: Update this file after each phase completion and after each failed gate with remediation notes.
- **Detailed tracking**: Every phase below includes execution tasks and a mandatory verification gate.

## Hard-fork constraints (non-negotiable)

1. No compatibility adapters, dual-read paths, or fallback parsers for previous dashboard generator contracts.
2. No legacy prerelease toggle path.
3. No legacy metadata-only inference when explicit `release_version` is expected.
4. No dead constants/methods retained "just in case".
5. No `# type: ignore`/`noqa` suppressions unless no compliant alternative exists and owner approves.

## Detailed phase tracking

### Phase 0 – Hard-fork guardrails (complete)

- **Goal**: Freeze scope and remove ambiguity about compatibility behavior.
- **Steps / detailed work items**
  1. `[x]` Declare hard-fork rule set in this plan.
  2. `[x]` Lock four-step UX contract and update-flow enhancements.
  3. `[x]` Lock release metadata direction (`release_version` + `schema_version`).
- **Verification gate**
  - `[x]` Plan explicitly states no compatibility code allowed.

### Phase 1 – Data contracts (complete, design)

- **Goal**: Define deterministic data contracts for registry/provenance/update comparison.
- **Steps / detailed work items**
  1. `[x]` Define top-level registry keys: `schema_version`, `release_version`, `repo`, `templates`, etc.
  2. `[x]` Define provenance requirements to support direct local-vs-online comparisons.
  3. `[x]` Define hard-fail behavior when required selected-release contract data is unavailable.
- **Planned file targets**
  - `choreops-dashboards/dashboard_registry.json`
  - `choreops-dashboards/utils/release_sanity.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/helpers/dashboard_builder.py`
  - `custom_components/choreops/const.py`
- **Verification gate**
  - `[x]` Contract decisions are documented and implementable without compatibility branching.

### Phase 2 – Flow redesign implementation (4-step contract) (complete)

- **Goal**: Implement the owner-approved UX exactly and only.
- **Locked step sequence**
  1. Step 1: required mode + template source/release selection
  2. Step 2: create-name or update-target selection
  3. Step 3: shared configure step (create/update), with template source controls removed
  4. Step 4: always-show dependency review + submit routing
- **Steps / detailed work items**
  1. `[x]` Refactor action routing to enforce Step 1 always first for create/update.
  2. `[x]` Keep Step 2 target logic explicit and isolated (name vs selected dashboard).
  3. `[x]` Ensure Step 3 schema is identical for create/update except context defaults.
  4. `[x]` Implement Step 4 submit routing:
  - deps met → execute + return Step 1
  - deps missing + no override → route Step 3
  - deps missing + override → execute with acknowledgment
  5. `[x]` Ensure warning copy explicitly states dashboards may not function correctly without required cards.
- **Planned file targets**
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/translations/en.json`
- **Verification gate**
  - `[x]` Flow path tests pass for create and update with deterministic transitions.
  - `[x]` Manual run confirms no hidden step branching.

### Phase 3 – Release asset pipeline (templates/translations/preferences) (complete)

- **Goal**: Provide deterministic release asset preparation with clear latency/error UX.
- **Steps / detailed work items**
  1. `[x]` Trigger selected-release asset preparation on Step 1 submit.
  2. `[x]` Fetch required scope: registry definitions, templates, translations, preferences docs.
  3. `[x]` Implement flow-session cache model (single-session reuse, deterministic invalidation).
  4. `[x]` Add progress UX during fetch; no pre-warning on Step 1.
  5. `[x]` On fetch failure: return Step 1 with actionable error and local/current guidance.
  6. `[x]` Guarantee preferences asset availability by Step 4.
- **Planned file targets**
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/helpers/dashboard_builder.py`
  - `custom_components/choreops/options_flow.py`
- **Verification gate**
  - `[x]` Success path fetches once per flow session for same selection.
  - `[x]` Failure path reliably returns to Step 1 with clear message.
  - `[x]` No silent fallback to stale remote assets.

### Phase 4 – Update UX enhancements (complete)

- **Goal**: Improve update-target usability and preserve existing dashboard visuals.
- **Steps / detailed work items**
  1. `[x]` Update selector options to show friendly-name-first labels.
  2. `[x]` Keep URL path as internal value for stable selection behavior.
  3. `[x]` Show URL path only when friendly titles collide.
  4. `[x]` Read selected dashboard config and preload existing icon into Step 3 default.
- **Planned file targets**
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/options_flow.py`
  - related tests under `tests/`
- **Verification gate**
  - `[x]` Update dropdown shows friendly names in normal cases.
  - `[x]` Duplicate-title case disambiguates correctly.
  - `[x]` Step 3 icon default matches selected dashboard icon.

### Phase 5 – Optimization and dead-code removal (mandatory)

- **Goal**: Ensure implementation is lean, optimized, and free of unnecessary code.
- **Steps / detailed work items**
  1. `[x]` Run symbol usage review for dashboard generator constants/methods and remove unused paths.
  2. `[x]` Remove superseded flow constants/fields and unreachable branches.
  3. `[x]` Remove stale docs/translations strings tied to removed behavior.
  4. `[x]` Ensure no compatibility-only code remains.
  5. `[x]` Verify no redundant network calls or repeated discovery without cache purpose.
- **Verification gate**
  - `[x]` Ruff/mypy clean after removals.
  - `[x]` Code usage audit shows no dead dashboard-generator symbols retained intentionally.
  - `[x]` Performance/log traces confirm no avoidable duplicate fetches.

### Phase 5B – Cohesive processing architecture (platinum hardening)

- **Goal**: Replace incremental MVP-era stitching with one seamless, deterministic processing architecture that guarantees the selected release is the executed release (or fails explicitly).
- **Core architectural principle**
  - **Single authoritative release context** per flow session:
    - `requested_release_selection` (what user picked)
    - `effective_release_ref` (exact resolved tag/ref used for execution)
    - `resolution_reason` (why/when selection was transformed)
    - `execution_source` (remote_release / local_fallback / mixed-forbidden)
  - This context is created once in Step 1 and consumed unchanged by Step 3 execution.

- **Processing contracts (non-negotiable)**
  1. **Explicit release tag selected**:
     - Must execute against that exact tag
     - Must not silently downgrade to latest-compatible or local template
     - On fetch miss/failure, flow returns actionable error (hard fail)
  2. **Latest stable / latest compatible selected**:
     - Resolve once in Step 1 to a concrete `effective_release_ref`
     - Step 3 uses that exact concrete ref, not dynamic re-resolution
  3. **Current installed selected**:
     - Uses local bundled release ref deterministically
     - If local release metadata absent, explicit fail path with corrective message

- **Detailed implementation steps / work items**
  1. `[x]` Introduce `DashboardReleaseExecutionContext` as the single handoff object.
     - Files: `custom_components/choreops/helpers/dashboard_helpers.py`, `custom_components/choreops/options_flow.py`
     - Include typed fields for request, effective ref, policy flags, and diagnostics.
  2. `[x]` Unify Step 1 prep and Step 3 execution to consume the same prepared template assets.
     - Remove duplicate release-resolution/fetch logic from execution path.
     - Files: `custom_components/choreops/options_flow.py`, `custom_components/choreops/helpers/dashboard_builder.py`
  3. `[x]` Enforce strict explicit-pin semantics in builder fetch layer.
     - Explicit pin failure must fail fast (no local silent fallback).
     - Automatic modes may fallback only under declared policy and with surfaced status.
  4. `[x]` Make fallback behavior policy-driven and visible.
     - Add explicit state/message keys for: `explicit_pin_failed`, `auto_fallback_used`, `resolved_effective_ref`.
     - Files: `custom_components/choreops/translations/en.json`, `custom_components/choreops/options_flow.py`
  5. `[x]` Add provenance integrity checks post-render.
     - Verify generated dashboard provenance contains `requested_release_selection` and `effective_release_ref` and they match contract.
     - Files: `custom_components/choreops/helpers/dashboard_builder.py`
  6. `[x]` Normalize release-tag parsing policy and define accepted tag grammar envelope.
     - Decide and codify handling for optional `v`-prefixed tags.
     - Files: `custom_components/choreops/const.py`, `custom_components/choreops/helpers/dashboard_builder.py`, `choreops-dashboards/utils/release_sanity.py`
  7. `[x]` Add contract tests that validate actual executed source, not just argument forwarding.
     - Files: `tests/test_dashboard_template_release_resolution.py`, `tests/test_options_flow_dashboard_release_selection.py`, `tests/test_dashboard_builder_release_fetch.py`
     - Include negative cases where explicit pin is unavailable and must fail.
  8. `[x]` Add runtime observability checkpoints.
     - Structured debug logs with one correlation id per dashboard generation attempt.
     - Log context: requested selection, effective ref, fallback decision, final provenance refs.

- **Trap coverage matrix (must be explicitly closed)**
  - **Trap A**: Step 1 fetch succeeds but Step 3 re-fetches different content
    - Mitigation: shared `DashboardReleaseExecutionContext` + prepared asset consumption only
  - **Trap B**: explicit tag appears selected but local fallback renders old templates
    - Mitigation: strict explicit-pin hard-fail semantics
  - **Trap C**: prerelease tags filtered during execution despite being explicitly selected
    - Mitigation: explicit-pin bypass of prerelease filtering and parser-consistent acceptance
  - **Trap D**: dropdown appears translated but option labels are hardcoded
    - Mitigation: translation-key-backed fixed options; dynamic tags remain literal tag values
  - **Trap E**: regression masked by permissive tests
    - Mitigation: source-integrity assertions + provenance assertions + negative-path tests

- **Verification gate (Phase 5B exit criteria)**
  - `[x]` One authoritative release context is used from Step 1 through final render.
  - `[x]` Explicit release selection either renders that exact release or fails explicitly.
  - `[x]` No silent local fallback occurs for explicit release mode.
  - `[x]` Provenance records requested and effective refs and passes contract assertions.
  - `[x]` Focused suites pass with new negative/strict tests:
    - `tests/test_options_flow_dashboard_release_selection.py`
    - `tests/test_dashboard_template_release_resolution.py`
    - `tests/test_dashboard_builder_release_fetch.py`
  - `[x]` Manual walkthrough confirms cohesive behavior in create + update flows.

### Phase 6 – Platinum quality validation and sign-off

- **Goal**: Enforce project standards and quality scale expectations before completion.
- **Steps / detailed work items**
  1. `[x]` Standards compliance review against `docs/DEVELOPMENT_STANDARDS.md`.
  2. `[x]` Run full quality gates in required order:
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/choreops/`
     - `python -m pytest tests/ -v --tb=line`
  3. `[x]` Run targeted dashboard generator suites (options-flow + release resolution + builder fetch tests).
  4. `[x]` Confirm docs updated (architecture/development/release notes if contract changed).
  5. `[x]` Confirm no compatibility code and no unresolved TODO placeholders.
- **Verification gate**
  - `[x]` All commands pass with no skipped required checks.
  - `[x]` Manual UX walk-through matches locked four-step contract exactly.
  - `[x]` Owner approval received after evidence review.

## Builder execution playbook (code-level)

Use this section as the exact implementation sequence. Do not reorder unless a blocker requires it.

### Execution order

1. Contracts and constants
2. Step routing and flow state
3. Release asset fetch stage
4. Step 3 schema parity and defaults
5. Step 4 dependency review behavior
6. Update-target UX enhancements
7. Dead-code and constant cleanup
8. Full validation and docs update

### 1) Contracts and constants

- **Files to change**
  - `choreops-dashboards/dashboard_registry.json`
  - `choreops-dashboards/utils/release_sanity.py`
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/helpers/dashboard_builder.py`
- **Required code-level changes**
  - Add top-level `release_version` in registry JSON; keep top-level `schema_version` unchanged.
  - Update registry sanity checks to require `release_version` and validate version format.
  - Ensure constants referenced by options flow remain single-source-of-truth for dashboard step IDs and inputs:
    - `OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR`
    - `OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE`
    - `OPTIONS_FLOW_STEP_DASHBOARD_MISSING_DEPENDENCIES`
    - `CFOF_DASHBOARD_INPUT_*` fields relevant to release selection, icon, update selection, dependency bypass.
  - Expand provenance payload in `_build_dashboard_provenance()` for explicit comparison fields (local/selected/effective release references).
- **Common traps to avoid**
  - Do not overload `schema_version` to represent release identity.
  - Do not retain old inferred comparison logic once explicit fields exist.

### 2) Step routing and flow state

- **Files to change**
  - `custom_components/choreops/options_flow.py`
- **Methods to edit**
  - `async_step_dashboard_generator`
  - `async_step_dashboard_create`
  - `async_step_dashboard_update_select`
  - `async_step_dashboard_configure`
  - `async_step_dashboard_missing_dependencies`
- **Required code-level changes**
  - Enforce 4-step progression:
    - Step 1: mode + release selection only
    - Step 2: create name or update target selection
    - Step 3: shared configure
    - Step 4: dependency review
  - Make Step 3 shared for create/update by using one schema builder call path and context defaults only.
  - Remove template-source controls from Step 3 schema inputs and state writebacks.
- **Common traps to avoid**
  - Avoid hidden mode-specific branches that mutate Step 3 field availability differently for create vs update.
  - Avoid re-introducing prerelease toggle controls in Step 3.

### 3) Release asset fetch stage (on Step 1 submit)

- **Files to change**
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/helpers/dashboard_builder.py`
- **Methods to edit/use**
  - `discover_compatible_dashboard_release_tags()`
  - `fetch_remote_manifest_template_definitions()`
  - `fetch_dashboard_template()`
- **Required code-level changes**
  - Add a deterministic asset preparation stage after Step 1 submit.
  - Fetch/prepare all required selected-release assets: registry definitions, templates, translations, preferences markdown.
  - Add flow-session cache object/state for the selected release and fetched assets.
  - On failure: route to Step 1 with explicit, actionable message and local/current guidance.
- **Common traps to avoid**
  - Do not fetch in loops per template if one fetch stage can prepare all needed assets.
  - Do not silently continue with stale/partial remote assets.

### 4) Step 3 schema parity and defaults

- **Files to change**
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/options_flow.py`
- **Methods to edit**
  - `build_dashboard_configure_schema()`
  - `async_step_dashboard_configure`
- **Required code-level changes**
  - Keep one configure schema path for both create/update.
  - Preserve shared fields and admin mode logic.
  - Ensure update-specific defaults are injected via state only (for example icon default after selection).
- **Common traps to avoid**
  - Duplicating Step 3 schemas for create and update.
  - Divergent validation behavior between modes.

### 5) Step 4 dependency review behavior

- **Files to change**
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/translations/en.json`
- **Methods/constants to edit**
  - `async_step_dashboard_missing_dependencies`
  - `build_dashboard_missing_dependencies_schema()`
  - `CFOF_DASHBOARD_INPUT_DEPENDENCY_BYPASS`
  - `TRANS_KEY_CFOF_DASHBOARD_DEPENDENCY_ACK_REQUIRED`
- **Required code-level changes**
  - Make Step 4 always present before execution.
  - Implement submit routing rules exactly:
    - deps satisfied → execute + return Step 1
    - deps missing + bypass off → route Step 3
    - deps missing + bypass on → execute with warning acknowledged
  - Ensure warning copy explicitly states required cards are necessary for correct dashboard behavior.
- **Common traps to avoid**
  - Allowing bypass to skip warning acknowledgment.
  - Allowing execution with missing required deps without explicit user choice.

### 6) Update-target UX enhancements

- **Files to change**
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/options_flow.py`
- **Methods to edit**
  - `get_existing_choreops_dashboards()`
  - `build_dashboard_update_selection_schema()`
  - update-path setup in `async_step_dashboard_update_select` and `async_step_dashboard_configure`
- **Required code-level changes**
  - Friendly-name-first labels in update selector; URL path as internal `value`.
  - Only append URL path to label when duplicate friendly names need disambiguation.
  - On dashboard selection in update path, read selected dashboard icon and set Step 3 icon default state.
- **Common traps to avoid**
  - Using URL path as user-facing primary label.
  - Overwriting user-modified icon defaults after initial preload.

### 7) Dead-code and constant cleanup (hard-fork enforcement)

- **Files to audit**
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/helpers/dashboard_builder.py`
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/translations/en.json`
- **Required code-level cleanup**
  - Remove superseded option paths and constants tied to deprecated flow behavior.
  - Remove stale translation keys/messages that are no longer referenced.
  - Remove unreachable helper branches and legacy comments tied to old flow design.
- **Common traps to avoid**
  - Leaving dead constants that still pass lint but confuse future maintenance.
  - Keeping compatibility aliases “for safety”.

### 8) Validation protocol (must pass in sequence)

1. Focused tests for each phase before moving to next phase.
2. Full quality gates at end:
   - `./utils/quick_lint.sh --fix`
   - `mypy custom_components/choreops/`
   - `python -m pytest tests/ -v --tb=line`
3. Manual walkthrough:
   - create flow end-to-end
   - update flow end-to-end
   - release fetch success path
   - release fetch failure path back to Step 1
   - dependency missing path (with and without bypass)

## Builder trap list (do not skip)

1. **Step drift**: Step numbering must remain 1→2→3→4 with no hidden optional branch replacing Step 4.
2. **Schema drift**: Step 3 create/update must not diverge into separate schemas.
3. **Metadata drift**: `release_version` is not optional once hard fork is active.
4. **Fallback drift**: On release-fetch error, do not route forward; always return to Step 1.
5. **UX drift**: Update selector label must be human-friendly first, URL only as disambiguation.
6. **Icon drift**: Update icon preload happens at selection time and is user-overridable afterward.
7. **Quality drift**: No phase is complete without its verification gate evidence.

## Implementation verification matrix (builder-facing)

- **Design fidelity checks**
  - Step sequence must match contract exactly.
  - Step 3 must be shared for create and update (context default differences only).
  - Step 4 must always render and gate submit routing.
- **Data contract checks**
  - Registry contains both top-level `schema_version` and top-level `release_version`.
  - Provenance contains explicit fields for local-vs-online comparison.
- **Error-handling checks**
  - Release fetch failures route to Step 1 with actionable guidance.
  - Missing required dependencies show explicit warning + override behavior.
- **Optimization checks**
  - No duplicate release discovery/fetch cycles within same step transition unless required.
  - No dead methods/constants from superseded flow designs.

## Testing & validation

- **Test strategy sources**
  - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
  - `tests/AGENT_TESTING_USAGE_GUIDE.md`
- **Mandatory completion gates**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- **Focused suites (minimum)**
  - `tests/test_options_flow_dashboard_release_selection.py`
  - `tests/test_dashboard_template_release_resolution.py`
  - `tests/test_dashboard_builder_release_fetch.py`
  - Add/adjust tests for friendly labels + icon preload + Step 1 error-return behavior

## Notes & follow-up

- This initiative is a hard-fork first implementation: keep architecture clean and forward-only.
- Builder decisions that change UX contract are not allowed without explicit owner approval.
- Any proposed deviation must be documented in this plan before implementation.

### Acceptance criteria for final design sign-off

- `[ ]` Four-step flow behavior matches locked contract for create and update.
- `[ ]` Step 3 is shared for create/update with no divergence in logic.
- `[ ]` Step 4 always shows and controls submit routing deterministically.
- `[ ]` Registry includes top-level `release_version` and top-level `schema_version`.
- `[ ]` Selected online release fetches templates/translations/preferences and handles errors by routing to Step 1.
- `[ ]` Update selector is friendly-name-first with URL disambiguation only when needed.
- `[ ]` Update icon default is preloaded from selected dashboard.
- `[ ]` No compatibility code paths remain.
- `[ ]` Unnecessary code/constants/methods are removed and validated.
- `[ ]` All platinum-quality verification gates pass.
