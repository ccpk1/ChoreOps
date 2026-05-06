# Initiative snapshot

- **Name / Code**: Dashboard helper hybrid sharding / `DASHBOARD_HELPER_HYBRID_SHARDING`
- **Target release / milestone**: TBD after prototype and dashboard complexity review; candidate for next dashboard-focused feature release
- **Owner / driver(s)**: TBD
- **Status**: Phase 4 in progress

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Contract review and prototype shape | Define the helper-pointer contract and decide what stays inline vs moves to companion helpers | 100% | Contract, lifecycle, compatibility matrix, and guide updates are documented |
| Phase 2 – Backend helper sharding | Add runtime-owned companion helper surfaces for large chore payloads and auxiliary data | 100% | Runtime shard plans, companion helper sensors, and targeted validation are complete |
| Phase 3 – Shared dashboard snippet migration | Update shared snippets to resolve, merge, and cache chore shards in memory once per card | 100% | Canonical branch `ccpk1/issue124` created; shared chore-engine snippets now merge shard helpers and rebuild labels from merged rows |
| Phase 4 – Testing, thresholds, and rollout | Validate size gains, template responsiveness, and backward compatibility | 75% | Added 120-density acceptance coverage, shard lifecycle/reload/orphan diagnostics tests, a strict one-edit cross-user flip case, a passing full opted-in stress matrix, and a verified dev-runtime startup fix; closeout is currently blocked by reload and small-edit helper-pointer regressions and live manual validation remains open |

1. **Key objective** – Preserve the current dashboard authoring model of “resolve helper once per card, work from local in-memory data” while allowing the main helper to point at an ordered list of additional chore UI helpers under `dashboard_helpers.chore_helper_eids` when the inline `chores` payload becomes too large, so the same contract scales naturally from one shard to many.
2. **Summary of recent work** –
   - Reviewed the current helper payload builder in `custom_components/choreops/sensor.py` around lines 4603-5078 and confirmed the main helper currently mixes chores, gamification, UI control, sensor pointers, and approvals in one attribute surface.
   - Reviewed the shared chore engine in `custom_components/choreops/dashboards/templates/shared/chore_engine/context_v1.yaml` and `prepare_groups_v1.yaml` around lines 1-260 and confirmed all maintained chore dashboards already normalize a single `chore_list` in one central place.
   - Reviewed `custom_components/choreops/dashboards/templates/user-gamification-premier-v1.yaml` around lines 82-130 and 354-430 and confirmed complex dashboards still follow the same core pattern: resolve `dashboard_helper`, pull needed attributes into local variables, then render from that in-memory data.
   - Reviewed the helper pointer precedent in `docs/ARCHITECTURE.md` around lines 782-787 and confirmed translation indirection already demonstrates a successful size-reduction pattern via helper pointers.
3. **Next steps (short term)** –
  - Phase 3 shared-snippet migration is complete in the canonical dashboard repo and synced into the vendored runtime mirror.
  - Maintained chore dashboards now merge shard helper payloads once per card through the shared chore-engine snippets instead of relying on backend `chores_by_label` transport.
  - Phase 4 now includes targeted lifecycle validation for shard mode, reload reconstruction, orphan cleanup, runtime diagnostics, and an above-100 acceptance scenario at 120 chores per assignee.
  - The opt-in dense stress module now understands shard-backed helpers and the full opted-in stress matrix passes across 40-120 chores per assignee.
  - The local dev Home Assistant instance now loads the integration again after correcting the `core/custom_components` symlink and fixing pre-attach shard planning to tolerate an unset entity `hass` reference.
  - Live manual validation is no longer blocked by the startup failure, but dashboard responsiveness and authenticated dense-scenario load checks are still pending.
  - The remaining technical blocker is shard-helper pointer publication on the main helper after reload and some ordinary edit paths: companion helper entities register with the expected `ui_dashboard_chore_list` naming contract, but the main helper can still publish `dashboard_helpers.chore_helper_eids = []` in those flows.
  - Preserve the closed Phase 1 and Phase 2 contracts as the implementation source of truth; do not reopen approved naming, threshold, or runtime-plan decisions without new evidence.
4. **Risks / blockers** –
   - Jinja can merge lists dynamically, but repeated `state_attr()` calls inside loops will hurt dashboard responsiveness if the contract is not designed to resolve shard payloads once per card.
   - A multi-helper merge contract is feasible in shared snippets, but debugging broken pointers or partial helper availability will be more complex than the current single-helper model.
   - Backward compatibility matters because existing power-user dashboards may read helper attributes directly instead of going through shared snippets.
  - If shard discovery becomes too dynamic, template readability and support burden may grow faster than the size benefit.
  - Current lifecycle behavior is not yet fully stable: focused shard tests still show reload and small-edit flows where the main helper loses the resolved shard pointer list even though companion helper entities are registered.
   - Dashboard authoring source-of-truth rules matter here: canonical template edits belong in `ccpk1/ChoreOps-Dashboards`, then must be synced into the integration repo via `python utils/sync_dashboard_assets.py` and parity-checked before validation.
