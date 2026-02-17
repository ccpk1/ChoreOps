# Initiative Plan: ChoreOps full rebrand

## Initiative snapshot

- **Name / Code**: ChoreOps Full Rebrand (`CHOREOPS-REBRAND-001`)
- **Target release / milestone**: v0.5.0 (current track: v0.5.0-beta5/schema 45 → v0.5.0)
- **Owner / driver(s)**: Repo maintainers (`@ccpk1` + active contributors), release manager TBD
- **Status**: In progress (Phases 1 and 4 complete; Phase 5 validation/release steps in progress on beta 5 / schema 45)

## Summary & immediate steps

| Phase / Step                                   | Description                                                | % complete | Quick notes                                                                                                              |
| ---------------------------------------------- | ---------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------ |
| Phase 1 – Governance & legal baseline          | Lock naming scope, legal obligations, and migration policy | 100%       | Decisions captured and validated in this phase                                                                           |
| Phase 2 – Public-facing rebrand                | Update README/wiki/community/repo presentation             | 65%        | README + metadata + active root docs rebrand completed; templates/translations/util docs remain                          |
| Phase 3 – GitHub automation & templates        | Rebrand workflows, issue templates, and maintainer agents  | 40%        | Repo-guard + issue template naming updates done; Crowdin path and maintainer guide alignment still pending               |
| Phase 4 – Integration runtime/domain migration | Rebrand integration internals with compatibility strategy  | 100%       | Canonical identity + package path complete; continuity/fixtures/constants done; deprecation policy and PR guardrails set |
| Phase 5 – Validation, release, and deprecation | End-to-end verification and communication rollout          | 40%        | Quality gates + focused migration/compat tests complete; release comms/workflow validation pending                       |

1. **Key objective** – Rebrand all project surfaces from KidsChores to ChoreOps, including the fundamental package path migration from `custom_components/kidschores` to `custom_components/choreops`, while preserving existing users through an explicit compatibility and migration strategy.
2. **Summary of recent work**

- Phase 1: Completed governance/legal baseline with explicit naming matrix, migration policy, licensing resolution decision, branding policy, and release governance ownership.
- Phase 2: Rebranded package metadata (`hacs.json`, `pyproject.toml`, `manifest.json`) and active root docs (`ARCHITECTURE.md`, `DEVELOPMENT_STANDARDS.md`, `QUALITY_REFERENCE.md`, `DASHBOARD_TEMPLATE_GUIDE.md`, plus checklist/review docs) to ChoreOps terminology and canonical domain/storage examples.
- Phase 3: Updated workflow repo guard in `.github/workflows/validate.yaml` and rebranded issue-template naming to ChoreOps; remaining scope is Crowdin path alignment and maintainer guide cleanup.

- Phase 4: Implemented scoped storage move to `.storage/choreops/choreops_data`, added legacy migration option in config flow (`Migrate from KidsChores`), centralized legacy artifact discovery/migration helpers in `migration_pre_v50.py`, and refactored config flow to thin migration hooks for easier one-release removal.
- Phase 4: Extracted legacy migration constants into `migration_pre_v50_constants.py`, corrected legacy storage fallback behavior to root-only `.storage/kidschores_data` probing, and removed duplicate button setup cleanup so orphan cleanup remains manager-owned.
- Phase 4: Completed Option 1 milestone by activating canonical runtime identity constants (`DOMAIN = "choreops"`, `STORAGE_KEY = "choreops_data"`), aligning `manifest.json` domain/name/docs/issue tracker, and retaining a legacy domain alias constant for transition logic.
- Phase 4: Completed package-path migration milestone by moving integration sources to `custom_components/choreops`, adding a legacy package compatibility shim at `custom_components/kidschores/__init__.py`, and bulk-updating active import/path references.
- Phase 4: Verified active code/test references contain no stale `custom_components.kidschores` or `custom_components/kidschores` paths except the intentional compatibility shim.
- Phase 5: Validation gates and release checklist dependencies identified from `utils/quick_lint.sh`, `mypy`, pytest suite, and `docs/RELEASE_CHECKLIST.md`.
- Scope guardrails captured: domain/storage-key rename required; internal Python variable names remain unchanged to reduce regression risk.

