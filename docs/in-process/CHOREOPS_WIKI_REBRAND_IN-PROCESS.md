# Initiative Plan: ChoreOps wiki rebrand and documentation cleanup

## Initiative snapshot

- **Name / Code**: ChoreOps Wiki Rebrand (`CHOREOPS-WIKI-REBRAND-001`)
- **Target release / milestone**: v0.5.0 documentation hardening window
- **Owner / driver(s)**: Repo maintainers (`@ccpk1` + contributors)
- **Status**: Deferred - execution transferred to `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

## Transfer notice

This plan is superseded for execution.
All remaining implementation work is tracked in:

- `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

This file remains as historical wiki cleanup evidence only.

## Summary & immediate steps

| Phase / Step                                | Description                                                  | % complete | Quick notes                                                                                                                                                     |
| ------------------------------------------- | ------------------------------------------------------------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Editorial baseline and policy     | Define branding, wording policy, and link standards          | 100%       | Policy finalized, style guide added, and baseline/permission inventory documented                                                                               |
| Phase 2 – Context-aware content rebrand     | Replace KidsChores branding in context, section by section   | 100%       | Batch A/B complete; current residual scan reports 0 matching files and 0 matches for tracked legacy patterns                                                    |
| Phase 3 – Link normalization and repair     | Convert old/full links and repair broken internal references | 95%        | Internal link integrity pass reports zero broken internal wiki links and zero legacy `ad-ha` wiki URLs; external-link retention set prepared for owner approval |
| Phase 4 – Navigation, logo decision, and QA | Improve discoverability and finalize visual branding pattern | 90%        | Navigation coverage complete (no Home/Sidebar orphans), logo strategy decision recorded, and final editorial QA sweep passed                                    |

1. **Key objective** – Rebrand the migrated wiki from KidsChores to ChoreOps with context-aware edits, working links, and maintainable navigation.
2. **Summary of recent work**
   - Wiki content was migrated into `ccpk1/ChoreOps.wiki.git` and is now editable locally at `/workspaces/choreops-wiki`.
   - Initial audit identified broad legacy branding footprint and legacy absolute-link patterns.
   - Initial audit identified internal wiki links that no longer resolve due to renamed pages and malformed targets.

