# Supporting appendix: Phase 3C registry shared-template contract schema

## Purpose

Define the exact manifest contract for per-template shared-fragment governance in Phase 3C, including:

- field names and semantics,
- validation/default rules,
- one concrete template entry example,
- migration and compatibility notes.

This appendix is implementation guidance for:

- `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3C.md`
- `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md`

## Scope and non-goals

### In scope

- Dashboard registry contract fields on each template record.
- Validation behavior in integration parser/helpers.
- Deterministic single-path compiler input contract.

### Out of scope

- Any `.storage/choreops/choreops_data` schema changes.
- Any new user-facing feature behavior in dashboard cards.

## Proposed registry field model

Add one optional object per template entry in `dashboard_registry.json`:

```json
"shared_template_contract": {
  "version": 1,
  "required_fragments": [
    "button_card_template_user_chores_row_v1"
  ],
  "optional_fragments": [],
  "enforce": {
    "sync": true,
    "release_prepare": true,
    "release_apply": true,
    "create_update": true
  }
}
```

## Field definitions

### `shared_template_contract.version`

- Type: integer
- Required when `shared_template_contract` exists: yes
- Allowed values (Phase 3C): `1`
- Purpose: contract evolution marker for parser/compiler behavior.

### `shared_template_contract.required_fragments`

- Type: array of string fragment ids
- Required when `shared_template_contract` exists: yes
- Empty allowed: yes
- Fragment id format: same marker id namespace as `template_shared.<id>` and path-aware ids are valid (`rows/chore/action_v1`).
- Purpose: explicit required shared dependencies for template closure validation.

### `shared_template_contract.optional_fragments`

- Type: array of string fragment ids
- Required when `shared_template_contract` exists: yes (can be empty)
- Purpose: non-blocking dependencies; can be used for diagnostics/warnings only.

### `shared_template_contract.enforce`

- Type: object of booleans
- Required when `shared_template_contract` exists: yes
- Required keys in Phase 3C:
  - `sync`
  - `release_prepare`
  - `release_apply`
  - `create_update`
- Purpose: explicit policy gate for where strict validation is active.

## Validation rules (Phase 3C)

1. If `shared_template_contract` is missing, template remains valid (legacy compatibility).
2. If `shared_template_contract` exists, all required keys must be present and correctly typed.
3. `version != 1` is invalid in Phase 3C.
4. Duplicate fragment ids in `required_fragments` or `optional_fragments` are invalid.
5. Overlap between required and optional sets is invalid.
6. Unknown enforce keys are invalid (strict parsing).
7. Fragment ids must match shared marker id grammar used by parser/compose logic.

## Behavioral defaults

For templates without `shared_template_contract`:

- treat as legacy template,
- infer dependencies from marker scanning as current behavior,
- do not fail solely for missing contract object.

For templates with `shared_template_contract`:

- enforce required fragment closure in all enabled enforcement paths,
- fail fast with actionable errors on missing required fragments.

## Concrete template entry example

Illustrative `user-chores-v1` example snippet:

```json
{
  "template_id": "user-chores-v1",
  "display_name": "Chores (User)",
  "audience": "user",
  "lifecycle_state": "active",
  "source": {
    "type": "vendored",
    "path": "templates/user-chores-v1.yaml"
  },
  "dependencies": {
    "required": [
      {
        "id": "ha-card:auto-entities",
        "name": "Auto-Entities",
        "url": "https://github.com/thomasloven/lovelace-auto-entities"
      },
      {
        "id": "ha-card:button-card",
        "name": "Button Card",
        "url": "https://github.com/custom-cards/button-card"
      }
    ],
    "recommended": []
  },
  "shared_template_contract": {
    "version": 1,
    "required_fragments": [
      "button_card_template_user_chores_row_v1"
    ],
    "optional_fragments": [],
    "enforce": {
      "sync": true,
      "release_prepare": true,
      "release_apply": true,
      "create_update": true
    }
  }
}
```

## Migration and release notes

- No storage schema increment required.
- Registry schema changes require parser updates and contract tests before release.
- Release checklist must include contract validation and parity checks for all enforce=true paths.

## Definition of done for this appendix

- Field model approved by maintainer.
- Parser validation implemented with tests.
- One real template entry migrated and validated end-to-end.
- 3C handoff plan references this appendix.

## Maintainer review checklist (fast approval)

- [ ] Contract fields are clear, minimal, and backward-compatible.
- [ ] Registry remains validation metadata, not a second composition engine.
- [ ] Phase 3C explicitly avoids `.storage` schema/version changes.
- [ ] Validation rules are strict enough to catch drift without breaking legacy templates.
- [ ] Example entry and enforce-path intent are implementation-ready for Builder.
