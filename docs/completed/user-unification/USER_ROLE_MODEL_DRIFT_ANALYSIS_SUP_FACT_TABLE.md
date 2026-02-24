# Support matrix: User-first hard-fork fact table

## Scope and policy

- This table is the proposed approval baseline for **runtime contract** naming changes.
- Policy enforced: **no runtime compatibility aliases/fallbacks**.
- Exception: legacy compatibility transforms are allowed **only in migration modules**.
- Status: **Approved fact table (ratified)**.

## Matrix A — must-change contract surfaces

| Category           | Current constant name                         | Current value                          | Proposed constant name                       | Proposed value        | Action                       |
| ------------------ | --------------------------------------------- | -------------------------------------- | -------------------------------------------- | --------------------- | ---------------------------- |
| Lifecycle signal   | `SIGNAL_SUFFIX_ASSIGNEE_CREATED`              | `assignee_created`                     | `SIGNAL_SUFFIX_USER_CREATED`                 | `user_created`        | Replace                      |
| Lifecycle signal   | `SIGNAL_SUFFIX_ASSIGNEE_UPDATED`              | `assignee_updated`                     | `SIGNAL_SUFFIX_USER_UPDATED`                 | `user_updated`        | Replace                      |
| Lifecycle signal   | `SIGNAL_SUFFIX_ASSIGNEE_DELETED`              | `assignee_deleted`                     | `SIGNAL_SUFFIX_USER_DELETED`                 | `user_deleted`        | Replace                      |
| Lifecycle signal   | `SIGNAL_SUFFIX_APPROVER_CREATED`              | `approver_created`                     | `SIGNAL_SUFFIX_USER_CREATED`                 | `user_created`        | Remove role lifecycle signal |
| Lifecycle signal   | `SIGNAL_SUFFIX_APPROVER_UPDATED`              | `approver_updated`                     | `SIGNAL_SUFFIX_USER_UPDATED`                 | `user_updated`        | Remove role lifecycle signal |
| Lifecycle signal   | `SIGNAL_SUFFIX_APPROVER_DELETED`              | `approver_deleted`                     | `SIGNAL_SUFFIX_USER_DELETED`                 | `user_deleted`        | Remove role lifecycle signal |
| Data identity key  | `DATA_ASSIGNEE_ID`                            | `assignee_id`                          | `DATA_USER_ID`                               | `user_id`             | Replace usages               |
| Service field      | `SERVICE_FIELD_ASSIGNEE_ID`                   | `assignee_id`                          | `SERVICE_FIELD_USER_ID`                      | `user_id`             | Replace                      |
| Service field      | `SERVICE_FIELD_ASSIGNEE_NAME`                 | `assignee_name`                        | `SERVICE_FIELD_TARGET_USER`                  | `target_user`         | Replace                      |
| Service field      | `SERVICE_FIELD_APPROVER_NAME`                 | `approver_name`                        | NO CHANGE                                    | NO CHANGE             | NO CHANGE                    |
| Service alias      | `FIELD_ASSIGNEE_ID`                           | alias to `SERVICE_FIELD_ASSIGNEE_ID`   | —                                            | —                     | Remove                       |
| Service alias      | `FIELD_ASSIGNEE_NAME`                         | alias to `SERVICE_FIELD_ASSIGNEE_NAME` | —                                            | —                     | Remove                       |
| Service alias      | `FIELD_APPROVER_NAME`                         | alias to `SERVICE_FIELD_APPROVER_NAME` | —                                            | —                     | Remove                       |
| Data reset scope   | `DATA_RESET_SCOPE_ASSIGNEE`                   | `assignee`                             | `DATA_RESET_SCOPE_USER`                      | `user`                | Replace                      |
| Attribute identity | `ATTR_ASSIGNEE_NAME`                          | `assignee_name`                        | `ATTR_USER_NAME`                             | `user_name`           | Replace                      |
| Attribute identity | `ATTR_SELECTED_ASSIGNEE_NAME`                 | `selected_assignee_name`               | `ATTR_SELECTED_USER_NAME`                    | `selected_user_name`  | Replace                      |
| Attribute identity | `ATTR_SELECTED_ASSIGNEE_SLUG`                 | `selected_assignee_slug`               | `ATTR_SELECTED_USER_SLUG`                    | `selected_user_slug`  | Replace                      |
| Attribute identity | `ATTR_CHORE_TURN_ASSIGNEE_NAME`               | `turn_assignee_name`                   | `ATTR_CHORE_TURN_USER_NAME`                  | `turn_user_name`      | Replace                      |
| Attribute identity | `ATTR_DASHBOARD_ASSIGNEE_NAME`                | `assignee_name`                        | `ATTR_DASHBOARD_USER_NAME`                   | `user_name`           | Replace                      |
| Config flow field  | `CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES`        | `assigned_assignees`                   | `CFOF_CHORES_INPUT_ASSIGNED_USER_IDS`        | `assigned_user_ids`   | Replace                      |
| Config flow field  | `CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_ASSIGNEES`  | `assigned_assignees`                   | `CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS`  | `assigned_user_ids`   | Replace                      |
| Config flow field  | `CFOF_CHALLENGES_INPUT_ASSIGNED_ASSIGNEES`    | `assigned_assignees`                   | `CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS`    | `assigned_user_ids`   | Replace                      |
| Config flow field  | `CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES`   | `associated_assignees`                 | `CFOF_USERS_INPUT_ASSOCIATED_USER_IDS`       | `associated_user_ids` | Replace                      |
| Service field      | `SERVICE_FIELD_CHORE_CRUD_ASSIGNED_ASSIGNEES` | `assigned_assignees`                   | `SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS` | `assigned_user_ids`   | Replace                      |
| Service alias      | `SERVICE_FIELD_ASSIGNED_ASSIGNEES`            | `assigned_assignees`                   | `SERVICE_FIELD_ASSIGNED_USER_IDS`            | `assigned_user_ids`   | Replace                      |
| Storage key        | `DATA_ASSIGNED_ASSIGNEES`                     | `assigned_assignees`                   | `DATA_ASSIGNED_USER_IDS`                     | `assigned_user_ids`   | Replace                      |
| Storage key        | `DATA_CHORE_ASSIGNED_ASSIGNEES`               | `assigned_assignees`                   | `DATA_CHORE_ASSIGNED_USER_IDS`               | `assigned_user_ids`   | Replace                      |
| Storage key        | `DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES`         | `assigned_assignees`                   | `DATA_ACHIEVEMENT_ASSIGNED_USER_IDS`         | `assigned_user_ids`   | Replace                      |
| Storage key        | `DATA_CHALLENGE_ASSIGNED_ASSIGNEES`           | `assigned_assignees`                   | `DATA_CHALLENGE_ASSIGNED_USER_IDS`           | `assigned_user_ids`   | Replace                      |
| Storage key        | `DATA_APPROVER_ASSOCIATED_USERS`              | `associated_assignees`                 | `DATA_USER_ASSOCIATED_USER_IDS`              | `associated_user_ids` | Replace                      |
| Scan payload field | `CHORE_SCAN_ENTRY_ASSIGNEE_ID`                | `assignee_id`                          | `CHORE_SCAN_ENTRY_USER_ID`                   | `user_id`             | Replace                      |
| Config flow step   | `CONFIG_FLOW_STEP_ASSIGNEE_COUNT`             | `assignee_count`                       | `CONFIG_FLOW_STEP_USER_COUNT`                | `user_count`          | Consolidate                  |
| Config flow step   | `CONFIG_FLOW_STEP_ASSIGNEES`                  | `assignees`                            | `CONFIG_FLOW_STEP_USERS`                     | `users`               | Consolidate                  |
| Options flow step  | `OPTIONS_FLOW_STEP_ADD_ASSIGNEE`              | `add_assignee`                         | `OPTIONS_FLOW_STEP_ADD_USER`                 | `add_user`            | Consolidate                  |
| Options flow step  | `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE`             | `edit_assignee`                        | `OPTIONS_FLOW_STEP_EDIT_USER`                | `edit_user`           | Consolidate                  |
| Options flow step  | `OPTIONS_FLOW_STEP_DELETE_ASSIGNEE`           | `delete_assignee`                      | `OPTIONS_FLOW_STEP_DELETE_USER`              | `delete_user`         | Consolidate                  |
| Options flow menu  | `OPTIONS_FLOW_ASSIGNEES`                      | `manage_assignee`                      | `OPTIONS_FLOW_USERS`                         | `manage_user`         | Consolidate                  |

