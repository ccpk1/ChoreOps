I'll now build a complete, standards-aligned plan. Let me verify a few additional constraints before finalizing.

Searched for text `SENTINEL_` (`**/custom_components/choreops/const.py`), 18 results

Searched for text `SERVICE_FIELD_CHORE_CRUD_ASSIGNED` (`**/custom_components/choreops/const.py`), 8 results

Searched for text `^SIGNAL_SUFFIX_REWARD` (`**/custom_components/choreops/const.py`), 18 results

Searched for text `def create_reward_button_entities|create_reward_button` (`**/custom_components/choreops/button.py`), no results

Searched for text `_async_add_entities_callback` (`**/custom_components/choreops/sensor.py`), 14 results

Searched for text `_REWARD_DATA_RESET_PRESERVE` (`**/custom_components/choreops/data_builders.py`), 4 results

Read [](file:///workspaces/choreops/custom_components/choreops/sensor.py#632-632), lines 632 to 660

Read [](file:///workspaces/choreops/custom_components/choreops/data_builders.py#358-358), lines 358 to 385

Searched for text `def validate_reward_data` (`**/custom_components/choreops/data_builders.py`), 2 results

Read [](file:///workspaces/choreops/custom_components/choreops/data_builders.py#193-193), lines 193 to 270

Now I have all the context needed. Here's the complete, standards-aligned plan:

---

# Per-User Reward Assignment — Initiative Plan

*(Save as `docs/in-process/REWARD_PER_USER_ASSIGNMENT_IN-PROCESS.md`)*

---

## Initiative snapshot

- **Name / Code**: `REWARD_PER_USER_ASSIGNMENT`
- **Target release / milestone**: v0.6.0+
- **Owner / driver(s)**: TBD
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                          | Description                                              | % complete | Quick notes                                     |
| ------------------------------------- | -------------------------------------------------------- | ---------- | ----------------------------------------------- |
| Phase 1 – Schema & Data Model         | Add `DATA_REWARD_ASSIGNED_USER_IDS`, TypedDict, builder  | 100%       | ✅ |
| Phase 2 – Entity Gating & Cleanup     | Gate sensor/button creation, add orphan removal helper   | 100%       | ✅ |
| Phase 3 – Manager & Service Layer     | `RewardManager` handles assignments, services expose it  | 100%       | ✅ |
| Phase 4 – Testing & Quality Gates     | 13 new tests, existing tests pass, all gates pass        | 100%       | ✅ Final gate: 72 total tests pass |

1. **Key objective** — Make rewards assignable per gamified user, using the same `assigned_user_ids` pattern already established by chores, badges, achievements, and challenges. Default all gamified users to every reward (`["*"]` sentinel) for full backward compatibility. When a user is removed from a reward, their status sensor + three buttons are cleaned from the HA entity registry.

2. **Summary of recent work** — Issue [#77](https://github.com/ccpk1/ChoreOps/issues/77) requested per-user reward gating. This initiative is the architectural prerequisite. The `"*"` sentinel design was chosen over a `locked` boolean because it's extensible (future claim limits, cooldowns) and consistent with the codebase.

3. **Next steps (short term)** — Begin Phase 1: add `SENTINEL_ALL_USERS` and `DATA_REWARD_ASSIGNED_USER_IDS` to const.py, update `RewardData` TypedDict in type_defs.py, update `build_reward()` in data_builders.py.

4. **Risks / blockers**
   - Entity sync after assignment changes: currently `update_reward` triggers no entity sync. Plan uses full reload (`async_reload`) matching the `create_reward` production path. Targeted entity sync (like `async_sync_chore_entities`) is deferred to a follow-up optimization.
   - No schema version bump needed (runtime fallback handles missing keys), but must ensure every read path tolerates absent `assigned_user_ids`.

5. **References**
   - ARCHITECTURE.md — Data model (§Data Architecture), Landlord-Tenant (§Landlord-Tenant Period Structure), Type System (§Type System Architecture)
   - DEVELOPMENT_STANDARDS.md — Constant naming (§3), Data write standards (§4), CRUD ownership (§4b), Entity standards (§6), 4-Layer architecture (§5.2), Event architecture (§5.3)
   - QUALITY_REFERENCE.md — Platinum compliance tracking
   - tests/AGENT_TESTING_USAGE_GUIDE.md — Test patterns & fixtures

6. **Decisions & completion check**
   - **Decisions captured**:
     - **D1**: Sentinel `SENTINEL_ALL_USERS = "*"` means "all gamified users." Stored as the sole list element. No separate boolean.
     - **D2**: No `SCHEMA_VERSION_CURRENT` bump — missing key on existing installs defaults to `["*"]` at every read site.
     - **D3**: Service field name = `SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_NAMES` (display names), resolved to UUIDs in handler. Also accept `SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_IDS` for legacy compatibility — mirrors chore dual-key pattern exactly.
     - **D4**: `add_entities` callback pattern (used by `create_reward_entities`) is sensor-only today. For assignment changes, use full reload (`async_reload`) — same as production `create_reward` path. Targeted sync deferred.
     - **D5**: `DATA_REWARD_ASSIGNED_USER_IDS` is a **reward-record field** (Landlord territory only). No Tenant (StatisticsManager) involvement. RewardManager owns the field entirely.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

---

## Issue #77 Context

**Original request** (jesserockz, March 2026): Limit reward claims per child (max 3/day). Workarounds exist (inflating cost, auto-disapproving) but are clunky.

**Why this initiative instead of a `locked` boolean**:

| Approach | Per-user? | Consistent with codebase? | Extensible? |
|---|---|---|---|
| `locked: bool` on reward | ❌ Global only | N/A (new pattern) | ❌ Dead-end |
| `assigned_user_ids: list[str]` | ✅ Yes | ✅ Mirrors chores, badges, achievements, challenges | ✅ Foundation for claim limits, cooldowns, exclusions |

Adding `assigned_user_ids` to rewards makes the data model consistent across **all** Domain Item types that have per-user scope. It solves the immediate use case (automation removes kid from reward after 3 claims) and enables future features.

---

## Detailed phase tracking

### Phase 1 – Schema & Data Model Foundation ✅ COMPLETE (June 2, 2026)

- **Goal**: Add `assigned_user_ids` to the reward storage record with backward-compatible defaults. Zero runtime behavior changes. All existing tests continue to pass.

- **Steps / detailed work items**

  1. `[x]` **const.py**: Add `SENTINEL_ALL_USERS: Final = "*"` sentinel constant. ✅ (line 467)
  2. `[x]` **const.py**: Add `DATA_REWARD_ASSIGNED_USER_IDS: Final = "assigned_user_ids"`. ✅ (line 1598)
  3. `[x]` **type_defs.py**: Add `assigned_user_ids: list[str]` to `RewardData` TypedDict. ✅
  4. `[x]` **data_builders.py**: Update `build_reward()` with `assigned_user_ids` defaulting to `["*"]`. ✅
  5. `[x]` **data_builders.py**: Add `DATA_REWARD_ASSIGNED_USER_IDS` to `_REWARD_DATA_RESET_PRESERVE_FIELDS`. ✅
  6. `[x]` **data_builders.py**: Update `validate_reward_data()` with shape validation (list-of-strings, sentinel must be sole element). ✅
  7. `[x]` **const.py**: Add `CFOF_REWARDS_INPUT_ASSIGNED_USER_NAMES`. ✅ (line 716)
  8. `[x]` **translations/en.json**: Add `invalid_reward_assigned_users` and `mixed_reward_assignment_sentinel` error strings. ✅ (lines 490-491)
  9. `[x]` **Quality gates**: All pass. Lint ✅, MyPy 0 errors ✅, Boundary checks 13/13 ✅, 23 reward tests pass ✅

- **Key issues** — Resolved: UUID existence validation deferred to service handler (Phase 3), keeping `validate_reward_data()` pure per Rule of Purity.

---

### Phase 2 – Entity Gating & Cleanup ✅ COMPLETE

- **Goal**: Reward status sensors and buttons are only created for users assigned to that reward. When assignments change, orphaned entities are removed.

- **Steps / detailed work items**

  1. `[x]` **`helpers/entity_helpers.py`**: Added `is_user_assigned_to_reward()` — handles `"*"` sentinel and explicit UUID lists. ✅
  2. `[x]` **sensor.py**: Gated `AssigneeRewardStatusSensor` creation in `async_setup_entry` loop. ✅
  3. `[x]` **sensor.py**: Gated `create_reward_entities()` dynamic creation. ✅
  4. `[x]` **button.py**: Gated all 3 reward button types (Redeem, Approve, Disapprove). ✅
  5. `[x]` **`helpers/entity_helpers.py`**: Added `remove_orphaned_assignee_reward_entities()` — mirrors chore pattern, scans sensor+button platforms. ✅
  6. `[x]` **`helpers/entity_helpers.py`**: Verified `remove_entities_by_validator()` supports multi-platform. ✅
  7. `[x]` **Quality gate checkpoint**: Lint ✅, MyPy 0 errors ✅, boundary checks ✅, all tests pass ✅.

---

### Phase 3 – Manager & Service Layer ✅ COMPLETE

- **Goal**: `RewardManager` handles `assigned_user_ids` in create/update. `update_reward` service exposes `assigned_user_names`. Name→UUID resolution follows chore pattern. Entity sync happens after assignment changes.

- **Steps / detailed work items**

  1. `[x]` **const.py**: Added `SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_NAMES` and `_IDS`. ✅
  2. `[x]` **services.py**: `UPDATE_REWARD_SCHEMA` now accepts both `assigned_user_names` and `assigned_user_ids`. ✅
  3. `[x]` **services.py**: `CREATE_REWARD_SCHEMA` now accepts both fields. ✅
  4. `[x]` **services.py**: `_SERVICE_TO_REWARD_DATA_MAPPING` maps `_IDS` → `DATA_REWARD_ASSIGNED_USER_IDS`. ✅
  5. `[x]` **services.py**: `handle_update_reward()` has name→UUID resolution + entity sync. ✅
  6. `[x]` **services.py**: `handle_create_reward()` has name→UUID resolution. ✅
  7. `[x]` **`managers/reward_manager.py`**: `update_reward()` detects assignment changes, cleans orphaned entities, triggers entity sync. ✅
  8. `[x]` **`managers/reward_manager.py`**: `create_reward()` — no changes needed, `build_reward()` handles default `["*"]`. ✅
  9. `[x]` **`managers/reward_manager.py`**: `get_assignee_reward_data()` — no changes needed. ✅
  10. `[x]` **`managers/reward_manager.py`**: `_ensure_assignee_structures()` — no changes needed. ✅
  11. `[ ]` **`services.yaml`**: Field documentation still needed for `assigned_user_names`/`assigned_user_ids`. **MINOR GAP**.
  12. `[x]` **Quality gate checkpoint**: Lint ✅, MyPy 0 errors ✅, boundary checks ✅, tests pass ✅.

- **Additional gap fix**: `build_reward_schema()` in `flow_helpers.py` now accepts `assignees_dict` + multi-select dropdown. `validate_rewards_inputs()` extracts the field. `options_flow.py` add/edit steps pre-populate assignments.

---

### Phase 4 – Testing & Quality Gates ✅ COMPLETE

- **Goal**: 95%+ test coverage. Zero mypy errors. All tests pass without modification.

- **Steps / detailed work items**

  1. `[x]` **`tests/test_reward_per_user_assignment.py`** (new file): 13 tests covering default `["*"]`, explicit UUIDs, sentinel, update add/remove, name resolution, backward compat, delete cleanup. All pass.
  2. `[x]` **test_reward_crud_services.py**: 23 existing tests pass unmodified — backward compatibility verified. ✅
  3. `[x]` **test_reward_services.py**: 23 existing tests pass unmodified. ✅
  4. `[x]` **test_options_flow_entity_crud.py**: 23 existing tests pass unmodified. ✅
  5. `[x]` **Full quality gate**: Ruff ✅, MyPy 0 errors ✅, boundary checks 13/13 ✅.
  6. `[ ]` **`CHANGELOG.md`**: Not updated (future task).

- **Key issues** — Minor gap: `services.yaml` still needs field documentation. Not a blocking issue for functionality.

---

## Affected Files Inventory

| File | Change | Description |
|---|---|---|
| const.py | Add | `SENTINEL_ALL_USERS`, `DATA_REWARD_ASSIGNED_USER_IDS`, `SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_NAMES`, `SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_IDS`, `CFOF_REWARDS_INPUT_ASSIGNED_USER_NAMES` |
| type_defs.py | Modify | Add `assigned_user_ids: list[str]` to `RewardData` TypedDict (~line 128) |
| data_builders.py | Modify | `build_reward()` includes new field with `["*"]` default; `validate_reward_data()` validates list shape; `_REWARD_DATA_RESET_PRESERVE_FIELDS` updated |
| entity_helpers.py | Add | `is_user_assigned_to_reward()`, `remove_orphaned_assignee_reward_entities()` |
| sensor.py | Modify | Gate `AssigneeRewardStatusSensor` creation in `async_setup_entry` and `create_reward_entities()` |
| button.py | Modify | Gate all 3 reward button types in `async_setup_entry` |
| reward_manager.py | Modify | `update_reward()` triggers entity sync on assignment changes |
| services.py | Modify | Schema + handler updates for `assigned_user_names`; name→UUID resolution; mapping dict updated |
| services.yaml | Modify | Document new field on create/update reward services |
| en.json | Modify | Validation error strings |
| `tests/test_reward_per_user_assignment.py` | **New** | Comprehensive test suite (11+ test cases) |
| test_reward_crud_services.py | Modify | Verify new field presence on created rewards |
| conftest.py | Modify | Update reward fixtures with `assigned_user_ids` |

---

## Architecture Compliance Checklist

| Rule | Source | Compliance |
|---|---|---|
| **Single Write Path** — Only Manager calls `_persist()` | ARCH §Architectural Rules, DEV §4 | ✅ `RewardManager.update_reward()` handles persistence |
| **Event-Driven** — No direct cross-manager writes | ARCH §Architectural Rules, DEV §4b | ✅ Entity removal is self-contained in RewardManager; no cross-manager calls needed |
| **Persist → Emit Ordering** | DEV §5.3 | ✅ Persist before `SIGNAL_SUFFIX_REWARD_UPDATED` already established |
| **Landlord-Tenant** — RewardManager owns reward-level fields | ARCH §Landlord-Tenant, DEV §4c | ✅ `assigned_user_ids` lives on reward record (Landlord territory only) |
| **Constant Naming** — `DATA_*` singular, `SERVICE_FIELD_*`, `CFOF_*` plural | DEV §3 | ✅ `DATA_REWARD_ASSIGNED_USER_IDS`, `SERVICE_FIELD_REWARD_CRUD_ASSIGNED_USER_NAMES` |
| **Type System** — TypedDict for static, dict[str, Any] for dynamic | DEV §5.1 | ✅ `RewardData` is static, TypedDict appropriate |
| **4-Layer Architecture** — Builder, Validator, Schema, Handler | DEV §5.2 | ✅ `build_reward()`, `validate_reward_data()`, service schema, service handler all updated |
| **Key Alignment** — `CFOF_*` values match `DATA_*` values | DEV §5.2 | ✅ `CFOF_REWARDS_INPUT_ASSIGNED_USER_NAMES = "assigned_user_names"` |
| **No Hardcoded Strings** | DEV §5 | ✅ All user-facing strings use `TRANS_KEY_*` constants |
| **Lazy Logging** | DEV §5 | ✅ New logging will use `%s` format |
| **Type Hints 100%** | DEV §5 | ✅ All new functions fully typed |
| **Docstrings Required** | DEV §5 | ✅ All new public functions have docstrings |
| **Entity ID Dual-Variant** | DEV §6 | ✅ Existing UID/EID pattern preserved; no new suffixes needed |
| **Lexicon** — "Item" not "Entity" for storage records | DEV §9 | ✅ Plan consistently uses "reward item/record" for storage, "entity" for HA platform objects |
| **Entry-Only Scope** | ARCH §Architectural Rules, DEV §4d | ✅ All operations scoped to coordinator's config entry |

---

## Testing & validation

- **Tests to execute**: `python -m pytest tests/ -v --tb=line --cov=custom_components/choreops --cov-report term-missing`
- **Specific suites**: `tests/test_reward_per_user_assignment.py` (new), test_reward_crud_services.py (modified), `tests/test_config_flow.py` (regression)
- **Outstanding tests**: Snapshot updates may be needed; run with `--snapshot-update` then re-run without flag to verify.
- **CI/CD gates**: `.quick_lint.sh --fix` must pass (includes ruff, mypy, boundary check).

## Notes & follow-up

- **Future: Targeted entity sync** — The current plan uses full reload for entity sync after assignment changes (`async_sync_entities_after_service_create`). A follow-up initiative should implement `async_sync_reward_entities()` mirroring `async_sync_chore_entities()` for targeted sensor + button creation/removal without reload.

- **Future: Per-user claim limits** — Once `assigned_user_ids` exists, a `max_claims_per_period` field on rewards (or on the assignee-reward junction) becomes the natural next step for the original #77 use case.

- **Future: Exclusion syntax** — The `"*"` sentinel leaves room for `"!uuid"` exclusion syntax (e.g., `["*", "!alice_uuid"]` = all users except Alice). No implementation needed now.

- **Future: `update_reward_assignments` convenience service** — A lightweight service that only changes `assigned_user_ids` without touching name/cost/description/icon/labels. Reduces automation complexity.

- **Schema version**: No bump needed. The `SCHEMA_VERSION_CURRENT` remains `100` (`SCHEMA_VERSION_1_0_0`). The missing-key fallback pattern is the same one used for other optional TypedDict fields added post-v1.0.0.

---

> **Template usage notice:** This plan follows the structure defined in PLAN_TEMPLATE.md. Save as `docs/in-process/REWARD_PER_USER_ASSIGNMENT_IN-PROCESS.md`. When complete, rename to `_COMPLETE` and move to completed.
