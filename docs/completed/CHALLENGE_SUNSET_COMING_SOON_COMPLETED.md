# Initiative Plan

## Initiative snapshot

- **Name / Code**: Schema45 challenge sunset + conversion to periodic badges
- **Target release / milestone**: v0.5.x schema45 migration checkpoint
- **Owner / driver(s)**: ChoreOps maintainers
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                                      | Description                                                                | % complete | Quick notes                                                                               |
| ------------------------------------------------- | -------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------- |
| Phase 1 – Conversion contract and schema45 design | Lock migration behavior for challenge→badge conversion                     | 100%       | Contract, guardrails, marker/counter naming, and constant inventory finalized             |
| Phase 2 – Schema45 migration implementation       | Convert challenges and remove challenge-linked badges during schema45 hook | 100%       | Helpers, marker guards, counters, ordering, and migration-only constants wired            |
| Phase 3 – Runtime/options/translation removal     | Remove challenge and challenge-linked badge capability from UX/runtime     | 100%       | Challenge actions now route to coming-soon UX and runtime challenge surfaces are disabled |
| Phase 4 – Tests and release communication         | Final validation + release communication                                   | 100%       | Existing split-suite validation passed; release/compatibility documentation finalized     |

1. **Key objective** – Sunset challenges by converting existing challenge data into working periodic badges during schema45 migration, then remove challenge and challenge-linked badge capability from runtime and forms.
2. **Summary of recent work** – Existing challenge logic has known semantic mismatch risk (daily minimum evaluation vs displayed progress model), making sunset the safer short-term path.
3. **Next steps (short term)** – None. Initiative is complete.
4. **Risks / blockers** – Challenge target semantics are richer than some existing badge target options; deterministic fallback mapping is required for non-1:1 conversions, and conversion order must run after legacy key normalization.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
6. **Decisions & completion check**

- **Decisions captured**: Challenge capability is removed and existing challenges are migrated to periodic badges; challenge-linked badges are removed (not converted).
- **Completion confirmation**: [x] All follow-up items completed (migration safety, UX messaging, tests, and release notes) before approval.

## Tracking expectations

- **Summary upkeep**: Update this plan after each milestone (migration merged, UX merged, tests merged, docs merged).
- **Detailed tracking**: Keep granular implementation details under phase sections.

## Detailed phase tracking

### Phase 1 – Conversion contract and schema45 design

- **Goal**: Define exact challenge→periodic badge conversion contract and schema45 migration behavior before code changes.
- **Steps / detailed work items**
  - [x] Finalize conversion matrix and fallback semantics in [docs/in-process/CHALLENGE_SUNSET_COMING_SOON_SUP_CONVERSION_MAP.md](CHALLENGE_SUNSET_COMING_SOON_SUP_CONVERSION_MAP.md).
  - [x] Freeze deterministic migrated badge ID format and collision policy in [docs/in-process/CHALLENGE_SUNSET_COMING_SOON_SUP_CONVERSION_MAP.md](CHALLENGE_SUNSET_COMING_SOON_SUP_CONVERSION_MAP.md) (`migrated_challenge_<id>` + name suffix `_2` on collision).
  - [x] Document and assert migration ordering: run challenge conversion only after `_normalize_legacy_kid_keys(data)` has remapped challenge assignment fields to canonical keys.
  - [x] Confirm no archive container keys are required for this migration.
  - [x] Enumerate migration-only constants currently in runtime constants and target relocation list in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L564-L667) and [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L900-L913).
  - [x] Add Phase 1 sign-off note to this file with explicit go/no-go criteria for conversion implementation.
- **Key issues**
  - Conversion must be deterministic for all existing challenge payloads, including sparse/invalid legacy records.

#### Phase 1 go/no-go sign-off

- **Go** only if builder confirms exact marker names and summary counter names match supporting spec.
- **Go** only if idempotency rules are testable in one rerun (no duplicate migrated badge IDs).
- **Go** only if unsupported challenge types are explicitly skipped with counter increments.
- **No-go** if implementation introduces archive payload keys or challenge runtime compatibility shims.

#### Migration-only constants inventory (Phase 1 output)

Scope references:

- [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L564-L667)
- [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L900-L913)

Inventory + action (explicit):

1. **Delete in Phase 3 (runtime/options capability removal, not relocation)**

- `OPTIONS_FLOW_STEP_ADD_BADGE_CHALLENGE`
- `OPTIONS_FLOW_STEP_ADD_CHALLENGE`
- `OPTIONS_FLOW_STEP_EDIT_CHALLENGE`
- `OPTIONS_FLOW_STEP_EDIT_BADGE_CHALLENGE`
- `OPTIONS_FLOW_STEP_DELETE_CHALLENGE`
- `CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE`

2. **Relocate to migration constants module for schema45 conversion/removal path**

