# Chore dynamic entity lifecycle: traps and opportunities

## Purpose

This document is the risk register and implementation guardrail set for `CHORE_DYNAMIC_ENTITY_LIFECYCLE`.

The target outcome is narrow and strict:

- Chore create, update, and delete must stop requiring full integration reload.
- Active dashboard pages must remain usable without a manual Lovelace refresh.
- Existing signal-first manager architecture must remain intact.
- System settings and feature-flag reload behavior must stay separate unless explicitly expanded later.

This is not a speculative architecture note. It is a practical list of the places an implementation can fail.

## Non-negotiable invariants

1. Manager-owned writes stay manager-owned.
   The write path remains `modify -> persist -> notify -> emit` inside the owning manager. Services, options flow, and runtime entity sync helpers must not mutate `coordinator._data` directly.

2. Runtime entity synchronization is not a substitute for persistence.
   The entity graph must be synchronized only after the manager write has completed successfully.

3. System settings reload behavior stays intact.
   `config_entry.options` changes such as points label, update interval, and conditional entity flags continue to use integration reload unless explicitly separated in a follow-up initiative.

4. Existing entities and new entities are different problems.
   `async_update_listeners()` updates existing entities. It does not materialize missing ones. Any plan that treats those as equivalent will fail.

5. Delete and update must be treated as entity-graph operations when assignments or criteria change.
   Create is not the only graph mutation. Assignment edits, independent/shared transitions, and rename-sensitive constructor fields also affect runtime behavior.

6. The dashboard helper is a contract surface, not just a convenience sensor.
   If helper payloads point to missing or stale entity IDs, the dashboard can degrade even when backend writes are technically correct.

7. Test-mode behavior must not remain more capable than production behavior.
   The current create path already diverges by allowing direct sensor creation in tests while production reloads. The new design must remove that behavioral split.

## What already works and should be reused

### 1. Manager lifecycle contract already exists

`custom_components/choreops/managers/chore_manager.py` already does the hardest backend part correctly:

- `create_chore()` persists and emits `SIGNAL_SUFFIX_CHORE_CREATED`
- `update_chore()` persists, performs targeted orphan cleanup, and emits `SIGNAL_SUFFIX_CHORE_UPDATED`
- `delete_chore()` removes registry entities, cleans owned data, persists, and emits `SIGNAL_SUFFIX_CHORE_DELETED`

Opportunity:

- The implementation does not need a new CRUD architecture.
- The missing layer is runtime entity graph synchronization, not domain write logic.

### 2. Calendar already models the right read-path pattern

`custom_components/choreops/calendar.py` subscribes to chore mutation signals, invalidates caches, and writes state.

Opportunity:

- This proves that not every consumer needs explicit orchestration.
- Any surface that derives from coordinator data and registry lookups may only need signal/listener confirmation, not custom sync code.

### 3. Selector surfaces are already mostly dynamic

`custom_components/choreops/select.py` builds chore options from `coordinator.chores_data` on access.

Opportunity:

- Selectors likely do not need new entity creation for chore CRUD.
- They need validation that existing entities stay registered and that option lists reflect data changes immediately.

### 4. Delete cleanup primitives already exist

`remove_entities_by_item_id()`, `remove_orphaned_assignee_chore_entities()`, and `remove_orphaned_shared_chore_sensors()` already solve most removal cases.

Opportunity:

- Removal should be conservative and reuse these helpers.
- Most new work is on add-path symmetry, not delete-path invention.

## Primary trap inventory

### Trap 1: Production and test behavior diverge today

Where:

- `custom_components/choreops/coordinator.py`
- `custom_components/choreops/services.py`
- `custom_components/choreops/sensor.py`

Current behavior:

- Test mode can call `create_chore_entities()` directly.
- Production still reloads via `async_sync_entities_after_service_create()`.

Why this is dangerous:

- Tests can pass while production still depends on reload.
- A partial implementation may unintentionally preserve this split and create false confidence.