3. **Next steps (short term)**

- Continue Phase 2 remaining work (README, dashboard templates, translation copy, utility docs) while preserving Phase 1 guardrails.
- Start Phase 3 implementation in parallel for workflow/template renames.
- Continue Phase 5 with workflow validation, release communication updates, and hard-cut execution gating for v0.5.0 final.
- Add explicit hard-cut milestone to remove `custom_components/kidschores/__init__.py` after transition-window exit criteria are met.
- Prepare HACS preflight checks to run immediately after hard-cut removal of the `kidschores` compatibility package path.
- Track hard-cut release target as `v0.5.0` final (current train: beta5/schema45).

4. **Risks / blockers**
   - Domain rename (`kidschores` → `choreops`) can break existing installations if migration/aliasing is incomplete.
   - Storage key change (`kidschores_data`) can cause data loss perception without one-time migration + backup checks.
   - External dependencies (dashboard repo naming, wiki URLs, badges, HACS listing expectations) may require coordinated repo-level changes.
   - License metadata inconsistency must be resolved with an explicit licensing decision and attribution policy.

- Renaming internal variable names during rebrand would add avoidable regression risk and is explicitly out of scope.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [custom_components/choreops/manifest.json](../../custom_components/choreops/manifest.json)
   - [pyproject.toml](../../pyproject.toml)
   - [LICENSE](../../LICENSE)
   - [.github/workflows/validate.yaml](../../.github/workflows/validate.yaml)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Rebrand execution model: staged rollout (public assets first, runtime/domain second).
     - Compatibility policy: preserve existing users by default, then deprecate legacy identifiers with warning window.
     - Legal policy: complete license and attribution review before public release tagging.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, migration notes, release communications) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Update percentages, blockers, and decisions after each merged PR in this initiative.
- **Detailed tracking**: Keep implementation details in phase sections; do not move detailed task logs into the summary table.

## Detailed phase tracking

### Phase 1 – Governance & legal baseline

- **Goal**: Freeze scope, naming standards, legal constraints, and migration policy before implementation.
- **Steps / detailed work items**
  - [x] Define canonical naming matrix (project, integration display name, domain, storage key, repo, dashboard repo)
    - Files to inspect/update: `README.md` (title/badges, ~L1-20), `custom_components/choreops/manifest.json` (~L1-12), `hacs.json` (~L1-5), `crowdin.yml` (~L1-30)
    - Owner: Maintainers
    - Decision (2026-02-16):
      - Project brand/display name: `ChoreOps`
      - Runtime domain target: `choreops`
      - Storage key target: `choreops_data`
      - Package path target: `custom_components/choreops`
      - Legacy attribution text: `Based on KidsChores`
  - [x] Approve domain migration policy (`kidschores` compatibility alias window vs hard cutover)
    - Files: `custom_components/choreops/__init__.py`, `custom_components/choreops/coordinator.py`, migration modules (`migration_pre_v50.py` and/or new migration file)
    - Decision artifact: add policy section to this plan under Notes
    - Decision (2026-02-16): hard-cut target domain is `choreops` with temporary compatibility handling for legacy identifiers during deprecation window.
  - [x] Resolve licensing and attribution policy
    - Verify and reconcile `LICENSE` (GPL-3.0 text) with `pyproject.toml` (`license = { text = "MIT" }`, ~L11)
    - Confirm obligations for fork attribution in README/wiki and release notes
    - Optional outputs: `NOTICE`/`COPYRIGHT` policy doc if required
    - Decision (2026-02-16): license source-of-truth remains `LICENSE` (GPL-3.0); `pyproject.toml` license metadata must be corrected to match before release.
  - [x] Define branding/trademark content policy
    - Files: `README.md`, `.github/ISSUE_TEMPLATE/*.yml`, docs pages using “KidsChores” brand text
    - Include policy for historical references in `docs/completed/legacy-kidschores/`
    - Decision (2026-02-16): keep `docs/completed/legacy-kidschores/` immutable as historical archive; active docs and user-facing assets move to ChoreOps terminology.
  - [x] Define release governance and comms ownership
    - Files: `docs/RELEASE_CHECKLIST.md`, `.github/ISSUE_TEMPLATE/config.yml`, maintainers’ docs in `.github/agents/`
    - Decision (2026-02-16): release manager accountable for final checklist sign-off (lint/tests/mypy + migration validation) before tag.
