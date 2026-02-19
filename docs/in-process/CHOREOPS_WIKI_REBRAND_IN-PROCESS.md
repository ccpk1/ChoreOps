# Initiative Plan: ChoreOps wiki rebrand and documentation cleanup

## Initiative snapshot

- **Name / Code**: ChoreOps Wiki Rebrand (`CHOREOPS-WIKI-REBRAND-001`)
- **Target release / milestone**: v0.5.0 documentation hardening window
- **Owner / driver(s)**: Repo maintainers (`@ccpk1` + contributors)
- **Status**: In progress (Phase 1 complete; Phase 2 pending gate approvals)

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Editorial baseline and policy | Define branding, wording policy, and link standards | 100% | Policy finalized, style guide added, and baseline/permission inventory documented |
| Phase 2 – Context-aware content rebrand | Replace KidsChores branding in context, section by section | 0% | Must avoid blind find/replace across service names and historical notes |
| Phase 3 – Link normalization and repair | Convert old/full links and repair broken internal references | 0% | Initial audit found internal broken links and legacy full-path wiki URLs |
| Phase 4 – Navigation, logo decision, and QA | Improve discoverability and finalize visual branding pattern | 0% | Home/sidebar completeness and logo strategy decision pending |

1. **Key objective** – Rebrand the migrated wiki from KidsChores to ChoreOps with context-aware edits, working links, and maintainable navigation.
2. **Summary of recent work**
   - Wiki content was migrated into `ccpk1/ChoreOps.wiki.git` and is now editable locally at `/workspaces/choreops-wiki`.
   - Initial audit identified broad legacy branding footprint and legacy absolute-link patterns.
   - Initial audit identified internal wiki links that no longer resolve due to renamed pages and malformed targets.
  - Phase 1 completed with a shared style guide (`choreops-wiki/Style-Guide.md`) and supporting baseline/permission inventory (`docs/in-process/CHOREOPS_WIKI_REBRAND_SUP_PHASE1_BASELINE.md`).
3. **Next steps (short term)**
  - Confirm remaining Phase 2 gate decision on technical identifier handling (Gate 2.1).
  - Start Batch A rebrand for top-level trust pages (`Home`, `_Sidebar`, installation, troubleshooting, FAQ).
  - Prepare Phase 3 external-link approval review using baseline inventory.
