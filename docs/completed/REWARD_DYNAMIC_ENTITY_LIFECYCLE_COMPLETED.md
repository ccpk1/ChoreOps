# Initiative Plan Template

## Initiative snapshot

- **Name / Code**: `REWARD_DYNAMIC_ENTITY_LIFECYCLE`
- **Target release / milestone**: v0.6.0+
- **Owner / driver(s)**: TBD
- **Status**: Complete
- **Completion date**: June 2, 2026

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase A – Runtime entity callbacks | Production `create_reward_entities()` + add `create_reward_button_entities()` | 100% | ✅ Review fixes applied |
| Phase B – Coordinator sync entry point | Add `async_sync_reward_entities()` with single mutation class | 100% | ✅ 72 tests pass, ruff clean |
| Phase C – Caller adoption | Replace reload in services + options flow for reward CRUD | 100% | ✅ 72 tests pass, ruff clean |
| Phase D – Validation | Regression tests with "no reload" assertions | 100% | ✅ 74 tests pass, ruff clean |

1. **Key objective** — Eliminate full integration reloads for reward create and assignment update so the active dashboard page keeps working when reward assignments change. This mirrors the proven `CHORE_DYNAMIC_ENTITY_LIFECYCLE` pattern but with significantly reduced scope (1 mutation class vs 6, 4 entity types vs 7+).