- **Key issues**
  - None open in Phase 1; decisions documented and ready for implementation phases.

### Phase 2 – Public-facing rebrand

- **Goal**: Rebrand all external communication surfaces without breaking runtime behavior.
- **Steps / detailed work items**
  - [x] Rebrand repository README and badges/links
    - File: `README.md` (badges and links around ~L1-10, product name around ~L9-30, install/docs links throughout)
    - Replace old repo links, wiki links, and dashboard references.
  - [x] Rebrand HACS and package metadata text
    - Files: `hacs.json`, `pyproject.toml` (`name`, `description`, `authors`), `custom_components/choreops/manifest.json` (`name`, URLs)
  - [x] Rebrand docs set for active docs (not archival)
    - Files: `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`, `docs/QUALITY_REFERENCE.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`
    - Preserve `docs/completed/legacy-kidschores/` as historical archive unless explicitly migrated.
  - [ ] Rebrand dashboard templates and user-facing markdown strings
    - Files: `custom_components/choreops/templates/dashboard_admin.yaml`, `dashboard_full.yaml`, `dashboard_minimal.yaml`
    - Update help text and dashboard repo links (currently `ccpk1/kidschores-ha-dashboard`).
  - [ ] Rebrand localization source copy and user-facing strings
    - Files: `custom_components/choreops/translations/en.json`, `translations_custom/en_dashboard.json`, `translations_custom/en_notifications.json`
    - Ensure translation key IDs remain stable unless migration strategy requires changes.
    - For newly introduced user-facing migration/deprecation copy, add explicit `TRANS_KEY_*` constants in `custom_components/choreops/const.py` and map them in English translation files before localization sync.
  - [ ] Update auxiliary utility docs and script references
    - Files: `utils/README.md`, `utils/quick_lint.sh` (workspace path reference), utility markdown docs
- **Key issues**
  - Extensive link churn may create broken docs if wiki/repo targets are not created first.
  - Translation key renames can create unnecessary churn; prefer value-text updates unless required.

### Phase 3 – GitHub automation & templates

- **Goal**: Rebrand collaboration workflows, CI guards, templates, and maintainer automation artifacts.
- **Steps / detailed work items**
  - [x] Update workflow repository guards and references
    - Files: `.github/workflows/validate.yaml` (repo check around ~L14), `.github/workflows/translation-sync-manual.yaml`, `.github/workflows/lint-validation.yaml`
    - Replace `ad-ha/kidschores-ha` references and update path filters if directory/domain changes.
  - [x] Rebrand issue templates and labels language
    - Files: `.github/ISSUE_TEMPLATE/01-issue_report.yml`, `.github/ISSUE_TEMPLATE/02-feature_reques.yml`, `.github/ISSUE_TEMPLATE/config.yml`
    - Update integration name, logging namespace examples, and title prefixes if needed.
  - [ ] Rebrand maintainer/agent guides under `.github/agents/`
    - Files include: `KidsChores Builder.agent.md`, `KidsChores Strategist.agent.md`, `KidsChores Documentarian.md`, `KidsChores Maintainer.md`, `KidsChores Test Builder.agent.md`
    - Align operational commands and naming with final domain strategy.
  - [ ] Review funding/governance metadata
    - Files: `.github/FUNDING.yml`, (add/update) `CODEOWNERS`, (optional) PR template if standardizing contributor intake
  - [ ] Add/refresh CI policy checks for brand regressions
    - Add grep-based check in CI to prevent reintroduction of deprecated brand/domain strings in active files.
- **Key issues**
  - Workflow changes can silently disable CI if triggers or repo conditions are incorrect.
  - Agent docs and contributor templates can drift from runtime naming if done before Phase 4 decisions.

### Phase 4 – Integration runtime/domain migration

