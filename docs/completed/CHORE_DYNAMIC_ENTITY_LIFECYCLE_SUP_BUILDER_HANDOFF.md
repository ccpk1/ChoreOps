# Dynamic chore entity lifecycle - Builder handoff

---

status: COMPLETE
owner: Strategist Agent
created: 2026-04-12
issue: 107
parent_plan: CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md
handoff_from: ChoreOps Strategist
handoff_to: ChoreOps Builder
phase_focus: Phase 4 rollout validation and documentation closeout completed

---

## Handoff button

[HANDOFF_TO_BUILDER_CHORE_DYNAMIC_ENTITY_LIFECYCLE](CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md)

## Handoff objective

This handoff has been completed. The rollout-blocking sparse-edit defect was remediated, Phase 4 validation closed green, and the initiative is ready for owner review.

Critical implementation bias:

- Do not preserve or introduce fallback paths, compatibility wrappers, or temporary dual-behavior shims unless they are explicitly justified, narrowly scoped, and called out in the handback.
- For issue 107, wrappers should be treated as a sign that the runtime sync contract may not have been solved at the root. Prefer finishing the real implementation over masking gaps with compatibility layers.

Required behavior:

1. Keep manager-owned writes intact and perform runtime entity synchronization only after successful persistence.
2. Replace chore-specific reload-driven entity rebuilds with targeted runtime add, remove, and update behavior.
3. Support graph-mutating updates, not just brand-new chore creation.
4. Preserve system-settings and non-chore reload behavior.
5. Prove dashboard helper integrity and registry correctness through tests.
6. Before continuing any new rollout work, expand sparse-edit regression coverage and fix the root cause behind ESV06 so omitted optional chore edit fields preserve stored values.
7. Close Phase 4 with explicit rollout validation, documentation updates, and release-note wording that preserves the sanctioned reload boundary for system settings.

## Implementation stance already locked

These planning decisions are considered settled for issue 107 and should not be re-opened during implementation unless a blocker is discovered:

1. Scope is chore domain item CRUD only.
2. System settings reload behavior stays intact.
3. Runtime graph mutation is the missing capability; `async_update_listeners()` alone is not sufficient.
4. Buttons are in scope for v1 and are not optional follow-up work.
5. Service and options-flow paths must converge on the same runtime sync contract.
6. No `.storage` schema bump is expected.
7. Public service update scope is narrower than options flow today because completion-criteria changes are not exposed by the update service schema.
8. ESV06 is a real defect signal, not a disposable test failure. Treat it as blocking rollout until test-first remediation is complete.

## Recommended defaults for remaining design choices

These are the defaults the builder should use unless implementation uncovers a concrete contradiction:

1. Fix the sparse-edit boundary at the root rather than layering field-specific preservation shims around it.
2. Add tests first to define the exact breadth of the defect surface before production-code remediation begins.
3. Treat rename-sensitive entities as a real acceptance item. Prefer runtime recomputation where practical; use explicit replacement only where constructor-cached values make that necessary.
4. Do not tolerate helper payloads that emit missing entity IDs as a normal steady-state outcome.

## In scope

- Core orchestration and fallback replacement:
  - [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
  - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py)
- Runtime entity families:
  - [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py)
  - [custom_components/choreops/button.py](../../custom_components/choreops/button.py)
  - [custom_components/choreops/helpers/entity_helpers.py](../../custom_components/choreops/helpers/entity_helpers.py)
- Chore callers/adopters:
  - [custom_components/choreops/services.py](../../custom_components/choreops/services.py)
  - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
- Validation and regression coverage:
  - [tests/test_chore_crud_services.py](../../tests/test_chore_crud_services.py)
  - [tests/test_entity_lifecycle_stability.py](../../tests/test_entity_lifecycle_stability.py)
  - [tests/helpers/setup.py](../../tests/helpers/setup.py)
  - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)

## Out of scope

- Generic multi-domain runtime entity sync abstraction.
- Changes to non-chore domains that still rely on deferred reload.
- Dashboard YAML redesign.
- System settings reload redesign.
- Storage migration or schema version work unless a hard blocker proves it is required.

## Completion summary

1. Expanded ESV06 into a representative sparse-edit regression set before production remediation.
2. Audited the edit boundary and confirmed the defect lived in schema default injection, not shared builder/service logic.
3. Remediated the root cause in the chore edit-form schema path only.
4. Re-ran sparse-edit regression coverage and the chore runtime-sync suite successfully.
5. Closed Phase 4 with rollout validation, documentation updates, and explicit release-note wording.

## Builder checklist

### Package A - Runtime sync contract

