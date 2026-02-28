# Initiative Plan Template

## Initiative snapshot

- **Name / Code**: Dashboard registry architecture standards and operating model (`DASHBOARD_REGISTRY_GENERATION`)
- **Target release / milestone**: Architecture ratification for 0.5.0-beta.5 delivery window
- **Owner / driver(s)**: ChoreOps maintainers (Architecture, Integration, DX)
- **Status**: Complete (execution tracking transitioned to `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_GAP_REMEDIATION_PLAN.md`)

## Summary & immediate steps

| Phase / Step                                | Description                                                                      | % complete | Quick notes                                                   |
| ------------------------------------------- | -------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------- |
| Phase 1 – Standards and guardrails          | Define architecture principles, scope boundaries, and non-negotiable standards   | 100%       | Principles, boundaries, guarantees, observability ratified    |
| Phase 2 – Registry contract and taxonomy    | Define manifest schema, naming model, dependency contract, and versioning rules  | 100%       | Manifest v1 contract and taxonomy checklist fully ratified    |
| Phase 3 – Runtime resolution model          | Define deterministic discovery/loading/merge behavior with offline guarantees    | 100%       | Merge, selection, caching, failures, and dependency UX frozen |
| Phase 4 – Contribution and operations model | Define submission workflow, review gates, release sync, and lifecycle governance | 100%       | Submission, CI gates, vendoring sync, and lifecycle finalized |

1. **Key objective** – Define an architecture-first dashboard ecosystem that scales across templates, contributors, and releases without inheriting proof-of-concept constraints.
2. **Summary of recent work**
   - Established dual-repo direction (`ccpk1/choreops` + `ccpk1/choreops-dashboards`) and vendoring requirement for HACS-safe fallback.
   - Created initial dashboards repository scaffold (`README.md`, `LICENSE`, `.gitignore`, baseline `dashboard_registry.json`).
   - Drafted initial implementation-biased plan and now pivoting to standards-first architecture and decision framework.
3. **Next steps (short term)**
   - Execution and remaining closeout validation moved to:
   - `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_GAP_REMEDIATION_PLAN.md` (Phase R1-R5 tracking)
   - This parent initiative plan remains the architectural decision record and completion summary.
4. **Risks / blockers**
   - Premature coding before standards ratification can cement poor contracts.
   - Contract drift risk between integration and registry repos without schema/version policy.
   - Submission quality variance without strict naming, metadata, and review gates.
5. **References** – Link to key resources:
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `docs/RELEASE_CHECKLIST.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
   - `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_GAP_REMEDIATION_PLAN.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Architecture must be registry-contract-first, not implementation-first.
     - Runtime behavior must be deterministic and offline-safe.
     - Template submission must be policy-driven with objective validation gates.
       - Dashboard registry remains template-focused; any future ChoreOps-specific custom cards live in separate card repositories.
   - D1 accepted with immutable kebab-case `template_id`; derive family key by stripping trailing `-v<major>` (no persisted `slug`).
     - Registry metadata is maintained in a single canonical manifest (no per-template manifests in v1).
       - D8 accepted: substitution fields are whitelist-only.
     - Localization source model is hybrid (local baseline + optional validated remote override).
     - Template text localization remains key-based via translation sensor payloads.
     - User-facing substitution contract uses `user.*` naming and must support multi-instance scoping via integration entry identifiers.
     - Dashboard helper lookup contract is accepted as attribute-scoped dynamic lookup only (no fallback modes).
   - D14 accepted: v1 template preference customization uses companion preference docs (no backend runtime preference engine).
   - D15 accepted: keep dashboard templates as canonical runtime units while allowing optional card-fragment authoring assets with explicit composition order metadata.
   - D16 accepted: define `choreops-dashboards` release/channel strategy for stable, beta, and dev artifact publication.
   - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Standards and guardrails