4. **Risks / blockers**
   - Blind replacement can break technical accuracy (service names, entity IDs, historical migration notes).
   - Legacy URL conversion can unintentionally degrade useful external references if done without classification.
   - Navigation changes can increase maintenance burden if all pages are forced into top-level menus without structure.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [docs/in-process/CHOREOPS_FULL_REBRAND_IN-PROCESS.md](CHOREOPS_FULL_REBRAND_IN-PROCESS.md)
  - [docs/in-process/CHOREOPS_WIKI_REBRAND_SUP_PHASE1_BASELINE.md](CHOREOPS_WIKI_REBRAND_SUP_PHASE1_BASELINE.md)
   - [choreops-wiki/Home.md](../../choreops-wiki/Home.md)
   - [choreops-wiki/_Sidebar.md](../../choreops-wiki/_Sidebar.md)
  - [choreops-wiki/Style-Guide.md](../../choreops-wiki/Style-Guide.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Use context-aware rewrite by page intent (user guide vs technical reference) instead of global text replacement.
     - Do not keep legacy KidsChores branding in wiki prose; bring content forward to ChoreOps naming.
     - Use relative links for wiki-internal navigation unless technically impossible.
     - Keep external links absolute only when destination is outside the wiki, and require owner permission for each external link retained.
     - Tone standard is plain and helpful for an open-source audience; owner signs off tone consistency.
   - **Completion confirmation**: `[ ]` All wiki branding, link integrity, navigation, and QA checklist items complete before owner sign-off.

> **Important:** Keep this summary current after each cleanup batch so reviewers can see progress and remaining risk quickly.

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after each merged wiki cleanup commit.
- **Detailed tracking**: Record line-item completion in phase sections below; keep summary concise.

## Detailed phase tracking

### Phase 1 – Editorial baseline and policy

- **Goal**: Create a clear policy for terminology, link styles, and historical references so edits remain consistent.
- **Steps / detailed work items**
  - [x] Capture initial wiki audit baseline
    - Scope observed: branding references, old absolute repo/wiki links, encoded URL forms, and broken internal links.
    - Evidence source: current local wiki clone in `/workspaces/choreops-wiki`.
  - [x] Define naming and legacy-reference policy
    - File: `choreops-wiki/Home.md`, plus policy note section in this plan.
    - Rule: use `ChoreOps` as the product name across wiki prose; do not preserve legacy KidsChores branding in documentation narrative.
    - Exception: retain literal technical identifiers only where required for factual correctness, with concise clarification if needed.
  - [x] Define internal-link style policy
    - Target convention: relative internal links (e.g., `Configuration%3A-Points`) for wiki pages.
    - External links remain absolute and human-readable (`https://...`, not encoded `https%3A//...`) only when non-wiki destinations are required.
  - [x] Define rewrite batching strategy (formerly “page classification”)
    - Purpose: execution batching only, not information architecture redesign.
    - Batch A: onboarding/trust pages (`Home`, `_Sidebar`, install, FAQ, troubleshooting)
    - Batch B: feature configuration and examples
    - Batch C: technical/developer reference pages with stricter terminology checks
  - [x] Add editorial quality checklist
    - Tone target: plain and helpful for open-source users.
    - Sign-off owner: repository owner reviews tone consistency before phase completion.
  - [x] Add external-link permission gate process
    - Build a review list of all external links that remain after internal-link conversion.
    - Require owner approval for retained external links before Phase 3 completion.
    - Baseline inventory captured in `docs/in-process/CHOREOPS_WIKI_REBRAND_SUP_PHASE1_BASELINE.md`.
- **Key issues**
  - None open for Phase 1.

### Phase 2 – Context-aware content rebrand

- **Goal**: Replace outdated branding while preserving technical correctness and historical context.
- **Phase gate (must pass before Phase 2 starts)**:
  - [ ] Gate 2.1: Confirm technical identifier policy for service IDs/entity IDs (replace vs retain with clarification) is explicitly approved.
  - [x] Gate 2.2: Confirm no legacy KidsChores branding remains acceptable in prose content.
- **Steps / detailed work items**
  - [ ] Rebrand top-level pages first (high-visibility)
    - Files: `choreops-wiki/Home.md`, `choreops-wiki/_Sidebar.md`, `choreops-wiki/Getting-Started:-Installation.md`, `choreops-wiki/Technical:-Troubleshooting.md`, `choreops-wiki/Frequently-Asked-Questions-(FAQ).md`.
  - [ ] Rebrand service and example docs with context safeguards
    - Files: `choreops-wiki/Services:-Reference.md`, `choreops-wiki/Service:-*.md`, `choreops-wiki/Examples:-*.md`, `choreops-wiki/Tips-&-Tricks:-*.md`.
    - Preserve literal service IDs only where they are still valid in runtime behavior docs; annotate legacy IDs where needed.
  - [ ] Rebrand technical reference pages carefully
    - Files: `choreops-wiki/Technical:-*.md`.
    - Ensure lexicon alignment with Item vs Entity standards from architecture docs.
  - [ ] Add explicit “legacy naming” callouts where required
    - Use short note blocks in pages that discuss migration history or old forum post names.
  - [ ] Peer review pass for wording and clarity
    - Validate user-facing tone and remove stale KidsChores branding that is not historical context.
- **Key issues**
  - High risk of accidental semantic changes in service examples if identifiers are rewritten without verification.

### Phase 3 – Link normalization and repair

- **Goal**: Ensure all wiki links resolve, old repo links are updated, and internal links use consistent relative format.
- **Phase gate (must pass before Phase 3 starts)**:
  - [ ] Gate 3.1: Approve the external-link retention review list (which non-wiki links remain and why).
  - [ ] Gate 3.2: Approve relative-link-first conversion for all internal wiki references.
- **Steps / detailed work items**
  - [ ] Replace legacy full-path wiki links to old repo
    - Pattern targets: `ad-ha/kidschores-ha/wiki/*` and old dashboard repo references where obsolete.
    - Files likely impacted: `Getting-Started:-Installation.md`, `Technical:-Notifications.md`, `Frequently-Asked-Questions-(FAQ).md`, `Shared-Chore-Functionality.md`, `Configuration:-Notifications.md`.
  - [ ] Normalize malformed encoded URL forms
    - Replace `https%3A//...` style links with proper absolute URLs for external resources.
  - [ ] Repair broken internal wiki links
    - Resolve renamed/non-existent targets found during audit.
    - Prioritize user-journey pages (install → config → services → troubleshooting).
  - [ ] Apply relative internal-link convention broadly
    - Convert any remaining full-path links to local wiki page links when destination is inside wiki.
  - [ ] Run link integrity validation pass
    - Validate zero unresolved internal targets before phase completion.
- **Key issues**
  - Some referenced pages may need to be created, merged, or redirected rather than simple relink.

### Phase 4 – Navigation, logo decision, and QA

- **Goal**: Finalize discoverability and visual consistency with minimal maintenance overhead.
- **Phase gate (must pass before Phase 4 starts)**:
  - [ ] Gate 4.1: Approve navigation coverage model (top-level vs deep-linked pages).
  - [ ] Gate 4.2: Approve logo placement strategy.
- **Steps / detailed work items**
  - [ ] Complete Home + sidebar navigation coverage strategy
    - Decide which pages are top-level vs deep-linked reference pages.
    - Ensure no orphan critical pages for setup and operations.
  - [ ] Decide logo placement strategy (explicit decision checkpoint)
    - Option A (recommended): logo on `Home.md` and optional compact sidebar header only.
    - Option B: logo on every page (not recommended unless strict branding requirement).
    - Record decision and rationale in this plan.
  - [ ] Apply chosen logo pattern consistently
    - If Option A: update only Home/sidebar assets and avoid repeated per-page header blocks.
  - [ ] Perform final editorial QA sweep
    - Check terminology consistency, heading quality, and duplicate/obsolete sections.
  - [ ] Publish completion report
    - Summarize changed files, resolved links, deferred items, and follow-up backlog.
- **Key issues**
  - Over-branding every article can reduce readability and create avoidable maintenance churn.

## Testing & validation

- **Validation gates for this initiative**
  - Internal-link integrity pass returns zero broken internal wiki links.
  - Grep audit for branding terms returns only intentional legacy callouts.
  - Home/sidebar spot-check confirms top navigation links resolve.
- **Suggested validation commands**
  - `grep -RInE --include='*.md' 'KidsChores|kidschores' /workspaces/choreops-wiki`
  - `grep -RInE --include='*.md' 'ad-ha/kidschores-ha|kidschores-ha/wiki' /workspaces/choreops-wiki`
  - Link-check script execution (to be added in implementation phase)
- **Outstanding tests**
  - Full automated markdown link-check script is not yet committed; currently manual/scripted audit workflow.

## Notes & follow-up

- **Context rule (non-negotiable)**: do not convert technical identifiers blindly; update runtime identifiers only if confirmed by integration behavior.
- **Documentation architecture recommendation**: keep user onboarding concise and route deep technical details to technical pages.
- **Owner decisions incorporated (2026-02-19)**:
  - No legacy branding narrative should remain in wiki docs.
  - Relative links are required for internal wiki pages unless not practical/possible.
  - External links that remain require owner permission.
  - Tone should remain plain and helpful; owner signs off final tone consistency.
- **Cross-plan alignment**: Track this plan as a Phase 5 supporting initiative under full rebrand and update parent summary after major wiki milestones.