- Phase 1 completed with a shared style guide (`choreops-wiki/Style-Guide.md`) and supporting baseline/permission inventory (`docs/in-process/CHOREOPS_WIKI_REBRAND_SUP_PHASE1_BASELINE.md`).
- Phase 2 Batch A first-pass updates completed for `Home`, `_Sidebar`, installation, troubleshooting, and FAQ pages with contextual rebrand and link normalization.
- Phase 2 Batch B started: `Configuration:-Points`, `Configuration:-Kids-Parents`, and `Configuration:-Notifications` updated with ChoreOps branding and link cleanup.
- Phase 2 Batch B continued: `Configuration:-Badges-Periodic`, `Getting-Started:-Backup-Restore`, and `Examples:-Overdue-Penalties` updated for ChoreOps naming, internal-link normalization, and legacy external-link reduction.
- Phase 2 Batch B expanded: `Services:-Reference` and `Technical:-Entities-States` updated to remove legacy `kidschores` branding in service/entity examples and technical snippets.
- Phase 2 Batch B expanded again: `Technical:-Notifications`, `Examples:-Calendar-Scheduling`, and `Service:-Shadow-Kid-Linking-User-Guide` updated for ChoreOps naming and legacy namespace/link cleanup.
- Phase 2 Batch B expanded further: `Advanced:-Dashboard` and `Tips-&-Tricks:-Configure-Automatic-Approval-of-Chores` updated for ChoreOps branding, namespace cleanup, and modern entity examples.
- Phase 2 Batch B expanded further: `Tips-&-Tricks:-Use-Calendar-Events-to-Set-Chore-Due-Dates` and `Examples:-NFC-Tags` updated for ChoreOps naming, namespace examples, and encoded-link normalization.
- Phase 2 Batch B expanded further: `Getting-Started:-Quick-Start` and `Technical:-Chores` updated to remove legacy naming in walkthroughs, technical entity examples, and source-path references.
- Phase 2 Batch B expanded further: `Getting-Started:-Dashboard-Generation`, `Tips-&-Tricks:-Critical-Chore-Overdue-Alerts`, `Tips-&-Tricks:-Apply-a-Penalty-for-Overdue-Chore`, and `Tips-&-Tricks:-Use-NFC-Tag-to-Mark-Chore-Claimed` updated for ChoreOps branding and encoded-link cleanup.
- Phase 2 Batch B completion pass: `Technical:-Services-Legacy`, `Service:-Reset-Overdue-Chores`, `Service:-Reset-All-Data`, `Getting-Started:-Scenarios`, `Advanced:-Badges-Overview`, `Service:-Set-Chore-Due-Dates`, `Configuration:-Badges-Cumulative`, `Shared-Chore-Functionality`, `Configuration:-Rewards`, `Advanced:-Badges-Cumulative`, `Advanced:-Access-Control`, and `Style-Guide` updated; residual scan now reports zero tracked legacy-pattern hits.
- Phase 3 execution pass repaired unresolved internal wiki links across access-control, dashboard, installation, rewards, FAQ, kids/parents, and shadow-linking pages; decoded internal-link validation now reports zero unresolved targets.
- Phase 3 execution pass also confirmed zero remaining `https://github.com/ad-ha/kidschores-ha/wiki/...` links in top-level wiki pages.
- Phase 3 gate-prep update captured a current external-link inventory in `CHOREOPS_WIKI_REBRAND_SUP_PHASE1_BASELINE.md` (occurrence/unique counts, domain summary, and retention set for owner approval).
- Phase 4 navigation update expanded `Home.md` and `_Sidebar.md` sections (services, tips, references, FAQ, style guide), and navigation coverage audit now reports zero pages missing from both Home and Sidebar.
- Final QA evidence pass confirms: zero tracked legacy-pattern matches, zero unresolved internal links (decoded-target validation), and zero pages missing from both Home and Sidebar coverage.
- Phase 4 logo strategy recorded as **Option A** (home/sidebar only; no per-page logos) to minimize maintenance churn.
- Supporting baseline inventory updated to record owner decision removing both legacy community forum thread links.

3. **Next steps (short term)**

- Request owner sign-off on external-link retention set (Phase 3 gate 3.1).
- Request owner sign-off on navigation/logo model (Phase 4 gates 4.1 and 4.2).
- Merge and publish after owner approval.

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
  - [docs/in-process/CHOREOPS_WIKI_REBRAND_SUP_OWNER_SIGNOFF_CHECKLIST.md](CHOREOPS_WIKI_REBRAND_SUP_OWNER_SIGNOFF_CHECKLIST.md)
- [choreops-wiki/Home.md](../../choreops-wiki/Home.md)
- [choreops-wiki/\_Sidebar.md](../../choreops-wiki/_Sidebar.md)
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
  - [x] Gate 2.1: Confirm technical identifier policy for service IDs/entity IDs (replace vs retain with clarification) is explicitly approved.
    - Decision: replace legacy-branded identifiers in examples when current ChoreOps identifiers are known; retain literal legacy identifiers only when required for factual compatibility context and add concise clarification.
  - [x] Gate 2.2: Confirm no legacy KidsChores branding remains acceptable in prose content.
- **Steps / detailed work items**
  - [x] Rebrand top-level pages first (high-visibility)
    - Files: `choreops-wiki/Home.md`, `choreops-wiki/_Sidebar.md`, `choreops-wiki/Getting-Started:-Installation.md`, `choreops-wiki/Technical:-Troubleshooting.md`, `choreops-wiki/Frequently-Asked-Questions-(FAQ).md`.
  - [x] Rebrand service and example docs with context safeguards
    - Files: `choreops-wiki/Services:-Reference.md`, `choreops-wiki/Service:-*.md`, `choreops-wiki/Examples:-*.md`, `choreops-wiki/Tips-&-Tricks:-*.md`.
    - Preserve literal service IDs only where they are still valid in runtime behavior docs; annotate legacy IDs where needed.
  - [x] Rebrand technical reference pages carefully
    - Files: `choreops-wiki/Technical:-*.md`.
    - Ensure lexicon alignment with Item vs Entity standards from architecture docs.
  - [x] Add explicit “legacy naming” callouts where required
    - Use short note blocks in pages that discuss migration history or old forum post names.
  - [x] Peer review pass for wording and clarity
    - Validate user-facing tone and remove stale KidsChores branding that is not historical context.
