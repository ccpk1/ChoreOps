# Initiative Plan Template

## Initiative snapshot

- **Name / Code**: Dashboard registry architecture standards and operating model (`DASHBOARD_REGISTRY_GENERATION`)
- **Target release / milestone**: Architecture ratification in v0.6 planning window; phased delivery across v0.6.x
- **Owner / driver(s)**: ChoreOps maintainers (Architecture, Integration, DX)
- **Status**: In progress (planning)

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Standards and guardrails | Define architecture principles, scope boundaries, and non-negotiable standards | 15% | Must be approved before implementation details |
| Phase 2 – Registry contract and taxonomy | Define manifest schema, naming model, dependency contract, and versioning rules | 10% | Core scaling decisions live here |
| Phase 3 – Runtime resolution model | Define deterministic discovery/loading/merge behavior with offline guarantees | 5% | “Single path” behavior and fallback policy |
| Phase 4 – Contribution and operations model | Define submission workflow, review gates, release sync, and lifecycle governance | 0% | Needed for community scale and maintainability |

1. **Key objective** – Define an architecture-first dashboard ecosystem that scales across templates, contributors, and releases without inheriting proof-of-concept constraints.
2. **Summary of recent work**
   - Established dual-repo direction (`ccpk1/choreops` + `ccpk1/choreops-dashboards`) and vendoring requirement for HACS-safe fallback.
   - Created initial dashboards repository scaffold (`README.md`, `LICENSE`, `.gitignore`, baseline `manifest.json`).
   - Drafted initial implementation-biased plan and now pivoting to standards-first architecture and decision framework.
3. **Next steps (short term)**
   - Lock architecture principles, non-goals, and target operating model.
   - Ratify manifest schema and naming taxonomy before writing runtime code.
   - Ratify dependency handling policy (`required`, `recommended`, `optional`) and UX behavior on missing dependencies.
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
   - `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Architecture must be registry-contract-first, not implementation-first.
     - Runtime behavior must be deterministic and offline-safe.
     - Template submission must be policy-driven with objective validation gates.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Standards and guardrails

- **Goal**: Define the architecture “north star” and quality guardrails so implementation decisions remain consistent and scalable.
- **Steps / detailed work items**
  1. [ ] Define architecture principles and anti-goals.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include principles: deterministic behavior, explicit contracts, compatibility by default, low cognitive load, and observability.
  2. [ ] Define explicit scope boundaries for this initiative.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_IN-PROCESS.md`
     - Clarify what is in scope (registry contract, discovery, submission, dependency model) and out of scope (new dashboard visual design system).
  3. [ ] Define operating modes and guarantees.
     - Files: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`, `docs/ARCHITECTURE.md`
     - Required guarantees: cold-start local fallback, non-blocking remote failure path, deterministic template selection.
  4. [ ] Define observability standards.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Establish what must be logged/diagnosed (manifest source, selection reason, dependency validation outcomes).
  5. [ ] Create architecture ratification checklist.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_IN-PROCESS.md`
     - Gate implementation start on approved standards decisions.
- **Key issues**
  - High risk of architecture drift without ratified standards.
  - Need one canonical place for decision history and rationale.

### Phase 2 – Registry contract and taxonomy

- **Goal**: Define the manifest as a strict, evolvable contract and standardize naming/organization so templates remain discoverable and maintainable at scale.
- **Steps / detailed work items**
  1. [ ] Define manifest schema v1 with required and optional fields.
     - Files: `choreops-dashboards/manifest.json` (spec target), `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Define identity fields (`template_id`, `slug`, `display_name`), semantics (`category`, `audience`), compatibility, dependencies, and lifecycle state.
  2. [ ] Define naming taxonomy and folder organization standards.
     - Files: `choreops-dashboards/README.md`, `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Establish canonical naming for template files, IDs, variants, and deprecation aliases.
  3. [ ] Define schema evolution and compatibility policy.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include semver strategy for manifest schema and backward-compatibility guarantees.
  4. [ ] Define dependency contract model.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Formalize `required` vs `recommended` dependencies and machine-readable dependency identifiers.
  5. [ ] Define template lifecycle states.
     - Files: `choreops-dashboards/manifest.json`, `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - States: `active`, `deprecated`, `archived`, with migration hints for replaced templates.
- **Key issues**
  - Template IDs must be immutable once published.
  - Over-flexible metadata increases maintenance burden and ambiguity.

### Phase 3 – Runtime resolution model

- **Goal**: Define one intuitive and deterministic runtime path for discovering, merging, selecting, and loading templates.
- **Steps / detailed work items**
  1. [ ] Define source precedence and merge semantics.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Local vendored manifest is baseline; remote can override by `template_id`; invalid remote entries are ignored with diagnostics.
  2. [ ] Define template selection algorithm contract.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Inputs: user choice, compatibility filter, dependency policy, lifecycle state.
  3. [ ] Define caching and refresh behavior.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include TTL, startup behavior, timeout policy, and stale data handling.
  4. [ ] Define failure-mode matrix.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Cases: remote unavailable, malformed manifest, missing template asset, dependency missing, schema mismatch.
  5. [ ] Define user-facing UX rules for dependency handling.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Blocking behavior for `required`; non-blocking warning behavior for `recommended`.
- **Key issues**
  - Runtime behavior must remain predictable even when remote state changes.
  - Selection logic must remain explainable to users and maintainers.

### Phase 4 – Contribution and operations model

- **Goal**: Define how templates are submitted, reviewed, validated, released, and vendored so community contribution scales cleanly.
- **Steps / detailed work items**
  1. [ ] Define template submission workflow.
     - Files: `choreops-dashboards/README.md`, `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include contributor checklist, metadata requirements, and minimum acceptance bar.
  2. [ ] Define CI/review quality gates for dashboard registry PRs.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Gates: schema validation, naming policy checks, dependency key validation, YAML parse checks.
  3. [ ] Define release synchronization workflow (vendoring).
     - Files: `docs/RELEASE_CHECKLIST.md`, `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Require sync artifact generation and contract validation prior to integration release cut.
  4. [ ] Define ownership and approval model.
     - Files: `choreops-dashboards/README.md`, `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Define who can approve schema changes vs template-only changes.
  5. [ ] Define deprecation and retirement process.
     - File: `docs/in-process/DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md`
     - Include lead time, migration guidance, and fallback behavior for retired templates.
- **Key issues**
  - Without explicit ownership boundaries, schema changes can destabilize runtime.
  - Release operations must avoid manual fragile steps.

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- Tests executed (describe suites, commands, results).
  - Planning-only pass: no implementation tests executed for this update.
- Outstanding tests (not run and why).
  - All architecture decisions require future contract and workflow tests after ratification.
- Links to failing logs or CI runs if relevant.
  - N/A at planning stage.

## Notes & follow-up

- This initiative intentionally prioritizes standards over immediate coding to avoid locking in proof-of-concept constraints.
- Implementation tasks should only be created after decision gates in the supporting standards document are resolved.
- If persistent storage behavior changes later (e.g., storing canonical `template_id` selections), add explicit schema migration planning and test requirements before build kickoff.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