- **Goal**: Define the architecture “north star” and quality guardrails so implementation decisions remain consistent and scalable.
- **Steps / detailed work items**
  1. [x] Define architecture principles and anti-goals.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include principles: deterministic behavior, explicit contracts, compatibility by default, low cognitive load, and observability.
     - Status note: Covered by sections `1) Architecture principles` and `2) Explicit non-goals` in supporting standards.
  2. [x] Define explicit scope boundaries for this initiative.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_COMPLETED.md`
     - Clarify what is in scope (registry contract, discovery, submission, dependency model) and out of scope (new dashboard visual design system).
     - Status note: Scope boundaries are captured in initiative summary/objective language plus explicit non-goals in supporting standards.
  3. [x] Define operating modes and guarantees.
     - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, `docs/ARCHITECTURE.md`
     - Required guarantees: cold-start local fallback, non-blocking remote failure path, deterministic template selection.
     - Status note: Ratified under runtime source precedence, selection, cache policy, and failure matrix contracts.
  4. [x] Define observability standards.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Establish what must be logged/diagnosed (manifest source, selection reason, dependency validation outcomes).
     - Status note: Covered by the architecture principle "Observable behavior" and runtime diagnostics requirements.
  5. [x] Create architecture ratification checklist.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_COMPLETED.md`
     - Gate implementation start on approved standards decisions.
     - Status note: Completed under `Pre-build alignment gate` sections A-D with frozen acceptance criteria and proof artifacts.
  6. [x] Ratify custom-card boundary policy.
     - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, `choreops-dashboards/README.md`
     - Confirm that template registry does not host custom card source code.
     - Status note: Accepted as D7 and documented under `6.1) Custom card strategy`.
  7. [x] Ratify localization architecture.
     - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, `docs/ARCHITECTURE.md`
     - Decide local-only vs remote-only vs hybrid translation source and fallback rules.
     - Status note: D9/D10 accepted with hybrid source model and key-based localization contract documented in `6.2)`.
- **Key issues**
  - High risk of architecture drift without ratified standards.
  - Need one canonical place for decision history and rationale.

### Phase 2 – Registry contract and taxonomy