5. **References** –
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [docs/DASHBOARD_TEMPLATE_GUIDE.md](../DASHBOARD_TEMPLATE_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep the current dashboard ergonomics: one helper resolution per card, then local in-memory processing.
     - Treat shared dashboard snippets as the main migration surface; avoid per-template custom merge logic where possible.
     - Use the existing translation-sensor pointer pattern as the architectural precedent for helper indirection.
     - Prefer runtime-computed shard pointers over new persistent storage fields unless later requirements force stored shard policy.
     - Focus the first iteration on chores, but define the contract so the same sharding pattern can be reused for rewards, badges, approvals, or future helper-heavy surfaces.
     - Design the chores contract for multi-helper expansion from day one; do not hard-code a single extra chore helper assumption into helper names, pointer fields, or Jinja merge logic.
     - All implementation work for this initiative must continue to adhere to the standing repository contracts in [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md), [docs/DASHBOARD_TEMPLATE_GUIDE.md](../DASHBOARD_TEMPLATE_GUIDE.md), and [docs/ARCHITECTURE.md](../ARCHITECTURE.md) outside the specific helper-sharding changes being introduced.
     - Dashboard template source edits for this initiative must be made in `ccpk1/ChoreOps-Dashboards`, then synced into the integration vendored runtime mirror using `python utils/sync_dashboard_assets.py` and verified with `python utils/sync_dashboard_assets.py --check`.
     - `user-chores-essential-v1` is an explicit non-goal for scale extension in this initiative; manual and automated validation focus on maintained profiles that are expected to scale further, especially `user-gamification-premier-v1` and `user-chores-standard-v1`.
     - Shard pointers for chores will live at `dashboard_helpers.chore_helper_eids`, and that field must always be present as a list, including `[]` when no chore shards exist.
     - `chores_by_label` will be removed from backend helper transport and rebuilt from merged `chores` rows in shared dashboard snippets; this change must be validated across all dashboard templates, including `user-chores-essential-v1`, even though essentials remains a non-goal for extended-scale support.
     - Chore sharding is threshold-triggered, not always-on, and the contract is mutually exclusive at scale: the helper will use either inline `chores` or shard-backed `chores`, but not both in parallel for the same user state.
     - Once sharding is triggered, dedicated chore shard helpers should carry only chore-row payload for this initiative unless a later measurement proves minimal metadata is required for diagnosability.
     - Dashboards must consume shard helpers only via the ordered entity IDs exposed by the main helper; helper naming patterns are backend-managed and not part of the dashboard contract.
     - For the broader architecture, prefer a reusable shard-helper implementation internally, but keep public shard-helper surfaces typed by payload family so chores, rewards, or future overflow families each retain clear contracts, names, and diagnostics.
     - Missing-shard behavior should stay simple in v1: render the data that is available, avoid over-engineering recovery paths, and provide only minimal diagnostics needed for support.
     - Whether a user is in inline mode or shard mode must be runtime-owned state, not persisted storage configuration and not something recomputed ad hoc only inside `extra_state_attributes`.
     - Shard lifecycle should follow the recent chore runtime-sync approach: reconcile adds/removals through a single mutation-driven orchestration path, then let helper attributes read the resulting runtime plan.
    - To avoid threshold flapping for users near the limit, shard-mode activation must use hysteresis with separate enter/exit guards rather than a single exact cutoff.
    - Shard lifecycle ownership for v1 is assigned to `ui_manager`; do not introduce a separate dashboard-helper lifecycle manager unless implementation pressure later proves `ui_manager` has become too broad.
    - `ui_manager` owns startup reconciliation, reload reconciliation, unload cleanup of runtime shard plans, and post-mutation shard reconciliation for affected users.
    - Shard helper unique IDs must be stable across restarts and ordinary edit churn and must not be derived from current chore count, current payload size, or other unstable runtime-only measurements.
    - Shard reconciliation must accept all affected user IDs for a mutation, not just the most obvious edited user, so cross-user assignment churn can push one user into shard mode while pulling another out.
    - Shard-mode diagnostics must remain intentionally small but must be sufficient for support: current mode, expected shard count, resolved shard entity IDs, and last accepted size measurement or equivalent runtime evidence.
     - Chore shard helper naming for v1 is deterministic and typed: backend-managed unique IDs should use a stable chore-shard suffix with an explicit shard index, while human-facing names should follow the equivalent of `Chore List 1`, `Chore List 2`, and so on.
     - Shard mode must activate from final exact serialized helper size with hysteresis anchored below the 16 KB recorder ceiling: enter shard mode at or above 14 KB projected/finalized size and exit shard mode only after the accepted payload falls to 12 KB or below.
     - Minimal shard-helper diagnostic metadata for v1 is fixed to `purpose`, `shard_index`, `shard_count`, and `helper_contract_version`; size and reconciliation evidence belong on the main helper runtime diagnostic surface, not duplicated heavily on every shard.
     - The reusable typed-shard pattern documentation for v1 should name chores as the implemented family and rewards as the explicit next-family example so the pattern is concrete without widening current implementation scope.
     - The minimum `ui_manager` shard runtime plan for each user is fixed to mode, ordered shard membership, expected shard count, last accepted serialized size, and last reconciliation outcome.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Contract review and prototype shape

- **Goal**: Define a helper contract that supports threshold-triggered pointer-based chore sharding while preserving the current single-helper dashboard authoring experience below the threshold.
- **Status**: Complete
- **Steps / detailed work items**
  1. [x] Document the current helper field classes in `custom_components/choreops/sensor.py` around lines 4603-5078 as `row data`, `derived indexes`, `auxiliary catalogs`, and `plumbing/meta` so sharding decisions are made against explicit categories.
  2. [x] Document the current shared lookup and caching pattern in `custom_components/choreops/dashboards/templates/shared/chore_engine/context_v1.yaml` around lines 95-186 and `custom_components/choreops/dashboards/templates/shared/chore_engine/prepare_groups_v1.yaml` around lines 1-120 to identify the minimal snippet changes needed to support merged shard lists.
  3. [x] Define the main-helper contract in `docs/DASHBOARD_TEMPLATE_GUIDE.md` around the helper-field section near lines 780-860 with `dashboard_helpers.chore_helper_eids` as the canonical ordered pointer list and require the field to exist even when empty.
  4. [x] Lock the initial chore shard payload to `chores` rows only and explicitly reject parallel inline-plus-shard choreography for the same user state unless later testing proves that a tiny compatibility slice is required.
  5. [x] Document that `chores_by_label` is removed from backend transport, then map the shared-snippet and profile-level template updates required to rebuild label grouping from merged `chores` rows across premier, standard, and essentials templates.
  6. [x] Record the selected trigger model in this plan: threshold-triggered overflow-only chore spillover with mutually exclusive output modes (`inline` below threshold, `shards` above threshold).
  7. [x] Define the minimum supported shard count and scaling expectation for v1 planning, with the contract explicitly supporting at least two extra chore helpers even if the first implementation rarely needs them.
  8. [x] By the end of Phase 1, document the approved helper entity naming pattern, pointer field names, helper-key contract, and worked examples covering at least a 20-chore user and a 120-chore user.
  9. [x] Decide and document the future-family shard model: use one reusable backend shard-helper implementation pattern, but expose typed public shard-helper surfaces for each payload family rather than a single generic overflow sensor contract.
  10. [x] Add a compact compatibility matrix to the plan or guide covering maintained dashboards (`user-gamification-premier-v1`, `user-chores-standard-v1`) and explicit non-goals (`user-chores-essential-v1`) so rollout expectations are fixed before implementation starts.
  11. [x] Define the shard-mode lifecycle contract explicitly in `ui_manager`: where per-user mode/allocation state lives in runtime memory, what mutation classes trigger reconciliation, and the approved hysteresis policy of entering at 14 KB and exiting at 12 KB based on accepted serialized size.
  12. [x] Specify startup, reload, and unload behavior: how `ui_manager` rebuilds shard plans from current coordinator data on setup, how it reconciles registry/runtime mismatches on reload, and how runtime shard plans are cleared on unload.
  13. [x] Specify shard helper identity rules: stable unique ID pattern with typed chore-shard indexing, `Chore List N` display naming, and explicit prohibition on unique IDs that depend on current shard payload content or current item counts.
  14. [x] Record the full reconciliation trigger inventory for v1, including startup, reload, chore create, chore edit, chore delete, assignment churn, and user deletion.
  15. [x] Define the minimum `ui_manager` runtime plan structure for each user as mode, shard membership/order, expected shard count, last accepted serialized size, and last reconciliation outcome.
- **Phase 1 completion update (2026-05-05)**
  - Documented the current dashboard-helper payload classes and the shared snippet merge/caching contract in [docs/DASHBOARD_TEMPLATE_GUIDE.md](../DASHBOARD_TEMPLATE_GUIDE.md).
  - Wrote the approved shard contract into the guide, including `dashboard_helpers.chore_helper_eids`, shard payload shape, label reconstruction rules, compatibility matrix, worked examples, and future typed-family guidance.
  - Converted Phase 1 from open planning items to completed contract deliverables and updated the initiative summary to reflect Phase 1 completion.
- **Key issues**
  - The pointer list must be structurally stable, not optional; an always-present empty list is easier for templates than a missing key.
  - Threshold-triggered mode switching is acceptable here because the user explicitly wants `inline or shards`, not partial parallel transport.
  - If shard order matters for stable UI grouping or deterministic merges, the contract must define ordering explicitly.
  - A stable contract is more valuable than the smallest possible implementation. If the trigger rule creates multiple helper shapes that templates must special-case, the operational cost may outweigh the size win.
  - Naming approval cannot drift into Phase 2. If helper names and pointer keys are still unsettled when coding starts, backend and dashboard work will diverge quickly.
  - Reusing implementation is good, but a generic public “overflow shard” sensor type would blur payload semantics and make future rewards or approvals harder to reason about than typed shard surfaces.
  - If shard-mode selection is left inside helper rendering instead of a runtime lifecycle owner, entity creation and cleanup will become nondeterministic and will not meet the same bar as the recent chore runtime-sync work.
  - Startup, reload, and unload semantics must be treated as first-class contract items. If those are left implicit, runtime correctness will depend on incidental registry state rather than owned lifecycle behavior.

### Phase 2 – Backend helper sharding

- **Goal**: Design backend-owned shard helpers that reduce main helper size without giving up the open, entity-based architecture.
- **Steps / detailed work items**
  1. [x] Prototype a runtime helper layout in `custom_components/choreops/sensor.py` around lines 4119-4478 and 4603-5078 where the existing per-user helper continues to expose core metadata and `dashboard_helpers.chore_helper_eids` can point at an ordered list of additional per-user chore helper sensors.
  2. [x] Introduce one `ui_manager`-owned shard reconciliation path, parallel to chore runtime sync, that accepts affected user IDs after chore graph mutations and updates shard-helper entity presence before listener refresh.
  3. [x] Base shard-helper creation/cleanup on the existing translation-sensor lifecycle pattern where possible, but extend it with explicit per-user runtime plan tracking so shard mode and shard count are not inferred solely from registry lookups.
  4. [x] Define the minimal shard payload as `chores` only for the first release, allowing only minimal diagnostic metadata if support needs prove it is necessary.
  5. [x] Remove `chores_by_label` from backend transport and shift label reconstruction to merged-chores logic in shared snippets, while confirming the full dashboard-template impact including essentials.
  6. [x] Keep non-chore payloads on the main helper for the first release and document that future rewards or other overflow families should follow the same typed-shard pattern rather than reusing chore shard entities.
  7. [x] Define simple failure handling for missing shard helpers so dashboards degrade cleanly when one pointer resolves to `unknown`, `unavailable`, or a stale entity ID without introducing complex recovery behavior.
  8. [x] Define the byte-budget policy for helper emission in `custom_components/choreops/sensor.py` around lines 4603-5078 using the selected hybrid strategy: cheap estimation during assembly plus exact serialized-byte measurement at final emission.
  9. [x] Define hysteresis for shard mode using separate enter/exit thresholds so users near the boundary do not teeter between inline and shard mode on small edits.
  10. [x] Decide whether chore shard allocation should be `spill until full` or `balanced distribution` once more than one extra chore helper is needed, and document why that strategy is easier to reason about for future payload families.
  11. [x] Add deterministic shard-membership rules and shard cleanup rules so ordinary chore edits do not cause unnecessary reshuffling between helpers and helper removal is defined when households shrink back below the shard exit threshold.
  12. [x] Define the approved v1 shard diagnostic metadata surface as `purpose`, `shard_index`, `shard_count`, and `helper_contract_version`, with size and reconciliation evidence exposed from the main helper runtime diagnostics instead of every shard.
  13. [x] Implement startup reconciliation in `ui_manager` so shard plans are rebuilt from coordinator data and registry state is reconciled before dashboard helpers rely on `dashboard_helpers.chore_helper_eids`.
  14. [x] Implement reload/unload lifecycle handling so shard runtime plans are refreshed on reload, stale runtime state is cleared on unload, and orphan helper entities are cleaned up deterministically when needed.
  15. [x] Ensure shard reconciliation accepts and processes all affected user IDs for a mutation, including assignment transfers that can move shard pressure from one user to another in a single edit.
  16. [x] Keep shard helper unique IDs stable and backend-owned, with predictable registry lookup and cleanup behavior even as users cross the shard threshold in both directions.
  17. [x] Make the `ui_manager` shard runtime state family-aware from day one so future reward shard work can reuse the pattern without colliding with chore-specific runtime keys, and document rewards as the next planned typed-family example in the guide.
- **Key issues**
  - The backend should not create card-specific helpers; shard helpers must remain general-purpose per-user surfaces.
  - A chore-only shard model is easier to adopt than full multi-concern sharding and should be considered the first release candidate.
  - No `.storage` schema change should be required if shard policy is derived at runtime from current payload size and helper composition.
  - The runtime lifecycle owner should be `ui_manager`, not the dashboard-helper sensor itself. The sensor should read a prepared plan; it should not decide whether entities need to be created or removed.
  - An overflow-only spillover model is the smallest behavioral change, but it requires logic to decide exactly where the cut line falls and to keep the main helper under the budget deterministically.
  - A sequential paging model is simpler mechanically and generalizes better across payload families, but it makes helper semantics less obvious because data can move between numbered helpers as the household grows.
  - Even if the first rollout usually creates only one extra helper, the shard allocator and pointer field should not assume that ceiling. The next 80 chores should be an extension of the same contract, not a second redesign.
  - Future reuse should happen at the implementation level, not by publishing one generic shard-sensor contract for all payload families. Public sensor contracts should remain typed so troubleshooting and dashboard expectations stay obvious.
  - The recent chore runtime-sync work is the right quality bar here: mutation-driven orchestration, production-safe add/remove behavior, shared cleanup helpers, and no reload-era fallback should be the target shape for shard helpers too.
  - Cross-user mutations are part of the contract surface. A reconciliation path that only thinks in terms of one edited user will miss real assignment-churn cases and leave runtime/entity state inconsistent.

### Phase 3 – Shared dashboard snippet migration

- **Goal**: Update the maintained dashboard ecosystem to resolve and merge shard helpers once per card so dashboards stay responsive and template complexity stays centralized.
- **Steps / detailed work items**
  1. [x] Create a matching working branch in `ccpk1/ChoreOps-Dashboards` for the canonical template work associated with this integration branch, and record the branch/linkage in the plan summary once created.
  2. [x] Update `custom_components/choreops/dashboards/templates/shared/chore_engine/context_v1.yaml` around lines 95-186 so it reads `dashboard_helpers.chore_helper_eids`, resolves referenced helper entities once, and constructs one merged in-memory `chore_list` before grouping or rendering begins.
  3. [x] Update `custom_components/choreops/dashboards/templates/shared/chore_engine/prepare_groups_v1.yaml` around lines 1-260 so label grouping and sorting operate on merged chore rows and do not assume all chores came from a single helper entity.
  4. [x] Review `custom_components/choreops/dashboards/templates/user-gamification-premier-v1.yaml` around lines 354-430 and the chore-card sections around lines 215-289 to ensure the complex profile can adopt shard-aware shared snippets without bespoke card-local merge logic.
  5. [x] Review `custom_components/choreops/dashboards/templates/user-chores-standard-v1.yaml` and `user-chores-essential-v1.yaml` around their shared-snippet call sites to confirm the migration surface is truly centralized and to verify that removing `chores_by_label` does not break those templates.
  6. [x] Decide whether helper pointer resolution should be capped to a small number of shards per user, such as 2-4, to keep Jinja merge overhead predictable while still supporting the intended “80 becomes 160” expansion path.
  7. [x] Document a fallback behavior in `docs/DASHBOARD_TEMPLATE_GUIDE.md` for legacy dashboards that continue reading `state_attr(dashboard_helper, 'chores')` directly and therefore will not benefit from automatic shard merges once threshold-triggered sharding activates.
  8. [x] Run the required canonical-to-vendored workflow for every template change: update the dashboard repo source, sync into `custom_components/choreops/dashboards/`, and parity-check before integration validation.
  9. [x] Document the template-side assumptions for shard-mode diagnostics and partial-failure handling so shared snippets know exactly which runtime fields are safe to inspect and which missing-shard cases should simply degrade to partial render.
- **Phase 3 completion update (2026-05-05)**
  - Created the matching canonical dashboard branch `ccpk1/issue124` in `ccpk1/ChoreOps-Dashboards` for the template migration work.
  - Updated the shared chore-engine context snippet to resolve `dashboard_helpers.chore_helper_eids` once, merge shard-backed `chores` rows into one in-memory `chore_list`, and preserve inline mode when no shard helpers are present.
  - Updated the shared grouping snippet to rebuild label groups from filtered merged chore rows instead of relying on backend `chores_by_label` transport.
  - Confirmed maintained profile call sites remain centralized through the shared snippets, documented the no-cap pointer-resolution rule and legacy fallback behavior, and synced canonical assets into the vendored runtime mirror.
- **Key issues**
  - Jinja can merge lists from multiple helpers, but it must do so once into a local namespace variable rather than repeatedly querying helpers during grouping and sorting.
  - Because `chores_by_label` is being removed, label-group reconstruction becomes a mandatory shared-snippet responsibility and needs explicit verification across all templates, not just maintained scale targets.
  - Shared snippet changes are powerful, but they raise the importance of good debug surfaces when one shard pointer is broken.
  - The numbered step list must remain sequential after dashboard-repo branch setup is added; keep the final plan tidy before handoff.

### Phase 4 – Testing, thresholds, and rollout

- **Goal**: Prove that the hybrid shard design actually expands capacity while keeping template behavior acceptable and avoiding broad dashboard breakage.
- **Steps / detailed work items**
  1. [x] Extend `tests/test_dashboard_helper_density_stress.py` around lines 24-77 to add shard-aware scenarios once a prototype exists, measuring both recorder-limit compliance and the number of chores supported per assignee under the new contract.
  2. [x] Add scenario coverage using the YAML scenario framework described in `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` and the existing dense scenarios under `tests/scenarios/` to compare inline-only vs shard-only helper behavior on the same households once the threshold is crossed.
  3. [ ] Add dashboard-template regression tests or compile-time contract tests for the shared snippets so `context_v1` and `prepare_groups_v1` continue to render when shard pointers are absent, present, or partially unavailable.
  4. [ ] Re-run the live-load workflow using `utils/load_test_scenario_to_live_ha.py` with dense scenarios so manual dashboard responsiveness can be evaluated alongside recorder-size wins.
  5. [x] Update `tests/SCENARIOS.md`, `tests/AGENT_TESTING_USAGE_GUIDE.md`, and `docs/DASHBOARD_TEMPLATE_GUIDE.md` with the new helper contract, expected dashboard behavior, the removal of `chores_by_label`, and debugging guidance.
  6. [x] Record a go/no-go threshold for adoption using an explicitly named acceptance scenario that is above 100 chores per assignee in the dense test family without materially degrading dashboard responsiveness, with dense 120 per assignee as the default planning target unless implementation evidence requires a revised signoff number.
  7. [ ] Add a mixed-load stress scenario or validation slice that combines dense chores with realistic labels and auxiliary payloads so the test target is not limited to chore-only density.
  8. [x] Treat “supports more than 100 chores” as a required success criterion for the initiative, not an aspirational target, and record the exact acceptance threshold and scenario shape in the validation notes.
  9. [ ] Obtain manual confirmation in the development Home Assistant environment that the agreed acceptance-threshold setup using the new helper sensors does not break `user-gamification-premier-v1` or `user-chores-standard-v1` dashboard templates.
  10. [ ] Explicitly exclude `user-chores-essential-v1` from the extended-scale acceptance target and document that its practical chore limit remains an acknowledged template-specific constraint.
  11. [x] Add targeted lifecycle validation for users near the threshold so repeated small edits prove shard mode does not flap, orphan helpers are cleaned up correctly, and runtime sync leaves entity registry state stable.
  12. [x] Add startup/reload validation proving users already in shard mode are reconstructed correctly after integration restart or reload and users returned to inline mode do not retain stale shard entities.
  13. [x] Add cross-user mutation validation proving one chore edit can move one user into shard mode while moving another out without leaving stale helper state or broken dashboard pointers.
  14. [x] Add entity-registry-focused validation proving shard helper unique IDs remain stable through ordinary edits, helper count changes only when mode changes require it, and orphan shard entities are removed when users leave shard mode.
  15. [x] Add diagnostics validation covering the minimal shard metadata surface so support tooling can explain current mode, expected shard count, and resolved shard helper entity IDs for affected users.
- **Phase 4 progress update (2026-05-06)**
  - Added `tests/scenarios/scenario_density_starblum_120.yaml` and updated `utils/generate_dense_test_scenarios.py` so the dense scenario family now extends beyond 100 chores per assignee.
  - Added focused shard validation in `tests/test_dashboard_helper_sharding.py` for 120-density acceptance, reload reconstruction, orphan cleanup on inline fallback, threshold-edge cross-user reconciliation, registry stability, and minimal shard diagnostics.
  - Updated the focused shard expectations to the translated `UI Dashboard Chore List {shard_index}` naming contract and added explicit coverage that the shared helper attributes publish registered `dashboard_helpers.chore_helper_eids` values.
  - Updated `tests/test_dashboard_helper_density_stress.py` to merge shard-backed chores from `dashboard_helpers.chore_helper_eids` so claim-path stress checks remain valid once the main helper no longer carries inline chores.
  - Updated `tests/SCENARIOS.md` and `tests/AGENT_TESTING_USAGE_GUIDE.md` to document the 120-density acceptance band and shard-aware validation focus.
  - Tightened the cross-user threshold-edge test into a deterministic one-edit move-out/move-in case by using a real oversized swing chore transfer between users near opposite hysteresis boundaries.
  - Ran the full opted-in dense stress suite with the default pytest stress exclusion overridden and confirmed all 16 stress cases pass across 40-120 chores per assignee.
  - Resolved the local dev-runtime startup regression by fixing the missing top-level `core/custom_components/choreops` link and making helper payload assembly tolerate pre-attach shard planning before `entity.hass` is populated.
  - Re-ran the full opted-in dense stress suite after the startup fix and confirmed it still passes at `16 passed` across 40-120 chores per assignee.
  - Latest focused shard reruns still fail in two lifecycle cases: reload reconstruction and small-edit shard retention can leave the main helper publishing an empty `dashboard_helpers.chore_helper_eids` list even while the expected shard helper entities are present in the registry and state machine.
- **Key issues**
  - The current stress suite measures attribute size, not dashboard render latency; manual validation will still matter.
  - Backward compatibility needs explicit tests because many dashboards may still assume one helper contains all chore rows inline.
  - If the shard-aware template logic becomes too complex relative to the size gain, the simpler “trim and split by concern” path may remain the better default.
  - Passing at exactly 100 chores is not enough for this initiative if the user requirement is “more than 100”; the threshold and scenario must be written precisely enough to avoid ambiguity during sign-off.
  - Because the contract changes from possible inline chores to shard-only chores above threshold, validation must prove both states render correctly and that dashboards do not rely on mixed transport.
  - Threshold-edge validation is required, not optional. If users can teeter around the guard, platinum-level entity handling depends on hysteresis and deterministic cleanup behaving correctly under edit churn.
  - Platinum-level signoff here depends on lifecycle validation as much as payload-size validation. Restart, reload, registry cleanup, and cross-user mutation behavior are part of the acceptance bar, not secondary follow-up work.

## Testing & validation

- Planned validation commands:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `mypy tests/`
  - `python utils/sync_dashboard_assets.py`
  - `python utils/sync_dashboard_assets.py --check`
  - `python -m pytest tests/test_dashboard_helper_density_stress.py -o addopts='' -m stress`
  - `python -m pytest tests/ -v --tb=line`
- Tests executed:
  - `./utils/quick_lint.sh --fix` ✅
  - `python -m pytest tests/test_dashboard_template_contract.py tests/test_dashboard_template_render_smoke.py tests/test_sync_dashboard_assets.py -v --tb=line` ✅ (`29 passed`)
  - `python -m pytest tests/test_dashboard_helper_sharding.py -v --tb=line` ✅ (`2 passed`)
  - `./utils/quick_lint.sh --fix` ✅ (Phase 2 backend implementation rerun)
  - `python -m pytest tests/test_dashboard_helper_sharding.py -v --tb=line` ✅ (`7 passed`)
  - `CHOREOPS_RUN_STRESS=1 python -m pytest -o addopts='' -m stress tests/test_dashboard_helper_density_stress.py -v --tb=line` ✅ (`16 passed`)
  - `./utils/quick_lint.sh --fix` ✅ (Phase 4 targeted validation rerun; includes mypy and boundary checks)
  - `python -m pytest tests/test_dashboard_helper_sharding.py -q` ✅ (`7 passed`) after the pre-attach `hass` fallback fix
  - `CHOREOPS_RUN_STRESS=1 python -m pytest -o addopts='' -m stress tests/test_dashboard_helper_density_stress.py -v --tb=line` ✅ (`16 passed`) after the startup fix
  - `python -m pytest tests/test_dashboard_helper_sharding.py -q` ❌ (`6 passed, 2 failed`) after the latest lifecycle and naming changes; failures are reload reconstruction and small-edit shard retention due to empty `dashboard_helpers.chore_helper_eids` publication on the main helper
- Outstanding tests: Manual live-load validation, mixed-load acceptance validation, template-side shard-pointer absence/partial-availability regression coverage, and a fix for the current reload/small-edit shard-pointer publication regression remain pending.

## Phase 4 validation notes

- **Acceptance threshold**: Dense 120 chores per assignee is the current explicit Phase 4 acceptance-band target for “supports more than 100 chores”.
- **Automated evidence added**:
  - Main helper stays below the 16 KB recorder ceiling in shard mode for the 120-density acceptance scenario.
  - Users already in shard mode reconstruct correctly after reload with stable shard helper entity IDs.
  - Ordinary edits do not flap shard mode, and shrinking back to inline removes orphan shard helpers deterministically.
  - Main-helper shard diagnostics and shard-helper minimal metadata remain internally consistent.
  - A single oversized chore edit can now be validated moving one user out of shard mode while pushing another into shard mode in the same mutation.
  - The full opt-in dense stress suite passes across both size checks and representative claim-path behavior from 40 through 120 chores per assignee.
- **Still required for signoff**:
  - Manual dashboard responsiveness checks in a live Home Assistant environment.
  - Authenticated live-load execution of the dense acceptance scenario in the dev Home Assistant instance.
  - A fix for the remaining reload and ordinary-edit shard-pointer publication regression so the main helper consistently republishes resolved `dashboard_helpers.chore_helper_eids` after shard helpers are registered.

## Notes & follow-up

- **Recommended first prototype**: threshold-triggered chore spillover with multi-helper support baked into the contract. Keep the current main helper contract and payload shape as intact as possible below the guard, expose `dashboard_helpers.chore_helper_eids` as an always-present list, enforce a conservative size guard around 14 KB of serialized attributes, and when the chore payload would push the helper past that guard, switch to ordered dedicated chore helpers while the main helper retains stable plumbing and does not carry a parallel inline chore slice.
- **Candidate strategy comparison**:
  - **Option A – Overflow spillover from the current helper**:
    - Main helper remains the canonical dashboard entry point and retains `core_sensors`, `dashboard_helpers`, `ui_control`, identity fields, and any small inline surfaces.
    - When the payload estimate exceeds the guard, chore rows are moved into dedicated extra helper entities and the main helper stops carrying inline `chores` for that state.
    - Best match for backward compatibility because the main helper stays conceptually the same.
    - Primary cost is cutoff logic: the backend must choose a deterministic split point that leaves enough headroom for fixed helper metadata and future small payload growth.
    - If designed as an ordered helper list rather than a single `extra_helper`, it scales cleanly from one overflow helper to two or more without changing the template contract.
  - **Option B – Sequential helper paging (`_2`, `_3`, ...)**:
    - Treat dashboard payload as a paged sequence of helper entities, with the first helper carrying stable identity and plumbing plus as much content as fits.
    - Easier to reason about mechanically because the splitter just fills helper pages in order.
    - More reusable across other payload families because it is not chore-specific.
    - Higher support cost because numbered helper semantics are less self-describing and direct-helper consumers may find debugging harder.
  - **Option C – Always-sharded chore helpers**:
    - The main helper always points to chore helper entities even for small households.
    - Simplest template contract because there is one way to read chores regardless of scale.
    - Largest migration step because even small households stop getting a fully self-contained chore list inline.
- **Current draft recommendation**:
  - Try **Option A** first, but implement it as an ordered-list shard contract rather than a single-extra-helper special case.
  - That preserves today’s mental model, limits dashboard churn, and still gives an immediate path from roughly one chore shard to two or more when households move from ~80 chores toward ~160.
  - Design the pointer field and merge logic so **Option B** remains available later if you want a more generic paging model for rewards, badges, approvals, or other helper-heavy sections.
- **Recommended initial non-goals**:
  - Do not introduce card-specific helper entities.
  - Do not make shard discovery depend on raw storage data or hidden helper registries.
  - Do not move every payload family at once unless early measurements show chore sharding alone is insufficient.
  - Do not extend `user-chores-essential-v1` beyond its already-known practical inline template ceiling as part of this initiative.
- **Closed design choices**:
  - **Helper naming pattern**: use deterministic typed chore-shard helpers with stable backend unique IDs that include shard index, while dashboards continue to consume only `dashboard_helpers.chore_helper_eids`; human-facing names should follow the equivalent of `Chore List 1`, `Chore List 2`, and so on.
  - **Byte threshold and headroom policy**: use final exact serialized helper size as the controlling measurement, enter shard mode at or above 14 KB, and exit shard mode only at or below 12 KB to provide hysteresis below the 16 KB recorder ceiling.
  - **Minimal shard diagnostics**: keep shard-helper diagnostics to `purpose`, `shard_index`, `shard_count`, and `helper_contract_version`; keep current mode, resolved shard entity IDs, last accepted serialized size, and last reconciliation outcome on the main helper runtime diagnostic surface.
  - **Named future payload families**: document chores as the implemented typed-shard family and rewards as the explicit next-family example for the reusable pattern, without widening v1 implementation scope beyond chores.
  - **`ui_manager` runtime plan shape**: store per-user mode, ordered shard membership, expected shard count, last accepted serialized size, and last reconciliation outcome.
- **Effort estimate**:
  - Chore-only shard prototype through shared snippets: medium.
  - Chore shards plus concern-based helper split: medium-high.
  - Full backward-compatible dual-contract support for legacy direct-helper dashboards: medium-high.
- **Recommendation threshold**:
  - Pursue the hybrid design only if the final prototype supports more than 100 chores under the agreed validation scenario without making the shared snippets significantly harder to maintain.
  - Prefer a contract that naturally supports the next expansion step to roughly 160 chores via two chore helpers, not one that would require revisiting helper semantics after the first overflow case ships.
  - Back down if template complexity, partial-failure handling, or manual render responsiveness becomes worse than the simpler helper-trimming path.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