- [ ] Replace the chore-specific reload fallback in [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py) with a chore-scoped runtime sync entry point.
- [ ] Ensure the sync entry point accepts mutation context instead of a bare refresh request.
- [ ] Keep storage mutation ownership in [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py).

### Package B - Runtime entity families

- [ ] Extend [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py) to support production-safe chore entity creation for create and update mutation paths.
- [ ] Extend [custom_components/choreops/button.py](../../custom_components/choreops/button.py) to support production-safe creation of claim, approve, and disapprove buttons for new assignee/chore pairs.
- [ ] Reuse cleanup helpers in [custom_components/choreops/helpers/entity_helpers.py](../../custom_components/choreops/helpers/entity_helpers.py) for delete and assignment-removal behavior.
- [ ] Resolve rename-sensitive display data intentionally rather than assuming state refresh will fix constructor-cached values.

### Package C - Caller adoption

- [ ] Update chore service handlers in [custom_components/choreops/services.py](../../custom_components/choreops/services.py) to use the shared runtime sync path.
- [ ] Replace chore-specific deferred reload behavior in [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py) while preserving non-chore reload paths.
- [ ] Treat service delete and options-flow delete as verification-first paths because they already avoid the reload helper today; only add runtime sync work there if direct validation shows missing cleanup or stale helper payloads.
- [ ] Avoid introducing a second orchestration layer in callers.

### Package D - Regression coverage

- [ ] Add sparse-edit reproduction tests around ESV06 in [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py).
- [ ] Add options-flow CRUD coverage for omitted optional fields after stored non-default values already exist, using a representative sampling of field patterns rather than one test per field.
- [ ] Add negative-control tests proving explicit edits still overwrite stored values and explicit clear semantics remain distinct from omission.
- [ ] Add or update service CRUD regression tests with explicit no-reload expectations.
- [ ] Add entity-surface coverage for live sensor and button creation/removal.
- [ ] Add helper payload integrity coverage so dashboard-facing IDs remain valid after live CRUD.
- [ ] Update test helpers and docs that currently assume options-flow CRUD replaces the coordinator via reload.

## Acceptance criteria

1. Creating a chore does not require a full integration reload and produces the expected live sensors and buttons.
2. Updating assignments adds and removes assignee-linked entities correctly without reload.
3. Shared/independent criteria transitions update the shared-state sensor correctly.
4. Deleting a chore removes linked entities and helper references without reload.
5. Dashboard helper payloads expose valid entity IDs after live chore CRUD.
6. Options-flow chore CRUD no longer depends on deferred reload for correctness.
7. System settings reload behavior remains intact.
8. Sparse edit submissions in chore options flow preserve omitted stored values for optional fields instead of resetting them to schema defaults.
9. Phase 3B coverage demonstrates closure across representative optional-field behavior patterns, not just the original ESV06 field.

## Validation gates

- `./utils/quick_lint.sh --fix`
- Targeted chore-focused suites during implementation, including at minimum:
  - `python -m pytest tests/test_options_flow_per_kid_helper.py::TestSchemaEdgeCases::test_esv06_edit_partial_section_payload_preserves_schedule_fields -v --tb=line`
  - `python -m pytest tests/test_chore_crud_services.py -v --tb=line`
  - `python -m pytest tests/test_entity_lifecycle_stability.py -v --tb=line`
- Full-suite rerun is not part of the implementation loop for this issue branch unless explicitly requested or required by a newly discovered blocker.

## Required handback from builder

1. Changed-files summary grouped by Package A-D.
2. The final runtime sync contract shape and where it lives.
3. Any fallback path, compatibility wrapper, or temporary shim left in place, with explicit justification and removal condition. Default expectation is `none`.
4. Targeted and full-suite test results.
5. Confirmation that no schema bump was required.
6. Parent plan summary update in [docs/completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md](CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md).

## Final handback

1. Runtime sync contract shape: chore-scoped mutation-context orchestration via `ChoreEntitySyncContext`, coordinated in `coordinator.py`, with platform-local entity creation in `sensor.py` and `button.py` plus shared cleanup helpers in `helpers/entity_helpers.py`.
2. Validation outcome: `./utils/quick_lint.sh --fix` passed, and `python -m pytest tests/test_chore_runtime_entity_sync.py tests/test_chore_crud_services.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py tests/test_options_flow_daily_multi.py -v --tb=line` passed (`100 passed`) on 2026-04-12.
3. Fallback path inventory: no new fallback path, compatibility wrapper, or temporary shim was introduced. `async_sync_entities_after_service_create()` remains only for non-chore service callers and is outside the completed chore runtime-sync scope.
4. Schema bump confirmation: none required.
5. Release note summary: chore create, edit, and delete now update runtime sensors, buttons, and dashboard helper payloads without a full integration reload. Sanctioned system-settings edits still reload the integration.
