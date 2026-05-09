# Initiative snapshot

- **Name / Code**: Dynamic chore entity lifecycle without integration reload / `CHORE_DYNAMIC_ENTITY_LIFECYCLE`
- **Target release / milestone**: TBD after scope review; candidate for next post-1.0.x backend UX release
- **Owner / driver(s)**: TBD
- **Status**: Completed and ready for archive under `docs/completed`

## Summary & immediate steps

> **Critical implementation note:** Do not preserve or introduce fallback paths, compatibility wrappers, or temporary dual-behavior shims unless they are explicitly justified, narrowly scoped, and recorded in the active phase notes with a concrete reason they are still required. For this initiative, wrapper-heavy implementation is treated as a potential sign that the runtime sync contract was not fully solved at the root.

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Runtime contract and scope lock | Freeze invariants, mutation classes, and scope boundaries before code changes | 100% | Reload boundary, mutation classes, non-goals, and rename policy are now locked |
| Phase 2 – Dynamic entity orchestration | Add chore-scoped runtime add/remove/sync support for graph-mutating entity families | 100% | Runtime sync contract, production-safe sensor/button creation, and shared-sensor cleanup are in place |
| Phase 3 – Flow and service adoption | Move chore service and options-flow CRUD to targeted sync without touching settings reload paths | 100% | Chore services and chore options-flow CRUD now converge on the shared runtime sync contract |
| Phase 3B – Sparse edit preservation remediation | Stop and resolve partial-section options-flow regressions before any additional rollout work | 100% | Sparse edit regressions added, root cause fixed at the edit schema boundary, and validation is green |
| Phase 4 – Validation and rollout | Prove dashboard continuity, registry correctness, and backward-safe behavior | 100% | Targeted rollout validation is complete, docs are updated, and the remaining reload boundary is explicitly limited to sanctioned non-chore paths |

1. **Key objective** – Eliminate full integration reloads for chore create, update, and delete so the active dashboard page keeps working while chore-backed entities and helper surfaces update live.
2. **Summary of recent work** –
   - Confirmed chore CRUD in `ChoreManager` already follows modify → persist → `async_update_listeners()` → emit signal.
   - Confirmed reload is still explicitly used for production entity graph refresh in `coordinator.py`, service handlers, and options flow.
   - Confirmed some surfaces already behave dynamically: calendar cache invalidation on chore signals, selector options derived from coordinator state, and manager-driven orphan cleanup.
   - Locked Phase 1 decisions: the reload boundary in `coordinator.py` is a temporary production fallback, mutation classes are fixed for v1, button runtime creation is mandatory, and no compatibility wrappers should be used unless explicitly justified.
  - Implemented Phase 2 orchestration: typed chore entity sync context, coordinator runtime sync entry point, production-safe chore sensor/button registration, and correct shared/shared-first orphan cleanup.
  - Implemented Phase 3 caller adoption: chore services and chore options-flow CRUD now use the shared runtime sync contract, while helper-only options-flow substeps no longer rely on deferred reload.
3. **Next steps (short term)** –
  - Prepare PR/release metadata using the summary below: chore create, edit, and delete now update runtime sensors, buttons, and dashboard helper payloads without a full integration reload; sanctioned system-settings edits still reload.
  - Keep the Phase 3B edit-boundary safeguard scoped to chore edit forms unless a separate audit proves other domains need the same pattern.
  - Preserve the current shared-service/data-builder contracts; do not broaden the fix beyond edit-form schema behavior without a new defect signal.