Implementation guardrail:

- Replace the divergence with one production-safe runtime sync path.
- If test-only branches remain, they should exercise the same runtime sync API, not a stronger alternate path.

### Trap 2: Button platform has no runtime add callback

Where:

- `custom_components/choreops/button.py`

Current behavior:

- Buttons are fully setup-time entities.
- New chores or new assignee/chore combinations cannot create claim/approve/disapprove buttons without reload.

Why this is dangerous:

- A sensor-only implementation will look partially correct in helper data while still breaking actual button interactions.
- Dashboard payloads may list chores whose backend button entity IDs do not exist.

Implementation guardrail:

- Do not mark the feature complete until button creation is handled for chore create and assignment expansion.
- Treat button runtime creation as a first-class requirement, not phase-two polish.

### Trap 3: Constructor-time name caching can leave stale UI copy

Where:

- `custom_components/choreops/button.py`
- `custom_components/choreops/sensor.py`
- `custom_components/choreops/select.py`

Current behavior:

- Many entities store `_chore_name`, `_assignee_name`, translation placeholders, or `_points_label` in `__init__`.

Why this is dangerous:

- Renames can leave existing entities showing stale names even if state values update.
- A no-reload change can appear broken only on rename paths, which are easy to miss in initial validation.

Implementation guardrail:

- Explicitly decide per entity family whether rename correctness requires:
  - runtime attribute recomputation from coordinator data, or
  - targeted entity replacement, or
  - a known limitation documented and deferred.

### Trap 4: Options flow assumes reload is the safe commit boundary

Where:

- `custom_components/choreops/options_flow.py`

Current behavior:

- `_reload_needed` is a generic flag used across many entity CRUD paths.
- Main menu entry can trigger deferred reload automatically.
- Chore helper steps store temp state in `_chore_being_edited` and related template fields.

Why this is dangerous:

- Removing reload only for chores can interact badly with a global deferred-reload mechanism still used by other entity types.
- A naive change can break options-flow navigation or leave stale temporary state after a live update.

Implementation guardrail:

- Separate chore runtime sync from the generic entity-reload flag rather than weakening the generic flag globally.
- Audit each chore step that currently calls `_mark_reload_needed()` and classify whether it actually needs graph sync, state refresh, or nothing.

### Trap 5: Assignment changes are more complex than create/delete

Where:

- `custom_components/choreops/managers/chore_manager.py`
- `custom_components/choreops/options_flow.py`
- `custom_components/choreops/services.py`

Current behavior:

- Update paths can add assignees, remove assignees, and switch criteria.
- Orphan cleanup exists for removed combinations.

Why this is dangerous:

- If runtime sync handles only brand-new chore creation, updated chores will still miss new assignee-specific sensors or buttons.
- These failures will be silent until someone edits assignments rather than creating a new chore.

Implementation guardrail:

- Treat these updates as first-class graph mutations:
  - assignee added
  - assignee removed
  - shared-state sensor introduced
  - shared-state sensor removed

### Trap 6: Completion-criteria transitions are structural, not cosmetic

Where:

- `custom_components/choreops/managers/chore_manager.py`

Current behavior:

- Criteria transitions route through specialized logic.

Why this is dangerous:

- `INDEPENDENT -> SHARED` and `SHARED -> INDEPENDENT` alter which entity families should exist.
- Shared-state sensor presence depends on criteria.

Implementation guardrail:

- Runtime sync must accept mutation context, not just a chore ID.
- The sync layer needs to know whether to add or remove a `SystemChoreSharedStateSensor` and whether per-assignee entities changed meaningfully.

### Trap 7: Dashboard helper payload can expose missing entity IDs

Where:

- `custom_components/choreops/sensor.py` in `AssigneeDashboardHelperSensor.extra_state_attributes`

Current behavior:

- Helper iterates over `coordinator.chores_data`, then looks up entity IDs from the registry.
- It can include chore entries with `eid=None`.