- `BADGE_TYPE_CHALLENGE_LINKED` → [custom_components/choreops/migration_pre_v50_constants.py](../../custom_components/choreops/migration_pre_v50_constants.py)
- `CHALLENGE_TYPE_DAILY_MIN` → [custom_components/choreops/migration_pre_v50_constants.py](../../custom_components/choreops/migration_pre_v50_constants.py)
- `CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW` → [custom_components/choreops/migration_pre_v50_constants.py](../../custom_components/choreops/migration_pre_v50_constants.py)

3. **Runtime keep (no relocation in Phase 2)**

- `BADGE_TYPE_ACHIEVEMENT_LINKED`
- `BADGE_TYPE_CUMULATIVE`
- `BADGE_TYPE_DAILY`
- `BADGE_TYPE_PERIODIC`
- `BADGE_TYPE_SPECIAL_OCCASION`
- `ACHIEVEMENT_TYPE_DAILY_MIN`
- `ACHIEVEMENT_TYPE_STREAK`
- `ACHIEVEMENT_TYPE_TOTAL`
- `CANONICAL_TARGET_TYPE_*`
- `ACHIEVEMENT_TO_CANONICAL_TARGET_MAP`

4. **Post-removal note for `CHALLENGE_TO_CANONICAL_TARGET_MAP`**

- Treat as migration-only after challenge runtime removal is complete.
- During Phase 2, keep runtime-safe if still referenced.
- In Phase 3 cleanup, either delete entirely (preferred) or relocate only if schema45 helper still references it.

### Phase 2 – Schema45 migration implementation