4. **Risks / blockers** –
  - Button entities are setup-time only today, so sensor-only dynamic creation is insufficient.
  - Assignment changes and completion-criteria transitions change the entity graph, not just entity state, so update paths need add and remove orchestration.
  - Entity names and helper attributes cache constructor-time values in several platforms, which can leave rename flows partially stale without targeted refresh logic or explicit replacement.
  - Dashboard helper payloads derive from both coordinator state and registry lookups, so entity creation ordering matters.
  - Options flow currently assumes entity CRUD requires deferred reload after the user returns to the main menu, and that assumption is shared with non-chore domains.
  - Tests and test utilities already encode reload-era assumptions, so correct runtime behavior may fail old tests until the assertions are updated deliberately.
  - `tests/test_options_flow_per_kid_helper.py::TestSchemaEdgeCases::test_esv06_edit_partial_section_payload_preserves_schedule_fields` fails in isolation and points to a likely backend gap where omitted optional edit fields are reset to defaults instead of preserving stored values.
  - Direct transform and builder calls preserve the same fields correctly, which suggests the defect sits in the options-flow form/schema boundary rather than in manager merge logic alone.
5. **References** –
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
  - [docs/completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_SUP_TRAPS_AND_OPPORTUNITIES.md](./CHORE_DYNAMIC_ENTITY_LIFECYCLE_SUP_TRAPS_AND_OPPORTUNITIES.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep system-settings reload behavior intact; this initiative only targets chore domain item CRUD.
     - Preserve signal-first manager communication; do not reintroduce cross-manager orchestration or direct platform writes from services.
     - Prefer targeted entity add/remove plus coordinator listener updates over full entry reload.
    - Treat runtime entity graph mutation as a separate problem from state refresh; `async_update_listeners()` alone is not sufficient.
    - Treat options flow as a second adopter of the runtime sync contract, not as the place where the contract is invented.
      - Treat ESV06 as a real defect signal, not as a disposable test artifact. No further implementation should continue until sparse-edit preservation is characterized and covered by explicit regression tests.
     - No `.storage/choreops/choreops_data` schema bump is expected unless execution later requires persisted entity-sync metadata.
  - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

> **Phase update style:** Keep phase updates short and operational. For each update, briefly state what changed, any gap or deviation from plan, and the next direct action. Favor implementation progress and decision clarity over process-heavy narration.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Runtime contract and scope lock

- **Goal**: Define the runtime lifecycle contract for chore CRUD so implementation work can remove reloads without broadening scope into unrelated config-entry behavior.
- **Steps / detailed work items**
  1. [x] Document the current reload boundary in `custom_components/choreops/coordinator.py` around line 377 and classify it as a temporary production fallback to be replaced by chore-specific runtime sync, not by `async_request_refresh()` and not by a broad settings reload substitute.
  2. [x] Audit chore CRUD callers in `custom_components/choreops/services.py` around lines 1100-1325 and `custom_components/choreops/options_flow.py` around lines 1020-2575 plus 6110-6175 to distinguish pure state updates from entity-graph mutations.
  3. [x] Freeze the runtime mutation classes to support in v1: chore created, chore deleted, assignment expansion, assignment shrinkage, criteria transition, and rename-sensitive update.
  4. [x] Enumerate chore-backed entity families and owners in the plan or follow-up design note: `AssigneeChoreStatusSensor`, `SystemChoreSharedStateSensor`, chore claim/approve/disapprove buttons, dashboard helper payloads, selectors, and calendar views. Mark each family as one of `dynamic create required`, `dynamic remove required`, or `listener-only verification`.
  5. [x] Lock the non-goals for v1: do not change system settings reload behavior in `__init__.py` / `config_flow.py`, do not redesign dashboard YAML, do not generalize into a multi-domain sync framework, and do not introduce a schema version bump unless a persisted contract genuinely changes.
  6. [x] Decide whether runtime entity synchronization lives in a new helper/module or remains platform-local via callback registries in `sensor.py` and `button.py`.
  7. [x] Record explicit rename policy per entity family: update in place, replace entity, or defer with documented limitation. This decision must be made before coding because cached constructor names exist in `button.py` and `sensor.py`.
- **Phase 1 completion update (2026-04-12)**
  - Accomplished: classified the reload boundary in `coordinator.py` as the production fallback to remove; confirmed service create and assignment-changing update paths are current graph-mutation callers; confirmed options flow still uses a shared deferred reload boundary for chore CRUD.
  - Accomplished: locked v1 mutation classes to `created`, `deleted`, `assignments_added`, `assignments_removed`, `shared_state_changed`, and `rename_sensitive_update`.
  - Accomplished: froze entity-family handling for v1:
    - `AssigneeChoreStatusSensor`: dynamic create required, dynamic remove required, rename-sensitive.
    - `SystemChoreSharedStateSensor`: dynamic create required, dynamic remove required.
    - Chore claim/approve/disapprove buttons: dynamic create required, dynamic remove required, rename-sensitive.
    - Dashboard helper payloads, selectors, calendars: listener-driven verification required; do not solve with wrapper refresh paths.
  - Decision: runtime sync will use one chore-scoped entry point coordinated from `coordinator.py`, with platform-local add/remove registration in `sensor.py` and `button.py` rather than independent caller-specific logic or a broad compatibility layer.
  - Decision: rename policy is strict. Update in place where attributes derive from coordinator state at read time; otherwise replace affected entities directly. Do not keep reload or compatibility wrappers just to hide constructor-cached naming gaps.
  - Validation: `./utils/quick_lint.sh --fix` passed locally, including MyPy and boundary checks. Full test validation for this workstream was already completed successfully before this phase report and should not be rerun unless explicitly requested.
  - Gap/deviation: none for Phase 1. The phase remained documentation-and-contract work only.
  - Next action: begin Phase 2 by introducing the chore-scoped runtime sync entry point and production-safe button/sensor registration.
- **Key issues**
  - `async_update_listeners()` already refreshes existing coordinator entities, so the missing capability is graph mutation, not data propagation.
  - Some surfaces already update live by signal invalidation, which means the plan should avoid re-solving problems that are already handled by calendar/select/helper read paths.
  - Test-mode sensor creation is currently stronger than production behavior. Any design that leaves that split intact is incomplete.
- **Phase exit checkpoint**
  - Fallback path / wrapper inventory: `none` left or added in Phase 1. The phase locked a no-wrapper bias for implementation and rejected reload-preserving compatibility shims as a default strategy.

### Phase 2 – Dynamic entity orchestration

- **Goal**: Add targeted runtime add/remove behavior for chore-backed entities so create, assignment changes, and completion-criteria changes no longer require full integration reload.
- **Steps / detailed work items**
  1. [x] Extend the callback-registration pattern in `custom_components/choreops/sensor.py` around lines 553-710 from test-only chore sensor creation into a production-safe runtime path that can add all required chore sensors, including `SystemChoreSharedStateSensor` when completion criteria are shared.
  2. [x] Add an equivalent runtime callback registration path in `custom_components/choreops/button.py` near the initial setup block around lines 44-240 so chore claim, approve, and disapprove buttons can be created for new assignee/chore pairs without reload.
  3. [x] Introduce a focused entity-sync entry point, likely coordinated from `custom_components/choreops/coordinator.py`, that accepts a chore ID plus mutation context and performs add/remove/update work rather than calling `hass.config_entries.async_reload(...)`.
  4. [x] Represent graph mutations explicitly in the sync contract. At minimum, the implementation must distinguish `created`, `deleted`, `assignments_added`, `assignments_removed`, and `shared_state_changed` so add and remove work is deterministic.
  5. [x] Update `custom_components/choreops/managers/chore_manager.py` around lines 3160-3365 so create/update/delete paths continue to own storage mutation and cleanup, but expose enough mutation context for the new entity-sync layer to handle newly added assignee/chore combinations and shared-state transitions.
  6. [x] Keep targeted cleanup on delete and assignment removal by preserving `remove_entities_by_item_id()`, `remove_orphaned_assignee_chore_entities()`, and `remove_orphaned_shared_chore_sensors()` in `custom_components/choreops/helpers/entity_helpers.py` around lines 705-790 as the removal half of the live-sync contract.
  7. [x] Add ordering guarantees for dashboard-facing consistency: runtime entity creation/removal must complete before helper surfaces are relied on for entity IDs. Treat `sensor.py` dashboard helper payloads around lines 4546-5000 as a contract consumer, not as an afterthought.
  8. [x] Resolve rename-sensitive entities either by computing display-facing values from coordinator data at read time or by explicit replacement/update logic so chore renames do not require reload for a consistent UI surface.
- **Phase 2 completion update (2026-04-12)**
  - Accomplished: added `ChoreEntitySyncContext`, a chore-scoped coordinator runtime sync entry point, and a small result contract for add/remove orchestration.
  - Accomplished: upgraded sensor runtime creation from test-only behavior to a production-safe path that creates assignee chore sensors and shared/shared-first global state sensors only when missing.
  - Accomplished: added production-safe chore button registration and runtime creation for claim, approve, and disapprove buttons.
  - Accomplished: fixed shared chore cleanup to track the real shared-state sensor unique-id suffix and to preserve both `SHARED` and `SHARED_FIRST` sensors correctly.
  - Accomplished: added targeted runtime sync regression tests covering create, assignment churn, rename-sensitive replacement, and shared-state transitions.
  - Gap/deviation: service handlers and options flow still call the old reload-driven service/helper path. That is the explicit Phase 3 adoption work, not an unfinished Phase 2 implementation detail.
  - Next action: replace service reload usage with the runtime sync contract, then move chore-specific options-flow CRUD to that same contract.
- **Key issues**
  - Dynamic creation needs to cover both create and update paths because assignment changes and independent/shared transitions create new entities without creating a new chore record.
  - The orchestration layer must not write storage itself; it should be a platform/entity sync concern triggered after manager-owned persistence.
  - The dashboard helper currently walks `coordinator.chores_data` and registry lookups independently, so race ordering between entity registration and helper rebuild can produce temporary `eid=None` payloads if sequencing is wrong.
  - Buttons cache chore and assignee names at construction. A create/delete-only implementation is not enough; rename safety must be resolved or explicitly deferred.
- **Phase exit checkpoint**
  - Fallback path / wrapper inventory:
    - Existing reload-driven caller path remains in `async_sync_entities_after_service_create()` and its service/options-flow callers. Justification: caller adoption belongs to Phase 3 and was intentionally not mixed into the orchestration phase.
    - No new compatibility wrapper or dual-behavior shim was introduced in Phase 2. The new runtime sync layer is a direct implementation path, not a wrapper around reload.

### Phase 3 – Flow and service adoption

- **Goal**: Replace reload-driven chore CRUD behavior in services and options flow with the targeted runtime sync contract while keeping feature-flag and settings reload paths intact.
- **Steps / detailed work items**
  1. [x] Replace `async_sync_entities_after_service_create()` in `custom_components/choreops/coordinator.py` around lines 377-388 with a chore-focused runtime sync API that can be called from create, update, and delete service handlers without reloading the config entry.
  2. [x] Update `handle_create_chore`, `handle_update_chore`, and `handle_delete_chore` in `custom_components/choreops/services.py` around lines 1100-1400 so production uses the same runtime sync path currently reserved for test-only direct sensor creation.
  3. [x] Ensure service handlers do not create a second orchestration layer. They should delegate write ownership to `ChoreManager` and then request runtime entity sync using persisted mutation context.
  4. [x] Replace deferred reload behavior in `custom_components/choreops/options_flow.py` around lines 1020-2575 and 6110-6175 for chore entity CRUD paths, while preserving `_update_system_settings_and_reload()` for `config_entry.options` changes that still require integration reload.
  5. [x] Introduce chore-specific handling in options flow instead of weakening the global `_reload_needed` behavior for all entity types. The chore path must stop relying on reload without destabilizing badges, rewards, users, or other domains that still use the deferred reload pattern.
  6. [x] Review temporary helper-state paths in `options_flow.py` such as `_chore_being_edited`, `_chore_template_date_raw`, `_chore_template_applicable_days`, and `_chore_template_daily_multi_times` so live updates do not leave stale flow state or rely on a post-return reload to normalize state.
  7. [x] Verify dashboard helper sensors, selectors, and calendars continue to respond from coordinator state and signal invalidation alone, avoiding new bespoke refresh calls where existing listener behavior is already sufficient.
- **Phase 3 completion update (2026-04-12)**
  - Accomplished: chore service create, update, and delete now delegate to the shared runtime sync contract after manager-owned persistence instead of using the reload-era service fallback.
  - Accomplished: chore options-flow add, edit, and delete now use the same runtime sync contract, while chore helper substeps for per-assignee dates, per-assignee details, and daily-multi times no longer mark deferred reload.
  - Accomplished: added focused tests proving service and options-flow chore callers use runtime sync directly and no longer rely on the old chore reload path.
  - Gap/deviation: `async_sync_entities_after_service_create()` still exists for non-chore service callers and was intentionally not generalized away in this phase.
  - Next action: expand Phase 4 validation around helper/dashboard continuity and remaining reload-era test/documentation assumptions.
- **Key issues**
  - Options flow currently batches entity CRUD and performs reload at menu return, so removing reload may expose stale assumptions about coordinator references or flow summaries.
  - Services and options flow should converge on the same runtime sync entry point to avoid one path becoming the new source of regressions.
  - Service update currently excludes completion-criteria edits from the public schema, so shared-state transition handling is an options-flow adoption concern today, not a service-call concern.
  - Options-flow delete already bypasses deferred reload, while per-assignee date/detail helpers and daily-multi helper steps currently mark reload even though they appear to be state-only updates rather than graph mutations.
  - Test helpers and comments currently teach developers to reacquire `config_entry.runtime_data` after options-flow CRUD because reload creates a new coordinator. Those expectations must be updated in the same workstream.
- **Phase exit checkpoint**
  - Fallback path / wrapper inventory:
    - Existing `async_sync_entities_after_service_create()` remains for non-chore service callers. Justification: this phase intentionally converged chore callers only and did not generalize non-chore domains prematurely.
    - No new compatibility wrapper or dual-behavior shim was introduced in Phase 3. Services and options flow now call the same chore runtime sync path directly.

### Phase 4 – Validation and rollout

- **Goal**: Validate that chore CRUD becomes live and dashboard-safe without regressions in entity registry cleanup, button authorization surfaces, or helper payloads.
- **Status**: Complete
- **Completed work**
  - Added explicit service-path assertions that chore create, update, and delete do not call config-entry reload and still materialize the expected live sensor, button, and dashboard-helper surfaces.
  - Added options-flow regression coverage proving chore add/edit/delete use runtime sync directly, while sanctioned system-settings edits still reload the integration.
  - Added helper-step regression coverage proving the multi-assignee INDEPENDENT helper step and the DAILY_MULTI helper step no longer mark deferred reload.
  - Updated test guidance in `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` so chore CRUD is no longer documented as reload-backed by default.
  - Reviewed `tests/helpers/setup.py` reload-era comments and left the badge-specific note unchanged because it is not part of the chore runtime-sync surface.
  - Discovered a critical follow-on defect signal in sparse edit preservation (ESV06), reopening rollout until the new Phase 3B work is complete.
- **Steps / detailed work items**
  1. [x] Add regression tests covering service-driven chore create/update/delete in `tests/test_chore_crud_services.py`, using scenario fixtures from `tests/scenarios/` and the patterns in `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`, with explicit assertions that no config-entry reload is required for chore CRUD.
  2. [x] Add entity-surface tests proving new chore status sensors and workflow buttons appear live after create and after assignment expansion, and disappear after delete or assignment removal.
  3. [x] Add coverage for completion-criteria transitions so independent-to-shared and shared-to-independent chore edits produce the correct shared-state sensor and assignee-chore entity graph.
  4. [x] Add dashboard/helper regression tests confirming helper payloads contain valid entity IDs after live chore CRUD and that label-grouped helper views remain consistent.
  5. [x] Add options-flow regression tests covering chore add/edit/delete without deferred reload assumptions, especially multi-assignee INDEPENDENT helper flows and DAILY_MULTI helper steps.
  6. [x] Update test helpers and test docs that currently assume options-flow entity CRUD forces reload and stale coordinator replacement, including `tests/helpers/setup.py` and `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` where relevant.
  7. [x] Run focused validation for the remaining sanctioned reload paths so system settings changes still reload correctly and this initiative does not blur the architecture boundary described in `docs/ARCHITECTURE.md`.
  8. [x] Update release notes and any relevant docs to state that chore CRUD now updates runtime entities dynamically while settings changes still reload the integration.
- **Key issues**
  - Tests must verify both entity registry state and user-visible behavior; proving “no reload” only by absence of exceptions is not enough.
  - Dashboard refresh symptoms can be indirect, so helper entity and selector state assertions are the safest backend proxy if frontend UI automation is out of scope.
  - Existing tests already contain comments that rationalize missing runtime entity creation; those comments must be removed or rewritten so the suite does not normalize old limitations.
  - Rollout cannot be declared complete while sparse section submissions in options flow may still reset omitted stored values to schema defaults.
- **Phase 4 completion update (2026-04-12)**
  - Accomplished: completed targeted rollout validation across chore runtime sync, chore CRUD services, chore options-flow CRUD, per-assignee helper flows, DAILY_MULTI helper flows, and the Phase 3B sparse-edit regression surface.
  - Accomplished: confirmed the sanctioned reload boundary remains intact for system settings, with explicit regression coverage proving those edits still call config-entry reload.
  - Accomplished: updated developer-facing test guidance and user-facing README language so the new runtime behavior is documented consistently.
  - Validation: `./utils/quick_lint.sh --fix` passed on 2026-04-12. `python -m pytest tests/test_chore_runtime_entity_sync.py tests/test_chore_crud_services.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py tests/test_options_flow_daily_multi.py -v --tb=line` passed on 2026-04-12 (`100 passed`).
  - Release note summary: chore create, edit, and delete now update runtime sensors, buttons, and dashboard helper payloads without a full integration reload. Sanctioned system-settings edits still reload the integration.
  - Gap/deviation: none within the approved rollout scope.
  - Next action: owner review and PR/release metadata alignment for issue 107.
- **Phase exit checkpoint**
  - Record any fallback path, compatibility wrapper, or temporary shim still present after validation. Default expectation is `none`. If any remain, justify each one briefly, explain why the release can still be considered correct, and state the exact follow-up needed before completion can be claimed.
  - Fallback path / wrapper inventory:
    - No new fallback path, compatibility wrapper, or temporary shim was added in Phase 4.
    - Existing `async_sync_entities_after_service_create()` remains scoped to non-chore service callers only, unchanged from Phase 3, and is not part of the chore CRUD runtime-sync path.

## Testing & validation

- Planned validation commands:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `mypy tests/`
  - `python -m pytest tests/ -v --tb=line`
  - Targeted suites during implementation:
    - `python -m pytest tests/test_workflow_chores.py -v`
    - `python -m pytest tests/test_config_flow.py -v`
    - `python -m pytest tests/test_services.py -v`
- Tests executed:
  - `./utils/quick_lint.sh --fix` passed on 2026-04-12.
  - Full test validation for this workstream was reported complete at 100% success and should not be rerun unless explicitly requested.
  - `python -m pytest tests/test_chore_runtime_entity_sync.py tests/test_chore_crud_services.py -v --tb=line` passed on 2026-04-12 (`22 passed`).
  - `python -m pytest tests/test_chore_runtime_entity_sync.py tests/test_chore_crud_services.py tests/test_options_flow_entity_crud.py -v --tb=line` passed on 2026-04-12 (`58 passed`).
  - `python -m pytest tests/test_chore_crud_services.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py::TestPerAssigneeHelperAdd::test_pkh02_helper_completion_does_not_mark_deferred_reload tests/test_options_flow_daily_multi.py::TestDailyMultiOptionsFlow::test_of_03_helper_completion_does_not_mark_deferred_reload -v --tb=line` passed on 2026-04-12 (`62 passed`).
  - Focused defect validation on 2026-04-12 confirmed `tests/test_options_flow_per_kid_helper.py::TestSchemaEdgeCases::test_esv06_edit_partial_section_payload_preserves_schedule_fields` fails in isolation, so this is a real backend defect signal rather than a suite-order artifact.
  - Direct transform/builder isolation on 2026-04-12 preserved the ESV06 values correctly, narrowing the suspected defect surface to the options-flow edit boundary and schema default handling.
- Implementation validation policy:
  - Use targeted chore-focused suites during implementation loops to keep iteration efficient.
  - Do not rerun the full test suite for this workstream unless explicitly requested or a later blocker makes it necessary.
- Outstanding tests: Phase 3B must add explicit sparse-edit preservation coverage before rollout can resume. Do not treat ESV06 as independent or optional follow-up work.
- Outstanding tests: none for the approved targeted rollout scope. Full-suite rerun remains optional and out of the active implementation loop unless explicitly requested.

### Phase 3B – Sparse edit preservation remediation

- **Goal**: Prove and fix partial-section edit behavior so omitted optional chore fields preserve stored values instead of being overwritten by schema defaults during options-flow edit submissions.
- **Why this phase exists**:
  - `test_esv06_edit_partial_section_payload_preserves_schedule_fields` in `tests/test_options_flow_per_kid_helper.py` around lines 1374-1449 fails in isolation.
  - The failure returns `0d 1h 0m`, the chore due-window default, instead of the stored `3h`, indicating default injection rather than correct preserve-existing semantics.
  - Direct calls through `flow_helpers.transform_chore_cfof_to_data()` and `data_builders.build_chore()` preserve the same values correctly, which means rollout should pause and the edit boundary should be remediated at the root.
- **Steps / detailed work items**
  1. [x] Add targeted reproduction tests in `tests/test_options_flow_per_kid_helper.py` around the ESV06 block to cover representative omission patterns by field family: schedule text offset, advanced text offset, consolidated multi-select notifications, and one explicit-overwrite control.
  2. [x] Add complementary options-flow tests in `tests/test_options_flow_entity_crud.py` for sparse edit submissions after stored non-default values exist, using a quality sampling approach across distinct field types rather than brute-force testing every optional field.
  3. [x] Add at least one negative-control test proving explicit user changes still overwrite stored values, and one preserve-on-omit control proving omitted values stay intact, so the remediation does not collapse omission and intentional update into the same behavior.
  4. [x] Audit `custom_components/choreops/helpers/flow_helpers.py` around lines 880-1045 and group optional edit fields by risk pattern: optional with defaulted text value, optional multi-select/synthesized selector, optional list/collection, optional field with explicit clear semantics, and required field that should be out of scope for preserve-on-omit concerns.
  5. [x] Trace the edit path in `custom_components/choreops/options_flow.py` around lines 1368-1404 to document whether Home Assistant returns schema-defaulted optional values in the submitted payload or whether ChoreOps is merging defaults too early.
  6. [x] Remediate the root cause in one place only: either stop using backend schema defaults for preserve-on-omit edit fields, or normalize the edit payload before validation/transform so omitted fields remain truly omitted. Do not add per-field compatibility shims.
  7. [x] Re-verify `flow_helpers.validate_chores_inputs()`, `flow_helpers.transform_chore_cfof_to_data()`, and `data_builders.build_chore()` still preserve their current separation of responsibilities after the edit-boundary fix.
  8. [x] Re-run the representative sparse-edit regression set plus the previously completed Phase 4 chore runtime-sync coverage before resuming rollout status updates.
- **Phase 3B completion update (2026-04-12)**
  - Accomplished: expanded sparse-edit regression coverage with representative tests for omitted schedule text fields, omitted collection fields, omitted advanced notification fan-out, explicit overwrite behavior, and explicit clear behavior.
  - Accomplished: confirmed the defect class at the live edit boundary rather than in shared transformation/building logic. Direct calls through `transform_chore_cfof_to_data()` and `build_chore()` remained correct.
  - Accomplished: fixed the root cause by adding an edit-mode schema option that suppresses backend default injection for optional preserve-on-omit fields while continuing to use suggested values for UI display.
  - Accomplished: kept the fix scoped to chore edit forms in `options_flow.py`; add flows, config flow, services, and `data_builders.build_chore()` were not behaviorally changed by this remediation.
  - Validation: `./utils/quick_lint.sh --fix` passed locally, including Ruff, production MyPy, and boundary checks. `python -m pytest tests/test_chore_runtime_entity_sync.py tests/test_chore_crud_services.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py tests/test_options_flow_daily_multi.py -v --tb=line` passed on 2026-04-12 (`100 passed`).
  - Gap/deviation: none within the approved Phase 3B scope.
  - Next action: await approval before resuming Phase 4 rollout validation/documentation completion.
- **Key issues**
  - `build_chore_schema()` in `custom_components/choreops/helpers/flow_helpers.py` around lines 919-1037 currently assigns defaults to multiple optional schedule and advanced fields, which is safe for add flows but may be unsafe for sparse edit submissions.
  - The edit handler in `custom_components/choreops/options_flow.py` around lines 1385-1394 passes sectioned user input through shared validation and transform logic, so a bug at this boundary can affect multiple optional fields, not just due-window offset.
  - Notification consolidation is particularly risky because omission of the selector must preserve stored booleans, while explicit submission must still rewrite them deterministically.
  - This phase must stay test-first. No production-code remediation should start until the new regression set proves the breadth of the defect surface.
  - Coverage should be pattern-complete rather than field-exhaustive. The bar is to sample enough distinct field behaviors to prove the defect class is closed without creating noisy duplicate tests for every single optional field.
  - Shared-usage safety boundary: `data_builders.build_chore()` and service-layer update/create flows remain shared contracts and were intentionally left unchanged. The remediation lives at the edit-form schema boundary only.
- **Phase exit checkpoint**
  - Fallback path / wrapper inventory: default expectation is `none`. The remediation must not add field-specific fallback wrappers to mask edit-boundary defects.

## Notes & follow-up

- **Current architecture readout**:
  - Chore CRUD is already manager-owned and signal-first in `custom_components/choreops/managers/chore_manager.py`.
  - Calendar entities already invalidate on chore mutation signals in `custom_components/choreops/calendar.py` and are a valid model for read-path live updates.
  - Select/helper surfaces mostly derive from coordinator state and are more likely to need listener verification than entity creation work.
  - The main missing runtime capability is setup-time entity families that do not yet have a production add callback, especially buttons.
- **Implementation guardrails**:
  - Service-path runtime sync should be proven before options-flow conversion if scope needs to be staged.
  - A chore update that changes only values is not equivalent to one that changes assignments or criteria. The implementation must model mutation classes explicitly.
  - Dashboard helper payload correctness is part of the acceptance bar. Storage correctness alone is insufficient.
  - Rename correctness must be resolved intentionally because many entities cache constructor-time names and translation placeholders.
- **Recommended implementation bias**:
  - Build a minimal, chore-scoped runtime entity sync contract first.
  - Reuse existing targeted orphan cleanup for removals.
  - Avoid a generic “dynamic everything” abstraction unless chore implementation proves the pattern is stable enough to promote.
  - Use [docs/completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_SUP_TRAPS_AND_OPPORTUNITIES.md](./CHORE_DYNAMIC_ENTITY_LIFECYCLE_SUP_TRAPS_AND_OPPORTUNITIES.md) as the risk register during implementation and review.
- **Open decisions**:
  - Whether the edit-boundary remediation should live entirely inside `build_chore_schema()` / form construction or in a single payload-normalization helper immediately before validation.
  - Whether to create a dedicated entity-sync helper module now or first land a sensor-plus-button callback pattern and extract later.
  - Whether options flow should switch all chore CRUD paths in the same change or follow after service/runtime sync is proven.
  - Whether entity rename semantics require constructor-time attribute cleanup or are acceptable through state/attribute refresh only.
  - Whether helper payloads should temporarily tolerate `eid=None` during in-flight creation or whether the sync contract must guarantee registry readiness before helper rebuild.
- **Effort estimate**:
  - Chore-scoped dynamic sync: medium-high.
  - Generalized multi-platform runtime sync framework: high.

> **Archive note:** This initiative is complete. The canonical archived filename is `CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md` under `docs/completed/`.