- **Goal**: Complete technical rename to ChoreOps with explicit backward compatibility and safe data migration.
- **Steps / detailed work items**
  - [x] Apply canonical runtime identity constants (required)
    - Rename `const.DOMAIN` to value `"choreops"`
    - Rename `const.STORAGE_KEY` to value `"choreops_data"`
    - Ensure all call sites consume the renamed constants without changing unrelated business logic
    - Files: `custom_components/choreops/const.py`, `custom_components/choreops/__init__.py`, `custom_components/choreops/coordinator.py`, storage/migration helpers
  - [x] Finalize integration domain migration contract
    - Required target: runtime domain value is `choreops`
    - Include compatibility handling for legacy `kidschores` references during transition window
    - Core files: `custom_components/choreops/manifest.json`, `const.py` (`DOMAIN`), services and logger namespaces
  - [x] Execute package path migration as a dedicated milestone
    - Rename directory: `custom_components/kidschores` → `custom_components/choreops`
    - Update all Python import paths: `custom_components.kidschores.*` → `custom_components.choreops.*`
    - Update all path-based references in tests, docs, scripts, and workflows to the new directory
    - Add temporary compatibility bridge for old imports where feasible (or explicit hard-cut release notes if bridge is not feasible)
    - Gate completion: no active-file references to old package path outside intentional legacy migration fixtures
    - Implemented bridge: `custom_components/kidschores/__init__.py` delegates legacy imports to `custom_components.choreops`
  - [x] Implement storage migration plan if keys/paths change
    - Current storage key/path references: `.storage/kidschores_data` in docs, constants, tests, and migration samples
    - Add one-time migration routine and backup/rollback behavior for existing users
    - If storage payload structure or keys change, increment schema version constant and add `_migrate_to_v{N}()` flow with explicit idempotency checks
    - Must explicitly migrate `kidschores_data` → `choreops_data` and preserve all existing records/metadata
  - [x] Validate Home Assistant continuity after package path migration
    - Verify config entry setup/unload, discovery, and service registration still function with the new package path
    - Explicitly test upgrade path from existing installs referencing the legacy package layout
    - Evidence (2026-02-17):
      - `python -m pytest tests/test_config_flow_use_existing.py tests/test_config_flow_fresh_start.py tests/test_migration_hardening.py tests/test_chore_services.py tests/test_due_date_services_enhanced_frequencies.py -v --tb=line` → ✅ 87 passed, 0 failed
  - [x] Rebrand documentation URL constants and dashboard release repo constants
    - File: `custom_components/choreops/const.py` (wiki links, dashboard repo name around current constants block)
    - Result (2026-02-17): all `DOC_URL_*` wiki links moved from `ad-ha/kidschores-ha` to `ccpk1/choreops`; `DASHBOARD_RELEASE_REPO_NAME` updated to `choreops-ha-dashboard`.
    - Validation: `./utils/quick_lint.sh --fix` → ✅ passed
  - [x] Update integration manifest branding and attribution
    - File: `custom_components/choreops/manifest.json`
    - Required fields:
      - `name`: change to `"ChoreOps"`
      - `documentation` and `issue_tracker`: update to new repository URLs
      - Add explicit credit text: `"Based on KidsChores"` in manifest-supported metadata or release-facing documentation if manifest schema does not support custom credit fields
    - Validate with hassfest to ensure schema compliance after attribution placement decision
    - Result (2026-02-17): `manifest.json` branding fields are aligned (`domain`, `name`, `documentation`, `issue_tracker`). Attribution is tracked for release-facing notes because manifest schema has no custom credit field.
  - [x] Update migration fixtures and legacy compatibility tests
    - Files: `tests/migration_samples/*kidschores*`, `tests/test_migration_hardening.py`, flow/setup tests
    - Result (2026-02-17): audited references and kept legacy-named fixtures intentionally as migration-input artifacts; compatibility tests pass against current migration path.
    - Evidence:
      - `python -m pytest tests/test_config_flow_use_existing.py tests/test_migration_hardening.py -v --tb=line` (included in Phase 4 HA continuity run) → ✅ passed
      - `grep -RInE "kidschores|custom_components\\.kidschores|custom_components/kidschores" tests/migration_samples tests/test_migration_hardening.py tests/test_config_flow_use_existing.py` → legacy markers found only in migration fixtures/tests by design
  - [x] Enforce variable-name freeze for internal data code paths
    - Keep internal variable names like `kid_id`, `parent_data`, and similar domain-variable identifiers unchanged
    - Restrict rename scope to integration identity constants, package paths, metadata, and user-facing branding
    - Add PR review checklist item: reject cosmetic internal variable renames not required for rebrand behavior
    - Implemented in `.github/PULL_REQUEST_TEMPLATE.md` rebrand guardrail checklist
  - [x] Publish explicit deprecation policy
    - Define warning period for legacy domain/entity IDs and a final removal version
    - Define legacy package import compatibility window for `custom_components.kidschores.*`
    - Hard-cut action at end of window: remove `custom_components/kidschores/__init__.py`
    - Hard-cut acceptance criteria:
      - No active code/docs/tests import `custom_components.kidschores.*`
      - Compatibility tests pass without alias package
      - Release notes include a breaking-change callout and migration snippet
    - Policy (2026-02-17):
      - Compatibility shim remains in `v0.5.0-beta5`
      - Shim emits `DeprecationWarning` for legacy import path usage
      - Hard cut scheduled for `v0.5.0` final: remove `custom_components/kidschores/__init__.py`