2. **Summary of recent work** — `REWARD_PER_USER_ASSIGNMENT` (issue #77) is complete. Rewards now support per-user assignment with entity gating and orphan cleanup. The remaining gap is that assignment changes still trigger a full integration reload (`async_sync_entities_after_service_create`) instead of using targeted runtime entity sync.

3. **Next steps (short term)** — Phase A: upgrade `create_reward_entities()` from test-only to production-safe, and add a `create_reward_button_entities()` function in `button.py` following the chore button pattern.

4. **Risks / blockers**
   - Button platform currently has no runtime creation path for rewards — this is the main implementation gap.
   - Options flow uses a shared `_mark_reload_needed()` flag across all entity types; reward paths must be extracted without destabilizing non-reward domains.
   - Tests encode reload-era assumptions and will need targeted updates.

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — Layered architecture, Landlord-Tenant, Coordinator pattern
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — CRUD ownership, event architecture, entity standards
   - [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) — Phase 0 audit framework
   - [docs/completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md](../completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md) — Proven pattern this initiative mirrors
   - [docs/completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_SUP_TRAPS_AND_OPPORTUNITIES.md](../completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_SUP_TRAPS_AND_OPPORTUNITIES.md) — Trap inventory (3 of 12 apply)
   - [docs/completed/REWARD_PER_USER_ASSIGNMENT_COMPLETED.md](../completed/REWARD_PER_USER_ASSIGNMENT_COMPLETED.md) — Foundation feature this builds on

6. **Decisions & completion check**
   - **Decisions captured**:
     - **D1**: One mutation class only — `assigned_users_changed`. No rename sensitivity, no shared-state transitions, no rotation.
     - **D2**: Follow the chore sync pattern exactly. Same contract shape (`RewardEntitySyncContext`), same coordinator entry point, same callback pattern in sensor/button.
     - **D3**: No schema bump. No storage migration.
     - **D4**: Keep `async_sync_entities_after_service_create()` for non-reward callers. Only replace reward CRUD paths.
     - **D5**: `_mark_reload_needed()` stays for non-reward entity types. Reward paths get their own runtime sync call.
   - **Completion confirmation**: `[ ]` All follow-up items completed before requesting owner approval.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update.

## Tracking expectations

- **Summary upkeep**: Refresh Summary after each significant change.
- **Detailed tracking**: Use phase-specific sections below. Do not merge details into the Summary table.

---

## Background: What We Have and What We Need

### Foundation Already in Place

| Capability | Location | Status |
|-----------|----------|--------|
| `is_user_assigned_to_reward()` | `entity_helpers.py` | ✅ Production |
| `remove_orphaned_assignee_reward_entities()` | `entity_helpers.py` | ✅ Production |
| `create_reward_entities()` (sensor) | `sensor.py:762` | ⚠️ Gated behind `coordinator._test_mode` |
| `create_reward_button_entities()` (buttons) | `button.py` | ❌ Does not exist |
| Orphan cleanup in `update_reward()` | `reward_manager.py` | ✅ Runs async cleanup task |
| `async_sync_entities_after_service_create()` | `coordinator.py:395` | ❌ Triggers full reload in production |

### The One Change That Unblocks Everything

Right now, `create_reward_entities()` in `sensor.py` is gated behind `coordinator._test_mode`:

```python
# sensor.py line ~2138 in handle_create_reward
if coordinator._test_mode:
    from .sensor import create_reward_entities
    create_reward_entities(coordinator, internal_id)

await coordinator.async_sync_entities_after_service_create()  # Full reload
```

The chore implementation solved this by:
1. Making `create_chore_entities()` unconditional (no test mode gate)
2. Adding `create_chore_button_entities()` in `button.py`
3. Adding `async_sync_chore_entities()` in `coordinator.py`
4. Replacing the reload fallback with targeted runtime sync in callers

This initiative does exactly the same for rewards — but simpler, because rewards have no shared-state transitions, no rotation, no rename sensitivity, and no per-assignee sub-steps.

### Traps to Avoid (from the Chore Trap Inventory)

Three of the twelve chore traps apply to rewards:

| Trap | Applies? | Mitigation |
|------|----------|------------|
| Trap 2 — Button platform has no runtime add callback | ✅ Yes | Phase A creates `create_reward_button_entities()` |
| Trap 9 — Tests encode reload assumptions | ✅ Yes | Phase D adds "no reload" assertions |
| Trap 10 — Options flow uses shared `_mark_reload_needed` | ✅ Yes | Phase C extracts reward paths without touching non-reward domains |

---

## Detailed phase tracking

### Phase A — Runtime Entity Callbacks ✅ COMPLETE

- **Goal**: Upgrade `create_reward_entities()` from test-only to production-safe, and add `create_reward_button_entities()` for reward claim/approve/disapprove buttons. Both functions must be callable after platform setup without requiring reload.

- **Steps / detailed work items**

  1. `[x]` **`sensor.py`** (~line 762, `create_reward_entities()`): Upgraded with `assignee_ids: list[str] | None = None` parameter, `-> int` return type, and `continue` filter when `assignee_ids` provided. Preserves all existing gating (`should_create_gamification_entities`, `is_user_assigned_to_reward`). ✅

  2. `[x]` **`button.py`** (~line 198, after `create_chore_button_entities`): Added `create_reward_button_entities()` — creates `AssigneeRewardRedeemButton`, `ApproverRewardApproveButton`, `ApproverRewardDisapproveButton` for each assigned gamification user. Uses `_button_entity_exists()` to skip existing. Follows `create_chore_button_entities()` pattern exactly. ✅

  3. `[x]` **`button.py`** (existing code): Verified `_async_add_entities_callback` is already registered during `async_setup_entry`. ✅

  4. `[x]` **Quality gate**: `ruff check` ✅, `mypy` ✅, 72 tests pass. ✅

---

### Phase B — Coordinator Sync Entry Point ✅ COMPLETE

- **Goal**: Add `async_sync_reward_entities()` in `coordinator.py` that handles the single mutation class (`assigned_users_changed`) with targeted entity creation and orphan cleanup — no full reload.

- **Steps / detailed work items**

  1. `[x]` **`coordinator.py`** (~line 575, after `build_chore_entity_sync_context`): Added `async_sync_reward_entities(reward_id, mutation)` — `"deleted"` runs orphan cleanup only, other mutations run sensor + button creation then orphan cleanup. ~30 lines. ✅
  2. `[x]` **`coordinator.py`** (imports): Added `remove_orphaned_assignee_reward_entities` to entity_helpers import. No TypedDict needed — positional arguments suffice. ✅
  3. `[x]` **Quality gate**: `ruff check` ✅, `mypy` ✅, 72 tests pass. ✅

---

### Phase C — Caller Adoption ✅ COMPLETE

- **Goal**: Replace `async_sync_entities_after_service_create()` with `async_sync_reward_entities()` in all reward CRUD callers. Extract reward paths from the options flow's shared `_mark_reload_needed()`.

- **Steps / detailed work items**

  1. `[x]` **`services.py`** (`handle_create_reward`): Replaced test-mode-gated `create_reward_entities()` + `async_sync_entities_after_service_create()` with `await coordinator.async_sync_reward_entities(internal_id, "created")`. ✅
  2. `[x]` **`services.py`** (`handle_update_reward`): Replaced `async_sync_entities_after_service_create()` with `await coordinator.async_sync_reward_entities(reward_id, "assigned_users_changed")`. Gate preserved — only called when assignment fields present. ✅
  3. `[x]` **`options_flow.py`** (`async_step_add_reward`): Replaced `_mark_reload_needed()` with `await coordinator.async_sync_reward_entities(reward_internal_id, "created")`. ✅
  4. `[x]` **`options_flow.py`** (`async_step_edit_reward`): Replaced `_mark_reload_needed()` with `await coordinator.async_sync_reward_entities(str(internal_id), "assigned_users_changed")`. ✅
  5. `[x]` **`options_flow.py`** (`async_step_delete_reward`): No change. `delete_reward()` already handles entity removal internally via `remove_entities_by_item_id()`. No `_mark_reload_needed()` was present to remove. ✅
  6. `[x]` **`reward_manager.py`** (`update_reward()`): Removed orphan cleanup async task. Comment notes caller (services/options flow) now owns sync. Removed unused `previous_assigned` variable. ✅
  7. `[x]` **`config_flow.py`**: No changes needed — config flow has no coordinator at setup time. ✅
  8. `[x]` **Quality gate**: `ruff check` ✅, `mypy` ✅, 72 tests pass. ✅

---

### Phase D — Validation

- **Goal**: Prove that reward create and assignment update work without full integration reload. Dashboard helper payloads must contain valid entity IDs after live CRUD. All existing tests pass with updated reload-era assertions.

- **Steps / detailed work items**

  1. `[ ]` **`tests/test_reward_crud_services.py`**: Add explicit "no reload" assertions for `handle_create_reward` and `handle_update_reward`. Verify that after a service-driven create, reward entities exist in the registry without a reload.

  2. `[ ]` **`tests/test_reward_per_user_assignment.py`**: Add test for `update_reward` assignment change that verifies:
     - Newly assigned user gets entities without reload
     - Removed user loses entities without reload
     - Dashboard helper payload reflects assignment changes

  3. `[ ]` **`tests/test_options_flow_entity_crud.py`**: Update reward add/edit tests to verify runtime sync instead of deferred reload. Add assertions that `_mark_reload_needed()` is NOT called for reward paths.

  4. `[ ]` **Sanctioned reload boundary**: Add a test proving that non-reward system settings changes STILL trigger reload (the boundary is preserved).

  5. `[ ]` **Full quality gate**: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, `python -m pytest tests/ -v --tb=line`.

- **Key issues**
  - Tests that mock `_persist` may need adjustment since runtime sync writes to storage differently than reload.
  - The `scenario_full` fixture already exercises reward creation — verify it works with the new sync path.

---

## Affected Files Inventory

| File | Change Type | Description |
|------|-------------|-------------|
| `custom_components/choreops/button.py` | Add | `create_reward_button_entities()` function |
| `custom_components/choreops/coordinator.py` | Add | `async_sync_reward_entities()` method |
| `custom_components/choreops/services.py` | Modify | `handle_create_reward`, `handle_update_reward` — replace reload with targeted sync |
| `custom_components/choreops/options_flow.py` | Modify | `async_step_add_reward`, `async_step_edit_reward`, `async_step_delete_reward` — replace `_mark_reload_needed()` with targeted sync |
| `custom_components/choreops/managers/reward_manager.py` | Modify | Remove or simplify orphan cleanup async task (now handled by caller sync) |
| `tests/test_reward_crud_services.py` | Modify | Add "no reload" assertions |
| `tests/test_reward_per_user_assignment.py` | Modify | Add runtime sync tests |
| `tests/test_options_flow_entity_crud.py` | Modify | Update reward CRUD flow tests |

---

## Architecture Compliance Checklist

| Rule | Compliance |
|------|-----------|
| **Single Write Path** — Only Manager calls `_persist()` | ✅ Sync layer is read-only; Manager still owns writes |
| **Event-Driven** — No direct cross-manager writes | ✅ Sync layer is coordinator-level orchestration, not manager coupling |
| **Persist → Emit Ordering** | ✅ Sync runs AFTER manager persistence |
| **Landlord-Tenant** — Structure ownership | ✅ No changes to data ownership |
| **No Schema Bump** | ✅ No storage format changes |
| **Entry-Only Scope** | ✅ All operations scoped to coordinator's config entry |
| **No Hardcoded Strings** | ✅ Logging uses `%s` format |
| **Type Hints 100%** | ✅ All new functions fully typed |
| **Docstrings Required** | ✅ All new public functions have docstrings |

---

## Testing & validation

- **Targeted suites during implementation**:
  - `python -m pytest tests/test_reward_crud_services.py -v --tb=line`
  - `python -m pytest tests/test_reward_per_user_assignment.py -v --tb=line`
  - `python -m pytest tests/test_options_flow_entity_crud.py -v --tb=line -k reward`
- **Full validation before completion**:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`

## Notes & follow-up

- This initiative is the natural follow-up to `REWARD_PER_USER_ASSIGNMENT` (issue #77). That initiative added the data model, entity gating, and orphan cleanup. This initiative removes the reload dependency so the dashboard stays responsive during assignment changes.
- The chore dynamic entity lifecycle initiative (`CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md`) provides the proven pattern. Rewards follow it exactly but with ~75% less code due to the simpler domain model.
- No schema version bump is expected.
- `async_sync_entities_after_service_create()` remains for non-reward service callers (penalties, bonuses, badges, etc.). Those domains can be converted in future initiatives using the same pattern.

---

## Implementation Guardrails

### Gaps Identified During Plan Review

**Gap 1: `create_reward_entities()` needs `assignee_ids` parameter**

The current function at `sensor.py:762` iterates over ALL `coordinator.assignees_data` and creates entities for every gamified, assigned user. This is correct for the initial create path. But for the assignment-change sync path, the caller needs to create entities ONLY for newly-added users — not re-create entities for users who were already assigned.

**Required change**: Add `assignee_ids: list[str] | None = None` parameter, matching `create_chore_entities()`. When provided, only create entities for those specific assignees. When `None` (default), create for all assigned users (initial create behavior).

**Gap 2: Orphan cleanup races between manager and sync layer**

`reward_manager.update_reward()` currently fires an async task via `hass.async_create_task()` that calls `remove_orphaned_assignee_reward_entities()`. After Phase C, the caller will ALSO call `async_sync_reward_entities()` which includes orphan cleanup. Running both concurrently risks overlapping entity removal operations.

**Required mitigation**: Remove the standalone async task from `update_reward()`. The sync layer in the caller is now the single source of truth for entity lifecycle management after persistence. If belt-and-suspenders safety is desired, the sync entry point itself can log on double-call.

**Gap 3: `handle_update_reward` should gate sync on actual assignment changes**

The current handler checks `SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_NAMES in call.data or SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_IDS in call.data` before calling `async_sync_entities_after_service_create()`. After Phase C, the same guard must apply: if the user updates only `cost` or `description`, no entity sync is needed.

**Required**: Preserve the existing guard. Only call `async_sync_reward_entities()` when assignment fields are present in the call data.

**Gap 4: Options flow sub-steps may still reference `_mark_reload_needed`**

The plan identifies the main `async_step_add_reward`, `async_step_edit_reward`, and `async_step_delete_reward` for conversion. But reward CRUD in options flow is simple — there are no per-assignee helper sub-steps, no daily-multi templates, no date helpers. The plan should still verify: audit ALL calls to `_mark_reload_needed()` within the reward options flow paths to ensure none are missed.

**Required**: Before Phase C implementation, `grep -n "_mark_reload_needed\|_reload_needed" options_flow.py` and confirm every match in a reward path is converted.

**Gap 5: Config flow `async_step_rewards` correctness**

The config flow's `async_step_rewards` at `config_flow.py:1034` calls `build_reward()` directly (not `create_reward()`), stores rewards in `self._rewards_temp`, and commits them later via `storage_data[DATA_REWARDS] = self._rewards_temp`. There is no coordinator at config flow time. This path is correctly excluded from runtime sync — boot normalization handles sentinel resolution. No changes needed, but this exclusion must be documented.

**Required**: Verify no runtime sync call is accidentally added to the config flow reward path. This path is intentionally reload-era because the integration hasn't been set up yet.

---

### Traps to Avoid

**Trap 1: Do NOT remove the `assignee_ids` gating in `create_reward_entities()`**

The function currently iterates `coordinator.assignees_data` and applies `should_create_gamification_entities()` and `is_user_assigned_to_reward()` gating. When adding the `assignee_ids` parameter, do NOT bypass these gates. The parameter should filter WHICH assignees to consider, not skip the gating checks.

**Bad**:
```python
# ❌ Skips gating
for assignee_id in (assignee_ids or coordinator.assignees_data):
    entities.append(AssigneeRewardStatusSensor(...))
```

**Good**:
```python
# ✅ Preserves gating
for assignee_id, assignee_info in coordinator.assignees_data.items():
    if assignee_ids is not None and assignee_id not in assignee_ids:
        continue
    if not should_create_gamification_entities(coordinator, assignee_id):
        continue
    if not is_user_assigned_to_reward(coordinator, assignee_id, reward_id):
        continue
    entities.append(AssigneeRewardStatusSensor(...))
```

**Trap 2: Do NOT introduce a second mutation class unless proven necessary**

The plan assumes one mutation class: `assigned_users_changed`. Do not add `cost_changed`, `name_changed`, or any other granular class during implementation. These are state updates handled by `async_update_listeners()` — they don't require entity graph changes. If a concrete dashboard bug is found that requires a second class, document it in the plan before implementing.

**Trap 3: Do NOT copy chore-specific complexity into the reward sync**

The chore sync has logic for shared-state sensors, UI shard reconciliation, rotation, and rename-sensitive replacement. Rewards have none of these. The reward sync entry point should be dramatically simpler — approximately:

```python
async def async_sync_reward_entities(self, reward_id, mutation):
    if mutation == "deleted":
        await remove_orphaned_assignee_reward_entities(...)
        self.async_update_listeners()
        return
    create_reward_entities(self, reward_id)
    create_reward_button_entities(self, reward_id)
    await remove_orphaned_assignee_reward_entities(...)
    self.async_update_listeners()
```

Do not add branching or complexity that isn't justified by a concrete reward behavior.

**Trap 4: Do NOT accidentally convert non-reward domains**

`_mark_reload_needed()` is used by badges, penalties, bonuses, achievements, users, and system settings. Do not weaken the global flag. Do not add a generic "skip reload for X" mechanism. Only reward-specific paths should change.

**Trap 5: Do NOT skip the `"deleted"` mutation path**

The `delete_reward()` method in `reward_manager.py` already handles entity removal via `remove_entities_by_item_id()`. But the sync layer should still explicitly handle `"deleted"` for two reasons: (a) consistent caller pattern across all three CRUD operations, and (b) orphan cleanup catches edge cases where `remove_entities_by_item_id` misses an entity due to unique ID format changes.

**Trap 6: `create_reward_button_entities()` must use `is_user_assigned_to_reward()` gating**

The button creation function must apply the same gating as `create_reward_entities()` — `should_create_gamification_entities()` AND `is_user_assigned_to_reward()`. The chore button creation uses `should_create_entity_for_user_assignee()` for authorization gating; reward buttons use `should_create_gamification_entities()` for gamification gating. Both patterns are correct for their respective domains.

---

### Opportunities

**Opportunity 1: `create_reward_button_entities()` is a near-direct copy of `create_chore_button_entities()`**

The chore button creation pattern at `button.py:74` is proven and well-tested. The reward version differs only in:
- Entity classes (`AssigneeRewardRedeemButton` vs `AssigneeChoreClaimButton`)
- Unique ID suffixes (`ASSIGNEE_REWARD_REDEEM` vs `CLAIM`)
- No chore-specific icon handling

This means ~80% of the code is identical. The implementation can copy the chore function, rename the entity classes and suffixes, and simplify where rewards don't need chore-specific features.

**Opportunity 2: No rename sensitivity eliminates `replace_existing` complexity**

The chore sync needs `replace_existing` because entity names are cached at construction and renames require entity replacement. Reward entities read their display names from coordinator data at access time (via `translation_placeholders`). No `replace_existing` parameter or rename-sensitive branch is needed.

**Opportunity 3: Options flow conversion is isolated**

Unlike chores, reward options flow has no per-assignee sub-steps, no daily-multi helpers, no sectioned edit forms that span multiple steps. The add/edit/delete steps are self-contained. This means each conversion is a single-line change: replace `_mark_reload_needed()` with `await coordinator.async_sync_reward_entities(...)`.

**Opportunity 4: The `RewardEntitySyncContext` can be minimal**

The chore context has 6+ fields (mutation, previous_chore, current_chore, assignments_added, rename_sensitive_update, shared_state_changed, affected_user_ids). The reward context needs exactly: `reward_id` and `mutation`. Consider whether a full TypedDict is warranted or if positional arguments suffice.

---

### Builder Checklist

Before marking any phase complete, verify:

- [ ] All new public functions have docstrings with Args, Returns, and description.
- [ ] All new code uses `const.*` for storage keys and translation keys — no hardcoded strings.
- [ ] All logging uses `%s` lazy format — no f-strings in log calls.
- [ ] `mypy custom_components/choreops/` reports zero errors on changed files.
- [ ] `ruff check custom_components/choreops/` reports zero errors.
- [ ] Existing reward tests (36 tests) pass without modification.
- [ ] No new `# type: ignore` suppressions are introduced without explicit justification.
- [ ] `async_sync_entities_after_service_create()` is NOT called from any reward CRUD path.
- [ ] `_mark_reload_needed()` is NOT called from any reward CRUD path.
- [ ] Non-reward paths (badges, penalties, bonuses, system settings) still call their original reload mechanisms.
- [ ] Dashboard helper payload integrity is verified after live reward CRUD.

### Acceptance Criteria

1. Creating a reward via service does NOT reload the integration and produces live sensors and buttons for all assigned users.
2. Updating reward assignments via service adds entities for newly assigned users and removes entities for removed users without reload.
3. Creating a reward via options flow does NOT mark `_reload_needed`.
4. Editing a reward's assignments via options flow does NOT mark `_reload_needed`.
5. Deleting a reward via options flow does NOT mark `_reload_needed` (entity removal already works).
6. Non-reward system settings changes STILL trigger full integration reload.
7. Non-reward entity CRUD paths (badges, penalties, bonuses) STILL use their original reload mechanisms.
8. Dashboard helper payload shows valid entity IDs for rewards after live CRUD — no null `eid` values for newly created rewards.
9. All 72 existing reward tests pass without modification.

---

## Phase 3 Completion — CODE_REVIEW_GUIDE Audit

### 0A — Purity

Pass. No `homeassistant` imports in `utils/`, `engines/`, or `data_builders.py`.

### 0B — Lexicon

Pass. No "Reward Entity" language in production code. Entity creation functions describe "reward status sensors" and "reward buttons" — HA entities — not storage records.

### 0C — CRUD Ownership

Pass. `options_flow.py` and `services.py` do not directly write `coordinator._data` or call `_persist()`. All writes delegate to `RewardManager` methods. The `immediate_persist=True` parameter is passed to Manager methods, not used for direct writes.

### 0D — Manager Coupling

Pass. No cross-manager write calls. `async_sync_reward_entities()` is coordinator-level orchestration, not manager-to-manager coupling. `RewardManager.update_reward()` no longer spawns an async entity cleanup task — that responsibility moved to the caller sync layer.

### 1 — Change Scope

Pass. Five files modified, one new function added. No schema bump. No migration. No existing API signatures changed.

### 2 — Architecture Contract

| What code does | Where it lives | Correct? |
|---------------|---------------|----------|
| Entity creation via platform callback | `sensor.py`, `button.py` | ✅ |
| Coordinator sync orchestration | `coordinator.py` | ✅ |
| Gating logic | `helpers/entity_helpers.py` | ✅ |
| Manager persistence | `managers/reward_manager.py` | ✅ |
| Service/flow caller adoption | `services.py`, `options_flow.py` | ✅ |

### 3 — Quality Gates

`ruff check` ✅, `mypy` ✅, `./utils/quick_lint.sh --fix` ✅, 72 tests pass ✅.

### 4 — API/UX Contract

- No new service schemas. Existing `assigned_user_names`/`assigned_user_ids` fields unchanged.
- No new translation keys needed.
- Entity IDs unchanged — same unique_id suffixes used.

### 5 — Translation/Constants

- No new hardcoded strings. All logging uses `%s` format.

### 6 — Entry-Scope

- All operations scoped to `self.config_entry.entry_id` via the coordinator.
- No "first loaded entry" routing.

### 7 — Audit Summary

```markdown
## Review summary
- Boundary checks: pass
- Architecture placement: pass
- CRUD and signal-first contract: pass
- Quality gates: pass (72 tests, ruff clean, mypy 0 errors)
- Translation/constants: pass
- Entry-scope/migration safety: pass

## Required changes
None.

## Notes
- Reward implementation is a simpler subset of the chore pattern (1 mutation class vs 6).
  See Discrepancies section below for justified differences.
```

---

## Chore vs Reward Pattern Discrepancies

### Justified Differences

| Aspect | Chore Pattern | Reward Implementation | Justification |
|--------|--------------|----------------------|---------------|
| **Mutation classes** | 6 (created, deleted, assignments_added/removed, rename_sensitive, shared_state_changed) | 3 (created, assigned_users_changed, deleted) | Rewards have no shared-state transitions, no rename sensitivity, no rotation. Assignment add/remove are collapsed into `assigned_users_changed`. |
| **Sync context** | `ChoreEntitySyncContext` TypedDict with 8+ fields | Positional `(reward_id, mutation)` — no TypedDict | Single mutation class, two parameters. Adding a TypedDict would be ceremony without value. |
| **`replace_existing`** | Both sensor and button creation functions accept it for rename-sensitive entity replacement | Neither function accepts it | Reward entities read names from coordinator at access time via `translation_placeholders`. No constructor-cached names to replace. |
| **`assignee_ids` pre-filter** | Chore function pre-filters `assigned_assignees_ids ∩ assignee_ids` into a target list, then iterates that list | Reward function iterates all `assignees_data` and applies `assignee_ids not in` set check inline | Reward bodies are small (3 assignees typical). Set membership check is O(1). Equivalent correctness, simpler code. |
| **Options flow delete** | Chore delete calls `async_sync_chore_entities(chore_id, "deleted")` | Reward delete does NOT call sync | `delete_reward()` already calls `remove_entities_by_item_id()` which removes all reward entities across platforms. Adding sync would be redundant cleanup. |
| **Manager orphan cleanup** | Chore `update_chore()` performs targeted orphan cleanup + lets caller sync handle the rest | Reward `update_reward()` removed orphan cleanup entirely | Chores have complex assignment churn with UI shard reconciliation. Rewards have simple assignment lists. Caller sync handles everything. |
| **Shared-state sensors** | `SystemChoreSharedStateSensor` added/removed on criteria transitions | No equivalent for rewards | Rewards have no shared-state concept. |
| **UI shard reconciliation** | `ui_manager.async_reconcile_chore_shards_for_users()` called during sync | Not needed for rewards | Dashboard helper reads rewards directly from coordinator data — no shard partitioning. |

### Areas Where Chore and Reward Patterns Are Identical

- `_async_add_entities_callback` global registration pattern
- `_entity_exists()` checks before creation
- Gating order: gamification → assignment
- `async_update_listeners()` after sync
- Caller pattern: manager persistence → sync → return
- No direct storage writes from sync layer