## Matrix B — role-semantic surfaces to keep as-is

| Category            | Constant name                  | Current value                          | Disposition             | Rationale                                         |
| ------------------- | ------------------------------ | -------------------------------------- | ----------------------- | ------------------------------------------------- |
| Role capability     | `DATA_USER_CAN_BE_ASSIGNED`    | `can_be_assigned`                      | Keep                    | Role capability on canonical user record          |
| Role capability     | `DATA_USER_CAN_APPROVE`        | `can_approve`                          | Keep                    | Role capability on canonical user record          |
| Role capability     | `DATA_USER_CAN_MANAGE`         | `can_manage`                           | Keep                    | Role capability on canonical user record          |
| Workflow semantics  | `ATTR_ASSIGNED_ASSIGNEES`      | `assigned_assignees`                   | CHANGE TO `assigned_to` | Describes assignment role set in workflow context |
| Workflow semantics  | `REPORT_STYLE_ASSIGNEE`        | `assignee`                             | Keep                    | Report presentation style, not lifecycle identity |
| Item type taxonomy  | `ENTITY_TYPE_ASSIGNEE`         | `assignee`                             | Remove from taxonomy    | Role is not an item type                          |
| Item type taxonomy  | `ENTITY_TYPE_APPROVER`         | `approver`                             | Remove from taxonomy    | Role is not an item type                          |
| Label               | `LABEL_ASSIGNEE`               | `Assignee`                             | Keep                    | User-facing role label                            |
| Label               | `LABEL_APPROVER`               | `Approver`                             | Keep                    | User-facing role label                            |
| Role action purpose | `PURPOSE_BUTTON_CHORE_APPROVE` | `Approver approves claimed chore`      | Keep                    | Explicit actor role semantics                     |
| Role action purpose | `PURPOSE_BUTTON_REWARD_REDEEM` | `Assignee redeems reward using points` | Keep                    | Explicit actor role semantics                     |

