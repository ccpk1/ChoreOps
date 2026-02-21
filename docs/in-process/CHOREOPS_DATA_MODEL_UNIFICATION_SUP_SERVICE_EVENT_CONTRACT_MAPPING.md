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
  - Translation contract parity and orphan-key cleanup requirements for service/event surfaces
- Out of scope:
  - Backward-compatible runtime alias parsing
  - Migration internals not directly tied to request/event contracts

## Contract policy (locked)

- Hard-fork runtime policy: only new field names are accepted in runtime handlers.
- Legacy mapping is documented here for migration communication and review only.
- Migration code paths may transform persisted legacy payloads where needed.
- Service docs and release notes must include before/after examples.
- Translation updates must ship in the same wave as runtime contract changes.
- `linked_*` runtime terminology should be removed by plan completion; keep any
  linked/shadow legacy names only in migration compatibility handling.
- Migration-only constants belong in `custom_components/choreops/migration_pre_v50_constants.py`.
- Locale files in both `custom_components/choreops/translations/` and `custom_components/choreops/translations_custom/` must not retain stale references to removed runtime keys.

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

## Service-by-service field mapping (implementation matrix)

This matrix is the implementation checklist for `services.yaml` + runtime handler parity.

| Service                    | Legacy request fields     | Hard-fork request fields         |
| -------------------------- | ------------------------- | -------------------------------- |
| `claim_chore`              | `kid_name`                | `assignee_name`                  |
| `approve_chore`            | `parent_name`, `kid_name` | `approver_name`, `assignee_name` |
| `disapprove_chore`         | `parent_name`, `kid_name` | `approver_name`, `assignee_name` |
| `redeem_reward`            | `parent_name`, `kid_name` | `approver_name`, `assignee_name` |
| `approve_reward`           | `parent_name`, `kid_name` | `approver_name`, `assignee_name` |
| `disapprove_reward`        | `parent_name`, `kid_name` | `approver_name`, `assignee_name` |
| `apply_bonus`              | `parent_name`, `kid_name` | `approver_name`, `assignee_name` |
| `apply_penalty`            | `parent_name`, `kid_name` | `approver_name`, `assignee_name` |
| `set_chore_due_date`       | `kid_name`                | `assignee_name`                  |
| `skip_chore_due_date`      | `kid_name`                | `assignee_name`                  |
| `reset_overdue_chores`     | `kid_name`                | `assignee_name`                  |
| `remove_awarded_badges`    | `kid_name`                | `assignee_name`                  |
| `generate_activity_report` | `kid_name`                | `assignee_name`                  |

## Script/automation migration examples

### Example 1: claim chore

Before (legacy):

```yaml
action: choreops.claim_chore
data:
  kid_name: "Henry"
  chore_name: "Brush teeth PM"
```

After (hard-fork):

```yaml
action: choreops.claim_chore
data:
  assignee_name: "Henry"
  chore_name: "Brush teeth PM"
```

### Example 2: approve chore

Before (legacy):

```yaml
action: choreops.approve_chore
data:
  parent_name: "Mom"
  kid_name: "Henry"
  chore_name: "Brush teeth PM"
```

After (hard-fork):

```yaml
action: choreops.approve_chore
data:
  approver_name: "Mom"
  assignee_name: "Henry"
  chore_name: "Brush teeth PM"
```

### Example 3: reward flow

Before (legacy):

```yaml
action: choreops.approve_reward
data:
  parent_name: "Dad"
  kid_name: "Henry"
  reward_name: "Movie Night"
```

After (hard-fork):

```yaml
action: choreops.approve_reward
data:
  approver_name: "Dad"
  assignee_name: "Henry"
  reward_name: "Movie Night"
```

## Runtime compatibility policy (explicit)

Runtime compatibility aliases are not supported in hard-fork mode. Legacy
fields (`kid_name`, `parent_name`) are migration-communication only and must not
be parsed by runtime service/event handlers outside migration modules.

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
- [ ] Translation cleanup scope approved (`translations/en.json` + `translations_custom/en_*.json` orphan-key cleanup + locale stale-key cleanup across both trees)

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
- Run translation hygiene audit for service/event surfaces:
  - remove orphaned keys in `translations/en.json`
  - remove orphaned keys in `translations_custom/en_dashboard.json`, `translations_custom/en_notifications.json`, and `translations_custom/en_report.json`
  - remove or reconcile stale locale references across `custom_components/choreops/translations/*.json`
  - remove or reconcile stale locale references across `custom_components/choreops/translations_custom/*.json`
  - attach audit artifact to in-process plan before sign-off
- Add/adjust tests for mixed-role scenarios in the same PR wave.
- Reject runtime reintroduction of legacy alias parsing outside migration modules.

## Migration communication note

- Script/dashboard examples must cover both Home Assistant automations and
  externally maintained dashboard repositories.
- Do not scope migration instructions to local template files only.