- **Key issues**
  - High risk of accidental semantic changes in service examples if identifiers are rewritten without verification.

### Phase 3 – Link normalization and repair

- **Goal**: Ensure all wiki links resolve, old repo links are updated, and internal links use consistent relative format.
- **Phase gate (must pass before Phase 3 starts)**:
  - [ ] Gate 3.1: Approve the external-link retention review list (which non-wiki links remain and why).
  - [x] Gate 3.2: Approve relative-link-first conversion for all internal wiki references.
- **Steps / detailed work items**
  - [x] Replace legacy full-path wiki links to old repo
    - Pattern targets: `ad-ha/kidschores-ha/wiki/*` and old dashboard repo references where obsolete.
    - Files likely impacted: `Getting-Started:-Installation.md`, `Technical:-Notifications.md`, `Frequently-Asked-Questions-(FAQ).md`, `Shared-Chore-Functionality.md`, `Configuration:-Notifications.md`.
  - [x] Normalize malformed encoded URL forms
    - Replace `https%3A//...` style links with proper absolute URLs for external resources.
  - [x] Repair broken internal wiki links
    - Resolve renamed/non-existent targets found during audit.
    - Prioritize user-journey pages (install → config → services → troubleshooting).
  - [x] Apply relative internal-link convention broadly
    - Convert any remaining full-path links to local wiki page links when destination is inside wiki.
  - [x] Run link integrity validation pass
    - Validate zero unresolved internal targets before phase completion.
- **Key issues**
  - Some referenced pages may need to be created, merged, or redirected rather than simple relink.

### Phase 4 – Navigation, logo decision, and QA

- **Goal**: Finalize discoverability and visual consistency with minimal maintenance overhead.
- **Phase gate (must pass before Phase 4 starts)**:
  - [ ] Gate 4.1: Approve navigation coverage model (top-level vs deep-linked pages).
  - [ ] Gate 4.2: Approve logo placement strategy.
- **Steps / detailed work items**
  - [x] Complete Home + sidebar navigation coverage strategy
    - Decide which pages are top-level vs deep-linked reference pages.
    - Ensure no orphan critical pages for setup and operations.
  - [x] Decide logo placement strategy (explicit decision checkpoint)
    - Option A (recommended): logo on `Home.md` and optional compact sidebar header only.
    - Option B: logo on every page (not recommended unless strict branding requirement).
    - Record decision and rationale in this plan.
  - [x] Apply chosen logo pattern consistently
    - Decision applied: Option A selected with no per-page logos; retain Home/sidebar-first branding to avoid duplication and maintenance overhead.
  - [x] Perform final editorial QA sweep
    - Check terminology consistency, heading quality, and duplicate/obsolete sections.
  - [x] Publish completion report
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

## Completion report (draft pending owner sign-off)

### Scope delivered

- Phase 1 policy baseline completed and documented
- Phase 2 contextual rebrand completed across user, service, example, and technical pages
- Phase 3 link normalization executed with repair + verification passes
- Phase 4 navigation model implemented and QA evidence collected

### QA outcomes

- Legacy pattern scan (top-level wiki pages): 0 files, 0 matches
- Decoded internal-link validation: 0 unresolved internal targets
- Navigation coverage audit (Home + Sidebar union): 0 pages missing
- Legacy old-wiki URL scan (`ad-ha/kidschores-ha/wiki`): 0 matches

### Remaining approvals

- Owner sign-off on external-link retention set (Phase 3 gate 3.1)
- Owner sign-off on navigation/logo model (Phase 4 gates 4.1 and 4.2)
- Owner review checklist prepared in `CHOREOPS_WIKI_REBRAND_SUP_OWNER_SIGNOFF_CHECKLIST.md`
