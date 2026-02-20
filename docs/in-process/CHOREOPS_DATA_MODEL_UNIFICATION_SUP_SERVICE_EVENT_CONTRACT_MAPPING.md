# Supporting Doc: ChoreOps hard-fork service/event contract mapping

## Purpose

Define the old-to-new field contract mapping for the schema45 hard-fork cutover.
This document is the approval artifact for implementation sequencing.

Architecture docs should describe the canonical model and current contract,
not transitional mapping details.

## Scope

- In scope:
  - Service payload field rename contract (legacy -> hard-fork)
  - Event/notification action naming cutover points
  - Approval checklist before runtime implementation
- Out of scope:
  - Backward-compatible runtime alias parsing
  - Migration internals not directly tied to request/event contracts

## Contract policy (locked)

- Hard-fork runtime policy: only new field names are accepted in runtime handlers.
- Legacy mapping is documented here for migration communication and review only.
- Migration code paths may transform persisted legacy payloads where needed.
- Service docs and release notes must include before/after examples.
- `linked_*` runtime terminology should be removed by plan completion; keep any
  linked/shadow legacy names only in migration compatibility handling.
- Migration-only constants belong in `custom_components/choreops/migration_pre_v50_constants.py`.

## Service field mapping matrix (approved direction)

### Core actor naming

| Legacy field  | New field       | Meaning                                      | Notes                                                 |
| ------------- | --------------- | -------------------------------------------- | ----------------------------------------------------- |
| `kid_name`    | `assignee_name` | User targeted for assignment/claim workflows | Required where assignee context is currently required |
| `kid_id`      | `assignee_id`   | Internal ID for assignee                     | Keep supported; optional for user-facing calls        |
| `parent_name` | `approver_name` | User targeted for approval workflows         | Use only for approval-domain service calls            |
| `parent_id`   | `approver_id`   | Internal ID for approver                     | Keep supported; optional for user-facing calls        |

### Domain object naming (no role bucket terms)

| Legacy/common term                        | New canonical term | Notes                                      |
| ----------------------------------------- | ------------------ | ------------------------------------------ |
| `kid` actor references in service APIs    | `assignee`         | Actor role in workflow, not identity class |
| `parent` actor references in service APIs | `approver`         | Capability role in workflow                |
| `kid_*` event payload keys                | `assignee_*`       | Keep service/event parity                  |

### Candidate service surfaces to cut over

Based on current `services.py` and `services.yaml` references, the rename scope
includes, at minimum, service schemas still using `kid_name` and `parent_name`
for chore/reward approval and reporting workflows.

## Notification/event contract cutover matrix (approved direction)

| Surface                             | Legacy key/segment | New key/segment       | Decision              |
| ----------------------------------- | ------------------ | --------------------- | --------------------- |
| Notification action payload segment | `kid_id` segment   | `assignee_id` segment | Approved (switch now) |
| Event payload for actor label       | `parent_name`      | `approver_name`       | Approved              |
| Event payload actor id              | `kid_id`           | `assignee_id`         | Approved              |

## Naming decisions to lock before implementation

1. **Actor vocabulary is role-based**
   - Use `assignee` and `approver` in service/event contracts.
   - Avoid `kid`/`parent` in runtime payload interfaces.

2. **Name-based fields remain required for user-facing calls**
   - Keep `*_name` fields for user-facing service usage.
   - `*_id` fields may remain supported, but are not required for normal user operation.

3. **Service/event parity rule**
   - Equivalent concepts use the same key names across services and events.
   - No mixed terms (`assignee_*` in service and `kid_*` in event) in final runtime.

4. **Capability vs actor separation**
   - Capability flags remain `can_approve`, `can_manage`, `can_be_assigned`.
   - Request payloads identify actors (`assignee_*`, `approver_*`), not capability flags.

5. **Prohibited new terminology in runtime contracts**
   - Do not introduce `owner_*`, `guardian_*`, or `manager_*` actor fields unless
     explicitly added to this doc and approved.

## Approval checklist (required before code cutover)

- [ ] Mapping table approved by product + architecture owner
- [ ] Service-by-service rename list confirmed (`services.yaml`)
- [ ] Event/notification payload parity approved
- [ ] Release-note migration examples drafted and reviewed
- [ ] Contract-lint rule targets approved (`kid_name`, `parent_name`, legacy dual parsing)

## Owner decisions captured (2026-02-19)

1. Name-based fields must be kept for user-facing service calls.
2. Notification/action payload contract should switch in this same cutover wave.
3. Dashboard migration examples must not assume templates under `custom_components/choreops/templates`; dashboard sources may be external.

## Implementation guardrails after approval

- Update constants first (`FIELD_ASSIGNEE_NAME`, `FIELD_ASSIGNEE_ID`,
  `FIELD_APPROVER_NAME`, `FIELD_APPROVER_ID`).
- Update service schemas/handlers and `services.yaml` in one batch.
- Update notification action parsing in one batch (same cutover wave as service contract).
- Update `translations/en.json` keys/texts and service docs in same wave to keep
  naming parity with runtime contract changes.
- Add/adjust tests for mixed-role scenarios in the same PR wave.
- Reject runtime reintroduction of legacy alias parsing outside migration modules.

## Migration communication note

- Script/dashboard examples must cover both Home Assistant automations and
  externally maintained dashboard repositories.
- Do not scope migration instructions to local template files only.