## Decision D1 — Item type vs role qualifier model

### What it currently controls

- `ENTITY_TYPE_*` values are used as **Domain Item routing discriminators** for lookup/validation maps.
- Primary control point: [custom_components/choreops/helpers/entity_helpers.py](custom_components/choreops/helpers/entity_helpers.py#L430-L519), where `get_item_id_by_name()` maps the type token to storage dict + name key.
- High usage surface: service handlers and managers pass these constants into item lookup helpers (for example [custom_components/choreops/services.py](custom_components/choreops/services.py#L558), [custom_components/choreops/managers/system_manager.py](custom_components/choreops/managers/system_manager.py#L671-L685)).
- This is **not** selecting Home Assistant platform entities (`sensor`, `button`, etc.); it selects ChoreOps Domain Item classes (user/chore/reward/badge...).

### Why this is a terminology concern

- Project terminology policy distinguishes Domain Items/Records from Home Assistant Entities.
- Role (`assignee`/`approver`) is capability/context on a user record, not an item class.

### Decision options

| Option | Choice                                                           | Effect                                    |
| ------ | ---------------------------------------------------------------- | ----------------------------------------- |
| D1-A   | Keep `ENTITY_TYPE_*` with assignee/approver entries              | Retains taxonomy/model mismatch           |
| D1-B   | Rename to `ITEM_TYPE_*` and remove role item types (recommended) | Clean item taxonomy + explicit role model |

**Decision outcome**: ✅ **D1-B approved** — adopt `ITEM_TYPE_*` taxonomy + `ROLE_*` qualifiers.

### Proposed mapping if D1-B is approved

| Current constant name                    | Current value | Proposed constant name  | Proposed value | Action                       |
| ---------------------------------------- | ------------- | ----------------------- | -------------- | ---------------------------- |
| `ENTITY_TYPE_ASSIGNEE`                   | `assignee`    | —                       | —              | Remove (role, not item type) |
| `ENTITY_TYPE_APPROVER`                   | `approver`    | —                       | —              | Remove (role, not item type) |
| `ENTITY_TYPE_CHORE`                      | `chore`       | `ITEM_TYPE_CHORE`       | `chore`        | Rename constant only         |
| `ENTITY_TYPE_REWARD`                     | `reward`      | `ITEM_TYPE_REWARD`      | `reward`       | Rename constant only         |
| `ENTITY_TYPE_PENALTY`                    | `penalty`     | `ITEM_TYPE_PENALTY`     | `penalty`      | Rename constant only         |
| `ENTITY_TYPE_BONUS`                      | `bonus`       | `ITEM_TYPE_BONUS`       | `bonus`        | Rename constant only         |
| `ENTITY_TYPE_BADGE`                      | `badge`       | `ITEM_TYPE_BADGE`       | `badge`        | Rename constant only         |
| `ENTITY_TYPE_ACHIEVEMENT`                | `achievement` | `ITEM_TYPE_ACHIEVEMENT` | `achievement`  | Rename constant only         |
| `ENTITY_TYPE_CHALLENGE`                  | `challenge`   | `ITEM_TYPE_CHALLENGE`   | `challenge`    | Rename constant only         |
| `DATA_USERS` (implicit user item bucket) | `users`       | `ITEM_TYPE_USER`        | `user`         | Add canonical user item type |

### Proposed role qualifier constants (new)

| Proposed constant name | Proposed value | Purpose                                       |
| ---------------------- | -------------- | --------------------------------------------- |
| `ROLE_ASSIGNEE`        | `assignee`     | Role qualifier for user lookup/filter/context |
| `ROLE_APPROVER`        | `approver`     | Role qualifier for user lookup/filter/context |

### Lookup contract after refinement

| Parameter         | Meaning                                                | Example                             |
| ----------------- | ------------------------------------------------------ | ----------------------------------- |
| `item_type`       | Domain record class                                    | `ITEM_TYPE_USER`, `ITEM_TYPE_CHORE` |
| `role` (optional) | User role qualifier when `item_type == ITEM_TYPE_USER` | `ROLE_ASSIGNEE`, `ROLE_APPROVER`    |

Example intent:

- "Find user by name with assignee capability" → `item_type=ITEM_TYPE_USER`, `role=ROLE_ASSIGNEE`
- "Find chore by name" → `item_type=ITEM_TYPE_CHORE`, no role qualifier

### Additional related rename candidates (if D1-B approved)

| Current symbol                                            | Proposed symbol                      | Notes                                                  |
| --------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------ |
| `OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE`                    | `OPTIONS_FLOW_PLACEHOLDER_ITEM_TYPE` | Placeholder refers to item-management flow             |
| generic local vars `entity_type` in item-lookup codepaths | `item_type`                          | Keep `entity_type` only where referring to HA entities |
| user role vars currently named `entity_type`              | `role`                               | Use only for assignee/approver capability context      |

## Matrix C — delete/remove only

| Category                       | Current constant name                                   | Current value         | Action                       |
| ------------------------------ | ------------------------------------------------------- | --------------------- | ---------------------------- |
| Runtime compatibility alias    | `FIELD_ASSIGNEE_ID`                                     | alias                 | Remove                       |
| Runtime compatibility alias    | `FIELD_ASSIGNEE_NAME`                                   | alias                 | Remove                       |
| Runtime compatibility alias    | `FIELD_APPROVER_NAME`                                   | alias                 | Remove                       |
| Runtime compatibility alias    | any additional `FIELD_*` role lifecycle aliases         | alias                 | Remove                       |
| Runtime role-lifecycle signals | `SIGNAL_SUFFIX_ASSIGNEE_*` / `SIGNAL_SUFFIX_APPROVER_*` | role lifecycle values | Remove from runtime contract |

## Matrix D — proposed `_ASSIGN*` exceptions for explicit approval

These are the only `_ASSIGN*` families proposed to remain in runtime contracts, because they model assignment relationships or assignment capability (not lifecycle identity).

| Category                | Constant / family                                    | Proposed disposition      | Justification                                                                 |
| ----------------------- | ---------------------------------------------------- | ------------------------- | ----------------------------------------------------------------------------- |
| Assignment relationship | `*_ASSIGNED_USER_IDS` (data/config/service families) | Keep (canonical)          | Expresses relationship “item is assigned to users”; not a user identity label |
| Assignment capability   | `DATA_USER_CAN_BE_ASSIGNED`                          | Keep (role capability)    | Capability flag on a user record; explicitly role-semantic                    |
| Assignment list field   | `assigned_to`-semantic workflow fields               | Keep per approved mapping | Approved in D2 as assignment semantics, not lifecycle identity                |

### Matrix D approval checklist (owner)

- [x] Approve keeping `*_ASSIGNED_USER_IDS` as canonical assignment-relation family
- [x] Approve keeping `DATA_USER_CAN_BE_ASSIGNED` as role-capability exception
- [x] Approve that all other non-exception `_ASSIGN*` runtime constants must be consolidated or removed

## Approval checklist (fact table ratification)

- [x] Approve Matrix A rows as required contract changes
- [x] Approve Matrix B rows as intentional role-semantic keepers
- [x] Approve Matrix C removals (no runtime compatibility aliases)
- [x] Confirm that any legacy normalization is migration-only
- [x] Confirm that renamed values are acceptable for service/event breaking changes in hard fork
- [x] Decide D1 (adopt `ITEM_TYPE_*` taxonomy + `ROLE_*` qualifiers)

## Notes

- This fact table intentionally prioritizes constants that define external/runtime contracts (signals, service fields, attributes, storage identity keys).
- Translation keys and prose labels are not exhaustively listed here unless they imply runtime contract drift.
- Decision note: assignment attribute naming row is intentionally approved as `assigned_to` for this migration tranche.
- After approval, this document becomes the canonical source of truth for implementation tranche planning.