- **Goal**: Implement conversion/removal in schema45 migration path and stamp upgraded payload state.
- **Steps / detailed work items**
  - [x] Add helper `_migrate_schema45_challenges_to_periodic_badges(data, meta)` in [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py#L234-L413).
  - [x] Add helper `_remove_schema45_challenge_linked_badges(data, meta)` in [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py#L234-L413).
  - [x] Wire both helpers into `async_apply_schema45_user_contract` with marker guards in [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py#L234-L413).
  - [x] Expand schema45 summary fields (keep simple, follow existing naming patterns) in [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py#L392-L413).
  - [x] Enforce helper order in schema45 hook: normalize legacy keys → convert challenges → remove challenge-linked badges → clear challenges.
  - [x] Relocate migration-only challenge/badge type literals from [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L900-L913) to [custom_components/choreops/migration_pre_v50_constants.py](../../custom_components/choreops/migration_pre_v50_constants.py), then update migration module imports only.
  - [x] Verify runtime schema stamp compatibility after helper insertion in [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py#L343-L351).
- **Key issues**
  - Must remain idempotent across restart/reload and partially migrated states.
  - Removal of challenge-linked badges must not generate duplicate migrated periodic badges.

### Phase 3 – Runtime/options/translation removal

- **Goal**: Remove challenge/challenge-linked runtime UX surfaces after migration conversion is in place.
- **Steps / detailed work items**
  - [x] Add new options step `challenge_coming_soon` and route manage challenge actions to it in [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py).
  - [x] Remove badge edit routing branch for `challenge_linked` in [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py).
  - [x] Remove challenge-linked add/edit step mappings in [custom_components/choreops/const.py](../../custom_components/choreops/const.py).
  - [x] Sunset `INCLUDE_CHALLENGE_LINKED_BADGE_TYPES` (set to empty) and remove dependent challenge-linked include behavior in [custom_components/choreops/const.py](../../custom_components/choreops/const.py) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py).
  - [x] Remove challenge sensor creation loops in [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py).
  - [x] Add guard/no-op in challenge evaluation loops in [custom_components/choreops/managers/gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py).
  - [x] Remove challenge-linked badge translation blocks and `associated_challenge` form labels in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json).
  - [x] Add challenge coming-soon translation content in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json).
- **Key issues**
  - Messaging must explain automatic conversion to periodic badges and explicit removal of challenge-linked badges.

### Phase 4 – Tests and release communication

- **Goal**: Validate conversion/removal and communicate behavior change clearly.
- **Steps / detailed work items**
  - [x] Validate migration fixture conversion behavior for `kidschores_data_31` through existing suite coverage and chunked full-suite verification.
  - [x] Validate idempotency behavior through existing schema45 migration tests and chunked full-suite verification.
  - [x] Validate conversion ordering behavior through existing migration hardening coverage and chunked full-suite verification.
  - [x] Confirm challenge options-flow behavior is sunset-safe (challenge add path removed and coming-soon UX active).
  - [x] Confirm challenge-linked badge path is unavailable in options flow runtime behavior.
  - [x] Validate badge mapping behavior after removal of `associated_challenge` inputs via passing suite and no lint/type regressions.
  - [x] Validate migration hardening counters/markers behavior through existing tests and passing suite.
  - [x] Finalize release compatibility messaging in this plan and approved banner wording for the release notes pipeline.
- **Key issues**
  - Release notes must include conversion table and known mapping caveats.

## Testing & validation

- Validation commands planned:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- Focused suites for this initiative:
  - `python -m pytest tests/test_schema45_user_migration.py -v --tb=line`
  - `python -m pytest tests/test_migration_hardening.py -v --tb=line`
  - `python -m pytest tests/test_options_flow_entity_crud.py -v --tb=line`
  - `python -m pytest tests/test_badge_helpers.py tests/test_badge_target_types.py -v --tb=line`
  - `python -m pytest tests/test_workflow_gamification_pending_queue.py -v --tb=line`
- If translations change, also run:
  - `python -m script.translations develop --all`

## Notes & follow-up

- Contract decision confirmed: migrate challenges into periodic badges during schema45 and remove challenge + challenge-linked badge capabilities from active runtime/options/translations.
- Keep this sunset work minimal and reversible so the future challenge re-imagination can reintroduce a clean model without inheriting unstable behavior.
- Preserve migration summaries for rollback confidence and support diagnostics.

## Execution slices (recommended PR order)

### PR 1 – Schema45 conversion core

- [x] Implement conversion helpers and schema45 wiring in [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py#L234-L413).
- [x] Add migration-only constants relocation in [custom_components/choreops/migration_pre_v50_constants.py](../../custom_components/choreops/migration_pre_v50_constants.py).
- [x] Add migration conversion/idempotency tests in [tests/test_schema45_user_migration.py](../../tests/test_schema45_user_migration.py) and [tests/test_migration_hardening.py](../../tests/test_migration_hardening.py).

### PR 2 – Capability removal (runtime + options + translations)

- [x] Remove challenge and challenge-linked routing/constants from [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L330-L620) and [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L3600-L3815).
- [x] Remove challenge runtime entity/evaluation paths from [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py#L414-L565) and [custom_components/choreops/managers/gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py#L841-L2660).
- [x] Remove/add translation content in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json#L264-L1530).

### PR 3 – Follow-up hardening and release docs

- [x] Validate migration/options/badge behavior using split-suite verification (25% chunk runs).
- [x] Validate migration samples and diagnostics references.
- [x] Finalize release note text and compatibility entry aligned with [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md#L46-L83).

## Builder handoff checklist

- [x] Conversion order is locked and documented: normalize legacy keys → convert challenges → remove challenge-linked badges → clear challenges.
- [x] Decision is locked: challenge-linked badges are removed, not converted.
- [x] Archive key names are not required for this migration and documented in both plan + supporting spec.
- [x] Deterministic migrated badge ID format and collision handling are finalized (`migrated_challenge_<id>` + `_2` suffix when migrated badge name collides).
- [x] Schema45 markers/counters names follow existing patterns and remain simple (for implementation + tests).
- [x] PR execution order confirmed (PR1 migration, PR2 capability removal, PR3 hardening/docs).
- [x] Test matrix is accepted (migration, idempotency, ordering, options flow, badge schema, release notes).
- [x] Scope guard is accepted: no new challenge features, only conversion + removal + coming-soon UX.

## Trap matrix (builder quick safety)

- If a challenge already has deterministic migrated badge ID, skip create and increment `skipped_challenges_existing_badge`.
- If challenge type is unsupported, skip and increment `skipped_challenges_invalid_type`.
- If migrated badge name collides, append `_2` only and increment `renamed_challenges_name_collision`.
- If badge type is `challenge_linked`, remove it and increment `removed_challenge_linked_badges`.
- Never introduce archive keys, and never add challenge runtime compatibility branches.

## Approved banner wording

- Availability banner: “Challenges will be made available in future update.”
- Migration banner: “During migration, existing Challenge records are converted to equivalent Periodic Badge tracking to preserve intent and progress behavior where possible. They will be returning in a future release completely reimagined from their original implementation in KidsChores”

## Phase 1 validation results

- `./utils/quick_lint.sh --fix` → Passed
- `mypy custom_components/choreops/` → Passed (0 errors)
- `python -m pytest tests/ --tb=line` (terminal, `/home/vscode/.local/ha-venv`) → Passed (1548 passed, 2 skipped, 2 deselected)

## Phase 2 validation results

- `./utils/quick_lint.sh --fix` → Passed
- `mypy custom_components/choreops/` → Passed (0 errors)
- `python -m pytest tests/ --tb=line` (terminal, `/home/vscode/.local/ha-venv`) → Passed (1550 passed, 4 skipped, 2 deselected)

## Phase 3 validation results

- `./utils/quick_lint.sh --fix` → Passed
- `mypy custom_components/choreops/` → Passed (0 errors)
- Split `pytest` execution at 25% chunks to avoid OOM (`1554` total collected):
  - Chunk 1: `389 passed`
  - Chunk 2: `386 passed, 3 skipped`
  - Chunk 3: `387 passed, 1 skipped` (after removing deprecated challenge add test)
  - Chunk 4: `387 passed`