- **Key issues**
  - Hard domain rename has highest blast radius (entity IDs, service names, logger keys, integrations config entries).
  - Incomplete migration handling can orphan user data or create duplicate integrations.

### Phase 5 – Validation, release, and deprecation

- **Goal**: Prove functional stability, publish migration guidance, and release safely.
- **Steps / detailed work items**
  - [x] Run quality gates on final branch
    - Commands: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/` (or new module path), `python -m pytest tests/ -v --tb=line`
  - [x] Execute focused migration and compatibility tests
    - Prioritize: config flow migration, setup/unload, storage migration, dashboard generation, services, translations
    - Candidate files: `tests/test_migration_hardening.py`, `tests/test_config_flow_*.py`, `tests/test_yaml_setup.py`, `tests/test_translations_custom.py`
  - [ ] Validate GitHub workflows end-to-end on PR + main
    - Ensure `validate`, `hassfest`, lint, and translation-sync jobs execute with correct repo/path assumptions
  - [ ] Prepare release package and communication assets
    - Update changelog/release notes with migration warnings and exact upgrade steps
    - Update wiki pages and “known impacts” section for domain/storage changes
  - [ ] Post-release monitoring and rollback window
    - Define 7-14 day post-release triage protocol and emergency rollback path
- **Key issues**
  - Release without migration docs will drive avoidable support load.
  - CI passing is necessary but insufficient; real-world upgrade path must be tested from legacy installs.

## Testing & validation

- **Planned test suites**
  - Full quality gate: `./utils/quick_lint.sh --fix`
  - Type checking: `mypy custom_components/choreops/` (and legacy-path checks only during compatibility window)
  - Test suite: `python -m pytest tests/ -v --tb=line`
  - Focused migration tests: `python -m pytest tests/test_migration_hardening.py -v --tb=line`
  - Focused config flow tests: `python -m pytest tests/test_config_flow_*.py -v --tb=line`
  - Regression guards:
    - `grep -r "DOMAIN\s*=\s*\"kidschores\"" custom_components/ tests/` should return no active matches
    - `grep -r "kidschores_data" custom_components/ tests/` should only match intentional migration fixtures and compatibility paths
- **Outstanding tests**
  - Validation commands intentionally deferred for Phase 1 (plan-only work, owner-approved).
- **CI validation requirement**
  - All GitHub workflows related to validation, hassfest, and translation sync must pass on the rebrand branch before tagging.

### Phase 1 validation results (2026-02-16)

- `./utils/quick_lint.sh --fix`: not run (plan-only phase, owner-directed defer)
- `mypy custom_components/choreops/`: not run (plan-only phase, owner-directed defer)
- `python -m pytest tests/ -v --tb=line`: not run (plan-only phase, owner-directed defer)

### Phase 4 migration subset validation results (2026-02-16)

- `python -m pytest tests/ -v --tb=line`: ✅ passed (1432 passed, 0 failed)

### Phase 4 migration hook-refactor validation results (2026-02-16)

- `./utils/quick_lint.sh --fix`: ✅ passed
- `python -m pytest tests/test_config_flow_use_existing.py tests/test_config_flow_error_scenarios.py tests/test_points_migration_validation.py tests/test_backup_utilities.py -v --tb=line`: ✅ passed (50 passed, 0 failed)
- `python -m pytest tests/ -v --tb=line`: ✅ passed (1432 passed, 0 failed)

### Phase 4 migration hardening validation results (2026-02-17)

- `./utils/quick_lint.sh --fix`: ✅ passed
- `python -m pytest tests/test_kiosk_mode_buttons.py tests/test_shadow_kid_buttons.py tests/test_points_migration_validation.py -v --tb=line`: ✅ passed (20 passed, 0 failed)

### Phase 4 Option 1 contract validation results (2026-02-17)

- `./utils/quick_lint.sh --fix`: ✅ passed
- `pytest tests/test_backup_utilities.py tests/test_config_flow_fresh_start.py tests/test_points_migration_validation.py`: ✅ passed (47 passed, 0 failed)

### Phase 4 Option 1 package-path validation results (2026-02-17)

- `./utils/quick_lint.sh --fix`: ✅ passed
- `python -m pytest tests/test_config_flow_fresh_start.py tests/test_backup_utilities.py tests/test_points_migration_validation.py tests/test_shared_chore_features.py tests/test_kiosk_mode_buttons.py -v --tb=line`: ✅ passed (76 passed, 0 failed)
- `grep -RInE "custom_components\\.kidschores|custom_components/kidschores" custom_components tests .github README.md pyproject.toml --exclude-dir=.git`: ✅ only intentional compatibility shim match remains

### Phase 4 HA continuity verification results (2026-02-17)

- `python -m pytest tests/test_config_flow_use_existing.py tests/test_config_flow_fresh_start.py tests/test_migration_hardening.py tests/test_chore_services.py tests/test_due_date_services_enhanced_frequencies.py -v --tb=line`: ✅ passed (87 passed, 0 failed)

### Planned hard-cut checkpoint (to schedule before v0.5.0 final)

- Remove compatibility alias package: `custom_components/kidschores/__init__.py`
- Re-run active reference guard:
  - `grep -RIn "custom_components.kidschores" custom_components tests .github README.md pyproject.toml --exclude-dir=.git`
  - expected result: 0 matches
- Run full quality gates and migration tests before tagging release.

### Planned post-hard-cut HACS readiness checks (pre-release, no publish yet)

- Remove `custom_components/kidschores/` compatibility package path so only one integration directory remains under `custom_components/`.
- Confirm HACS and manifest validation gates pass on `main`:
  - `.github/workflows/validate.yaml` (`hacs/action`) ✅
  - `.github/workflows/hassfest.yaml` ✅
- Verify repository metadata for HACS inclusion checks:
  - GitHub repository description is populated
  - GitHub topics are populated
  - Issues remain enabled
- Finalize README quality gate for HACS:
  - remove placeholder TODO markers
  - remove or defer badges that require releases until first release exists
  - keep installation/use instructions accurate for custom repository installs
- Prepare Home Assistant brands submission package for `choreops`:
  - target path: `home-assistant/brands/custom_integrations/choreops/`
  - required baseline files: `icon.png` (256x256), `icon@2x.png` (512x512)
  - optional but recommended: `logo.png`, `logo@2x.png`, and dark variants (`dark_icon.png`, `dark_logo.png`, etc.)
- GitHub release creation is intentionally deferred until final release readiness; do not publish release assets during this preparation stage.

### Phase 4 deprecation + guardrail implementation results (2026-02-17)

- `custom_components/kidschores/__init__.py`: compatibility shim now emits deprecation warning for legacy package path
- `.github/PULL_REQUEST_TEMPLATE.md`: added rebrand guardrail checklist including variable-name freeze
- `custom_components/choreops/manifest.json`: branding fields aligned; attribution placement delegated to release-facing notes per schema limits

### Phase 5 validation results (2026-02-17)

- `./utils/quick_lint.sh --fix`: ✅ passed
  - Ruff check/format: passed
  - MyPy (production integration scope): passed (`49 source files`)
  - Boundary checks: passed
- Focused migration/compatibility run:
  - `python -m pytest tests/test_migration_hardening.py tests/test_config_flow_fresh_start.py tests/test_config_flow_use_existing.py tests/test_yaml_setup.py tests/test_translations_custom.py -v --tb=line` → ✅ passed (`143 passed`)
- Rebrand regression fixes applied for stale legacy assertions/paths in:
  - `tests/test_event_infrastructure.py`
  - `tests/test_notification_helpers.py`
  - `tests/test_rotation_services.py`
  - `tests/test_workflow_notifications.py`
- Full suite release gate:
  - `python -m pytest tests/ -v --tb=line` → ✅ passed (`1432 passed, 2 skipped, 2 deselected`)

## Notes & follow-up

- **Scope boundary recommendation**
  - Keep `docs/completed/legacy-kidschores/` as immutable historical records; only add a short notice file mapping KidsChores → ChoreOps to avoid rewriting archive history.
- **Migration sequencing recommendation**
  - Execute in two releases if needed:
    1. `v0.6.0-beta1`: full public-facing rebrand + internal compatibility shims.
    2. `v0.6.0`: finalize runtime/domain migration after upgrade telemetry and test confidence.
- **Phase 1 policy decisions (locked 2026-02-16)**
  - `const.DOMAIN` target value: `choreops`
  - `const.STORAGE_KEY` target value: `choreops_data`
  - `manifest.json` branding target: `name = "ChoreOps"`, docs/issue links updated, explicit credit `Based on KidsChores`
  - Internal variable freeze: keep `kid_id`, `parent_data`, and equivalent internal variable names unchanged unless required for failing migrations/tests
- **Non-goal (stability control)**
  - Do not rename internal Python working variables (`kid_id`, `parent_data`, etc.) as part of rebrand unless a change is required to fix a failing migration/test.
- **Licensing references for implementation phase**
  - GPL-3.0 license obligations (source availability + preserved notices) should be reflected in release notes and fork attribution.
  - `pyproject.toml` license metadata must align with `LICENSE` before release packaging.
- **GitHub ecosystem follow-up items**
  - If repository rename occurs, implement redirect checks for badges, wiki URLs, issue links, and dashboard companion repo links.
  - Reconfirm Crowdin project mapping and secrets ownership after repo/branch naming changes.
- **Attribution implementation status**
  - Explicit fork attribution is now present in [README.md](../../README.md) with credit to the original KidsChores creator; release notes should repeat this attribution callout at tag time.
- **Top-level non-docs scan (2026-02-17, docs excluded)**
  - Updated now:
    - [.github/workflows/validate.yaml](../../.github/workflows/validate.yaml): repo guard switched to `ccpk1/choreops`
    - [.github/ISSUE_TEMPLATE/01-issue_report.yml](../../.github/ISSUE_TEMPLATE/01-issue_report.yml): integration naming updated to ChoreOps
    - [.github/ISSUE_TEMPLATE/02-feature_reques.yml](../../.github/ISSUE_TEMPLATE/02-feature_reques.yml): integration naming updated to ChoreOps
    - [pyproject.toml](../../pyproject.toml): project metadata rebranded (`name = "choreops"`, ChoreOps description/authors)
    - [crowdin.yml](../../crowdin.yml): translation source/target paths updated to `custom_components/choreops/*`
    - [.pylintrc](../../.pylintrc): top comment banner updated to ChoreOps
    - [AGENTS.md](../../AGENTS.md): operational commands and storage path examples updated to `choreops`
  - Remaining top-level references to evaluate in Phase 2/3:
    - None (non-doc top-level scan complete; README intentionally deferred)
  - Deferred by owner direction (full rewrite planned):
    - [README.md](../../README.md)