- **Goal**: Define the manifest as a strict, evolvable contract and standardize naming/organization so templates remain discoverable and maintainable at scale.
- **Steps / detailed work items**
  1.  [x] Define manifest schema v1 with required and optional fields.
  - Files: `choreops-dashboards/dashboard_registry.json` (spec target), `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
  - Define identity fields (`template_id`, `display_name`), semantics (`category`, `audience`), compatibility, dependencies, and lifecycle state.
  - Status note: Added explicit v1 optional fields and validation rules to standards, complementing required identity/compatibility/dependency/lifecycle contract definitions.
  2. [x] Define naming taxonomy and folder organization standards.
     - Files: `choreops-dashboards/README.md`, `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Establish canonical naming for template files, IDs, variants, and deprecation aliases.
  - Status note: Runtime/options now resolve template IDs and source paths from `dashboards/dashboard_registry.json`; hardcoded profile lists, selector option labels, and legacy style constants removed from helper/build/translation paths.
  3.  [x] Define schema evolution and compatibility policy.
  - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
  - Include semver strategy for manifest schema and backward-compatibility guarantees.
  - Status note: Ratified D2 policy with explicit `schema_version`, backward-compatible minor evolution, and breaking changes only on explicit major bumps.
  4.  [x] Define dependency contract model.
  - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
  - Formalize `required` vs `recommended` dependencies and machine-readable dependency identifiers.
  - Status note: Ratified dependency behavior contract: `required` blocks selection/generation with explicit reason; `recommended` warns but continues; dependency IDs are stable machine-readable keys.
  5.  [x] Define template lifecycle states.
  - Files: `choreops-dashboards/dashboard_registry.json`, `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
  - States: `active`, `deprecated`, `archived`, with migration hints for replaced templates.
  - Status note: Lifecycle semantics are ratified in standards and manifest template entries now declare explicit `lifecycle_state` (currently `active`).
  6.  [x] Define dependency identifiers for future ChoreOps-specific cards.
  - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
  - Ensure IDs map to separately versioned frontend card repositories.
  - Status note: Added namespace-scoped dependency ID guidance for future card packages, including stable ID rules and separate card-repo ownership boundaries.
  7.  [x] Define dashboard translation asset contract.
  - Files: `custom_components/choreops/dashboards/translations/` (target), `choreops-dashboards` registry docs
  - Standardize language file naming, schema metadata, and key-fallback behavior.
  - Status note: Ratified hybrid localization contract using local vendored baseline (`dashboards/translations`), `{lang}_dashboard.json` naming, validated remote bundle override path, and English key fallback.
  8.  [x] Define user-facing substitution contract for multi-instance templates.
  - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, future manifest schema docs
  - Standardize `user.*` substitution keys and require `integration.entry_id` for instance-safe template resolution.
  - Status note: Ratified `user.*` contract (`user.name`, `user.user_id`) with required `integration.entry_id` and `dashboard_lookup_key`-safe resolution for multi-instance determinism.
  9. [x] Ratify dashboard helper pointer contract.
     - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, template authoring docs
     - Status note: Accepted. Use attribute-scoped dynamic lookup (`purpose + integration.entry_id + user.user_id`) only; no legacy fallback path.
  10. [x] Ratify helper lookup optimization strategy.
  - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, template authoring docs
  - Status note: Accepted. Use composite `dashboard_lookup_key` and enforce unique helper identity per `<entry_id>:<user_id>`.
  11. [x] Decide dashboard template error-handling UX at implementation time.
  - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, template implementation PRs
  - Status note: Accepted. Use warning-card pattern with minimal validation ladder; avoid new framework complexity in v1.
  12. [x] Ratify template preference customization model (D14).
  - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, template docs in registry repo
  - Status note: Accepted. For v1, use companion preference docs per template over backend runtime preference controls.
  13. [x] Ratify template composition storage model (D15).
  - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, `choreops-dashboards/README.md`
  - Status note: Accepted. v1 uses hybrid authoring with pre-release assembly while preserving dashboard-level runtime units.
  14. [x] Ratify registry release/channel versioning model (D16).
  - Files: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, `choreops-dashboards/README.md`, `docs/RELEASE_CHECKLIST.md`
  - Status note: Accepted. Define stable, beta, and dev publication semantics, tag formats, and branch/promotion workflow.
- **Key issues**
  - Template IDs must be immutable once published.
  - Over-flexible metadata increases maintenance burden and ambiguity.

### Phase 3 – Runtime resolution model

- **Goal**: Define one intuitive and deterministic runtime path for discovering, merging, selecting, and loading templates.
- **Steps / detailed work items**
  1. [x] Define source precedence and merge semantics.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Local vendored manifest is baseline; remote can override by `template_id`; invalid remote entries are ignored with diagnostics.
     - Status note: Frozen under runtime contract `5.5.1` with deterministic merge keying, record validity rules, and stable ordering behavior.
  2. [x] Define template selection algorithm contract.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Inputs: user choice, compatibility filter, dependency policy, lifecycle state.
     - Status note: Frozen under runtime contract `5.5.2` with explicit filter order, selection precedence, and blocking result behavior.
  3. [x] Define caching and refresh behavior.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include TTL, startup behavior, timeout policy, and stale data handling.
     - Status note: Frozen under runtime contract `5.5.3` with default 30-minute TTL, non-blocking fallback, and explicit refresh triggers.
  4. [x] Define failure-mode matrix.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Cases: remote unavailable, malformed manifest, missing template asset, dependency missing, schema mismatch.
     - Status note: Frozen under runtime contract `5.5.4` with case-by-case runtime behavior, user impact, and diagnostics expectations.
  5. [x] Define user-facing UX rules for dependency handling.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Blocking behavior for `required`; non-blocking warning behavior for `recommended`.
     - Status note: Frozen under runtime contract `5.5.5`; required dependencies block, recommended dependencies warn and continue.
- **Key issues**
  - Runtime behavior must remain predictable even when remote state changes.
  - Selection logic must remain explainable to users and maintainers.

### Phase 4 – Contribution and operations model

- **Goal**: Define how templates are submitted, reviewed, validated, released, and vendored so community contribution scales cleanly.
- **Steps / detailed work items**
  1. [x] Define template submission workflow.
     - Files: `choreops-dashboards/README.md`, `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include contributor checklist, metadata requirements, and minimum acceptance bar.
     - Status note: Added explicit workflow and minimum acceptance bar in standards (`7`) and registry README.
  2. [x] Define CI/review quality gates for dashboard registry PRs.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Gates: schema validation, naming policy checks, dependency key validation, YAML parse checks.
     - Status note: Added required CI/review gate set for contract, naming, dependency, lifecycle, and YAML validation.
  3. [x] Define release synchronization workflow (vendoring).
     - Files: `docs/RELEASE_CHECKLIST.md`, `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Require sync artifact generation and contract validation prior to integration release cut.
     - Status note: Added explicit integration vendoring synchronization workflow and release-blocking criteria.
  4. [x] Define ownership and approval model.
     - Files: `choreops-dashboards/README.md`, `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Define who can approve schema changes vs template-only changes.
     - Status note: Maintainer approval and architecture-owner sign-off boundaries are now explicitly documented.
  5. [x] Define deprecation and retirement process.
     - File: `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include lead time, migration guidance, and fallback behavior for retired templates.
     - Status note: Added explicit stepwise deprecation-to-archival process with migration and visibility requirements.
  6. [x] Publish explicit community guidance for custom cards.
     - Files: `choreops-dashboards/README.md`, `docs/RELEASE_CHECKLIST.md`
     - Document that card code ships from dedicated frontend-card repositories and is consumed via dependency declarations.
     - Status note: Custom card boundary and dedicated-card-repo dependency guidance is now codified in release and repo docs.
  7. [x] Define `choreops-dashboards` release operations and branch policy.
     - Files: `choreops-dashboards/README.md`, `docs/RELEASE_CHECKLIST.md`
     - Publish SemVer tag policy (`vX.Y.Z`, `vX.Y.Z-beta.N`, `vX.Y.Z-dev.YYYYMMDD+<shortsha>`) and promotion steps from dev to beta to stable.
     - Status note: Branch and promotion workflow (`main` + optional `release/X.Y` + dev/beta/stable publication) documented with compatibility recording requirements.
- **Key issues**
  - Without explicit ownership boundaries, schema changes can destabilize runtime.
  - Release operations must avoid manual fragile steps.

_Repeat additional phase sections as needed; maintain structure._

## Pre-build alignment gate (required before builder handoff)

The builder handoff starts only when all items below are explicitly resolved and recorded.

### A) Final decision alignment

- [x] D13 finalized with explicit UX contract (default warning-card behavior or approved alternative with rationale).
  - Status note: Accepted. Use warning-card UX with actionable guidance and a minimal validation ladder (missing inputs, unresolved helper, incomplete helper payload).
- [x] Manifest v1 required fields frozen (names, required/optional status, and validation behavior).
  - Status note: Frozen to standards document v1 contract sections for identity, compatibility, assets, dependencies, and metadata.
- [x] Dependency contract frozen (`required`, `recommended`, and blocking/non-blocking behavior).
  - Status note: Frozen. `required` blocks template selection; `recommended` allows selection with warning.

### B) Operations and governance alignment

- [x] CI gate ownership defined for dashboard repo (who maintains schema validation and release checks).
  - Status note: Dashboard maintainers own schema/YAML/dependency CI gates; architecture owner required for schema-contract changes.
- [x] Release promotion authority defined (who can publish dev, beta, stable tags).
  - Status note: Dashboard maintainers publish dev/beta/stable tags; architecture owner sign-off required before stable when schema-impacting changes are included.
- [x] Vendoring cadence defined (when integration pulls dashboard artifacts and from which channel).
  - Status note: Integration release flow consumes stable dashboard tags by default; beta consumption is opt-in for pre-release validation.

### C) Documentation alignment

- [x] Runtime contracts remain canonical in integration docs.
- [x] Authoring and dashboard release operations remain canonical in dashboard repo docs.
- [x] Cross-links verified between integration and dashboard documentation to avoid duplicated authority.

### D) Builder-ready acceptance criteria

- [x] Implementation scope list is frozen and traceable to accepted decisions.
- [x] Test evidence requirements are defined (contract tests, validation tests, release checks).
- [x] Handoff packet is complete and attached to the implementation request.

## Builder handoff packet (attach with build request)

Use this packet as the mandatory handoff bundle:

1. Decision snapshot (D1-D16) with current statuses and unresolved items (if any).
2. Manifest v1 contract summary (fields, validation rules, compatibility fields).
3. Release/channel policy summary (dev, beta, stable tag formats and promotion flow).
4. Compatibility matrix baseline entry and required update process.
5. Documentation ownership map (integration runtime docs vs dashboard authoring docs).
6. Builder acceptance criteria and required proof artifacts.
7. Detailed builder implementation plan:
   - `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_BUILDER_IMPLEMENTATION.md`
8. Builder handoff card:
   - `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_BUILDER_HANDOFF.md`

### Builder acceptance criteria (frozen)

- Implement D11/D12 lookup contract using `dashboard_lookup_key` and required helper attributes.
- Implement D13 canonical warning-card validation ladder exactly (E01/E02/E03 paths).
- Keep dashboard runtime unit at full-template level (D15), with optional authoring modularity only.
- Preserve release/channel conventions and compatibility recording requirements (D16).

### Required proof artifacts

- Tests for helper lookup resolution and error-path rendering behavior.
- Contract validation evidence for manifest/dependency rules.
- Release checklist entry including compatibility matrix update.

## Testing & validation

- Tests executed (describe suites, commands, results).
  - Implementation and closeout validation are tracked in:
    - `docs/completed/DASHBOARD_REGISTRY_GENERATION_SUP_GAP_REMEDIATION_PLAN.md`
- Outstanding tests (not run and why).
  - See remediation plan Phase R5 for final validation-gate status.
- Links to failing logs or CI runs if relevant.
  - N/A at planning stage.

## Notes & follow-up

- This initiative intentionally prioritizes standards over immediate coding to avoid locking in proof-of-concept constraints.
- Implementation tasks should only be created after decision gates in the supporting standards document are resolved.
- If persistent storage behavior changes later (e.g., storing canonical `template_id` selections), add explicit schema migration planning and test requirements before build kickoff.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