Why this is dangerous:

- Dashboard cards may assume a valid `eid` exists for chore rows.
- Helper freshness depends on both coordinator data and registry state being aligned.

Implementation guardrail:

- Live create must ensure registry entities exist before the helper is expected to surface them.
- Live delete and de-assignment must ensure helper payload is rebuilt after registry cleanup.
- Add explicit tests for helper payload integrity, not just raw storage contents.

### Trap 8: Pending-change flags are not a general chore CRUD signal

Where:

- `custom_components/choreops/managers/ui_manager.py`
- `custom_components/choreops/sensor.py`

Current behavior:

- UI manager tracks `pending_chore_changed` for approval queue style changes.
- Flags are reset after helper attribute generation.

Why this is dangerous:

- These flags are not a safe proxy for all chore CRUD changes.
- A plan that assumes the helper will rebuild for create/delete because pending flags exist is incorrect.

Implementation guardrail:

- Ensure helper refresh relies on coordinator entity updates and registry consistency, not on pending-approval flags.

### Trap 9: Tests already encode current reload assumptions

Where:

- `tests/test_chore_crud_services.py`
- `tests/test_options_flow_entity_crud.py`
- `tests/helpers/setup.py`
- `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`

Current behavior:

- Some comments and helper patterns explicitly assume options flow reloads and that fresh coordinators must be reacquired afterward.
- Some service tests still describe sensor creation as incomplete without re-setup.

Why this is dangerous:

- A correct runtime-sync implementation will invalidate these assumptions.
- If tests are not updated deliberately, maintainers may “fix” the new behavior back toward reloads to satisfy old test expectations.

Implementation guardrail:

- Update tests and test docs in the same workstream.
- Add explicit “no reload required” assertions for chore CRUD.

### Trap 10: Global reload flag in options flow is shared by many domains

Where:

- `custom_components/choreops/options_flow.py`

Current behavior:

- `_mark_reload_needed()` is called by chores, badges, rewards, users, and more.

Why this is dangerous:

- Removing or changing this mechanism globally for chore work can accidentally destabilize unrelated entity types.

Implementation guardrail:

- Limit chore changes to chore-specific branches and leave non-chore reload paths untouched unless separately planned.

### Trap 11: Registry ordering matters for dashboard-facing consistency

Where:

- `custom_components/choreops/sensor.py`
- `custom_components/choreops/select.py`

Current behavior:

- Several helper structures depend on registry lookups to produce entity IDs.

Why this is dangerous:

- If helper rebuild happens before entity registration settles, the helper can momentarily return missing IDs.

Implementation guardrail:

- Runtime sync should finish entity add/remove work before relying on helper attribute rebuilds.
- Validation must include `await hass.async_block_till_done()` style sequencing in tests to catch ordering bugs.

### Trap 12: Runtime sync can overreach into generic infrastructure too early

Where:

- `custom_components/choreops/coordinator.py`
- any new helper/module added for runtime sync

Why this is dangerous:

- A generic entity synchronization framework is attractive, but it increases blast radius.
- Chores are the highest-value domain, so correctness matters more than elegance on the first pass.

Implementation guardrail:

- Keep v1 chore-scoped unless the abstraction emerges naturally after chore success.

## Opportunity inventory

### Opportunity 1: This is likely not a schema or migration initiative

No evidence so far suggests `.storage/choreops/choreops_data` needs to change.

Value:

- Lower rollout risk.
- No migration branch needed unless runtime metadata is later introduced.

### Opportunity 2: Delete path is already closer to final-state than create path

Delete already removes registry entities and owned data.

Value:

- The add path is the main missing capability.
- Implementation effort should concentrate on symmetric creation and update churn.

### Opportunity 3: Calendar and selectors reduce required code changes

Some surfaces already re-derive from coordinator state and signals.

Value:

- Not every platform needs explicit dynamic creation logic.
- The plan can prioritize button and sensor setup first.

### Opportunity 4: Helper sensor gives a backend-visible proxy for dashboard correctness

The dashboard helper already exposes chore lists, entity IDs, core sensor references, and grouped views.

Value:

- Backend tests can verify a large portion of dashboard continuity without frontend UI automation.

### Opportunity 5: Existing orphan-cleanup helpers can be promoted into the runtime contract

Current cleanup helpers already represent the negative-space definition of valid chore entities.

Value:

- They can anchor post-update cleanup after assignment shrinkage or criteria change.

## Required mutation classes for the runtime sync layer

The runtime sync layer must be designed around mutation classes, not a single “refresh” action.

1. Chore created
   - add assignee chore status sensors
   - add claim/approve/disapprove buttons for assigned assignees
   - add shared-state sensor if criteria is shared

2. Chore deleted
   - remove all chore-linked sensors and buttons
   - remove shared-state sensor if present
   - allow helper/select/calendar surfaces to naturally update from state + registry cleanup

3. Chore updated without graph change
   - no entity add/remove required
   - existing entities must refresh state/attributes
   - rename path may still need special handling

4. Chore updated with assignment expansion
   - add newly needed assignee-linked entities

5. Chore updated with assignment shrinkage
   - remove orphaned assignee-linked entities

6. Chore updated with criteria transition
   - add or remove shared-state sensor
   - validate whether existing assignee-linked entities remain valid or need replacement

## Recommended implementation sequence

1. Freeze contract and non-goals.
2. Add production-safe runtime add callbacks for chore sensors.
3. Add production-safe runtime add callbacks for chore buttons.
4. Create one chore-scoped runtime sync API that can handle create and update mutation classes.
5. Convert service handlers to call the new sync API.
6. Validate helper payload and entity registry behavior.
7. Convert options flow chore paths from deferred reload to targeted runtime sync.
8. Update tests and docs that currently assume reload.

This order is intentional. If options flow is converted first, the work will be harder to reason about because the generic reload system and temporary helper-state mechanics will obscure whether the entity-sync layer is actually correct.

## Explicit anti-patterns to avoid

1. Do not replace reload with plain `async_request_refresh()` and call it done.
   That only refreshes existing entities.

2. Do not let services create entities directly while options flow still reloads.
   That preserves behavioral split and makes defects harder to reproduce.

3. Do not remove `_mark_reload_needed()` globally.
   It is shared by other domains.

4. Do not add direct storage writes to services, options flow, or runtime sync helpers.
   Managers still own all writes.

5. Do not assume helper payload correctness from storage correctness alone.
   Registry state is part of the contract.

6. Do not postpone rename behavior analysis until after create/delete are done.
   Constructor-cached names will otherwise become a latent correctness bug.

## Acceptance criteria for “done correctly”

1. Creating a chore via service does not reload the integration and results in live sensor and button availability for all assigned assignees.
2. Updating a chore assignment adds entities for new assignees and removes entities for removed assignees without reload.
3. Updating completion criteria adds or removes the shared-state sensor correctly.
4. Deleting a chore removes all linked registry entities and helper references without reload.
5. Dashboard helper payload contains valid chore entity IDs after live CRUD operations.
6. Options flow chore CRUD can complete without relying on deferred reload for correctness.
7. System settings and feature-flag changes still use the sanctioned reload path and remain stable.
8. Tests no longer describe production as requiring reload or re-setup for chore sensor creation.

## Rollout recommendation

Recommended first release shape:

- chore-scoped runtime entity sync only
- services and chore options-flow paths included
- no generic multi-domain sync framework
- no config-entry settings refactor
- no schema version change

Recommended fallback if implementation risk spikes:

- land service-path runtime sync first
- hold options-flow conversion until the runtime sync layer is proven stable

That fallback still improves the most automation-friendly path while reducing the chance of entangling chore work with the generic options-flow reload system too early.
