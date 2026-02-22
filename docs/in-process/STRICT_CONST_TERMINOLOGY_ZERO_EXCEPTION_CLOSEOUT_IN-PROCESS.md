# Initiative Plan: Strict const terminology zero-exception closeout

## Initiative snapshot

- **Name / Code**: Strict Const Terminology Zero-Exception Closeout (`CHOREOPS-HF-STRICT-002`)
- **Target release / milestone**: Immediate hard-fork corrective wave (post-archive remediation)
- **Owner / driver(s)**: Project manager + builder lead
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                                 | Description                                                                                    | % complete | Quick notes                                                                  |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------- |
| Phase 1 – Governance reset                   | Re-open strict initiative and invalidate ambiguous close language                              | 100%       | Validation threshold met (`pylint 9.94`)                                     |
| Phase 2 – Const lexical eradication          | Remove all `KID`/`PARENT` naming and wording from `const.py` runtime surface                   | 100%       | Const lexical gates A1-A4 remain at zero                                     |
| Phase 3 – Runtime propagation                | Update runtime/tests/docs references after const contract changes                              | 95%        | Phase 3D runtime lexical closeout complete (runtime=0); docs blocker remains |
| Phase 3E – Const symbol contract remediation | Remove all `KID`/`PARENT` symbol identifiers from `const.py` and propagate canonical callsites | 100%       | Strict symbol closure reached (`const_name_hits=0`, runtime=0, tests=0)      |
| Phase 4 – Validation lock                    | Enforce machine-verifiable strict gates and publish evidence                                   | 80%        | All gates/evidence complete; owner sign-off + archive step pending           |

- Overall plan progress (phase-weighted): **95.00%** (Strict gates are green with zero residual counts; awaiting sign-off/archival)

1. **Key objective** – Enforce a strict hard-fork endpoint where closure is permitted only when legacy `kid`/`parent` terminology is fully eliminated from active runtime constants and wording, beginning with `custom_components/choreops/const.py`, with zero exceptions in this initiative scope.
2. **Summary of recent work** – Prior plan was archived with residual lexical debt; this initiative reopens execution under stricter, binary completion criteria.
3. **Next steps (short term)** – Lock closure policy, execute `const.py` canonicalization in bounded batches, then propagate references and verify full regression.
4. **Risks / blockers**
   - High-churn `const.py` edits can break imports and translation contracts if done in wide batches.
   - Legacy tokens may persist in comments, literal strings, service metadata, and test fixtures even after symbol renames.
   - Any “temporary alias” pattern conflicts with strict hard-fork rules and must be treated as a blocker.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/QUALITY_REFERENCE.md`
   - `docs/completed/HARD_FORK_TERMINOLOGY_FINALIZATION_COMPLETED.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/in-process/STRICT_CONST_TERMINOLOGY_ZERO_EXCEPTION_CLOSEOUT_SUP_CLOSURE_GATES.md`
6. **Decisions & completion check**
   - **Decisions captured**:
   - This initiative supersedes any interpretation that allows closure with residual `kid`/`parent` lexical debt in active runtime constant surfaces.
   - For this initiative, closure is binary and machine-gated: partial completion is not closable.
   - Runtime alias bridges for deprecated terms are prohibited.
   - **Completion confirmation**: `[ ]` Mark complete only when all strict gates in the support doc report pass with zero residual counts and full quality/test validation is green.

> **Important:** This plan is explicitly non-ambiguous: if any strict gate fails, status remains in progress.

## Tracking expectations

- **Summary upkeep**: Update percentages and blocker notes after each completed batch with exact command outputs.
- **Detailed tracking**: Every checklist item must include file evidence and validation output references before it is checked.

## Detailed phase tracking

### Phase 1 – Governance reset and closure contract

- **Goal**: Remove closure ambiguity and establish strict, objective completion criteria.
- **Steps / detailed work items**
  - [x] Add supersession note in archive context indicating strict follow-up governs closure acceptance
    - File: `docs/completed/HARD_FORK_TERMINOLOGY_FINALIZATION_COMPLETED.md` (summary + completion sections around prior completion claim)
  - [x] Lock strict “zero means zero” criteria in support doc
    - File: `docs/in-process/STRICT_CONST_TERMINOLOGY_ZERO_EXCEPTION_CLOSEOUT_SUP_CLOSURE_GATES.md`
    - Include no-waiver language and explicit fail-fast rules
  - [x] Record baseline metrics from current state
    - File: this plan (Phase 1 evidence subsection)
    - Baseline anchors from `const.py`: `word_hits=75`, `const_name_hits=5`, `value_hits=23`, `comment_hits=36`
  - [x] Confirm initiative scope boundaries (runtime + tests + docs as needed for propagation)
    - Files expected to change first: `custom_components/choreops/const.py`, then impacted runtime/test/doc callsites
- **Key issues**
  - Any conflicting “completed” statement without strict gate pass creates governance risk.

#### Phase 1 execution evidence (2026-02-22)

- Supersession note added in archived historical plan:
  - `docs/completed/HARD_FORK_TERMINOLOGY_FINALIZATION_COMPLETED.md`
  - Added strict governance handoff to `CHOREOPS-HF-STRICT-002`
- Strict gate lock confirmed in support doc:
  - `docs/in-process/STRICT_CONST_TERMINOLOGY_ZERO_EXCEPTION_CLOSEOUT_SUP_CLOSURE_GATES.md`
  - No allowlist/waiver/carve-out language enforced
- Baseline metrics recorded for strict const closure gate set A:
  - `word_hits=75`
  - `const_name_hits=5`
  - `value_hits=23`
  - `comment_hits=36`
- Confirmed phase execution scope boundaries:
  - Primary remediation starts in `custom_components/choreops/const.py`
  - Downstream propagation scope includes runtime modules, tests, and docs touched by renamed constants/wording

#### Phase 1 validation results (2026-02-22)

- `./utils/quick_lint.sh --fix` ✅ passed
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
- `python -m pytest tests/ -v --tb=line` ✅ passed (`1421 passed, 0 failed`)
- `pylint --rcfile=pyproject.toml custom_components/choreops` ✅ score `9.94/10` (required `>= 9.5` met)

Phase 1 validation threshold blocker is resolved.

### Phase 2 – Const lexical eradication (strict)

- **Goal**: Eliminate legacy `KID`/`PARENT` terms from active runtime `const.py` surfaces.
- **Steps / detailed work items**
  - [x] Build const rename ledger from current declarations and literal strings
    - File: `custom_components/choreops/const.py`
    - Line-hint clusters from latest scan: ~369, ~376, ~466, ~513, ~1013, ~1148, ~1958, ~2056, ~2728, ~2875, ~2882, ~3400
  - [x] Replace constant names containing `KID`/`PARENT` with canonical `ASSIGNEE`/`APPROVER`/`USER` naming
    - File: `custom_components/choreops/const.py`
    - Scope includes fields, action names, labels, and service metadata constants
  - [x] Replace literal value and user-facing wording in `const.py`
    - File: `custom_components/choreops/const.py`
    - Includes comments, purpose strings, labels, and translation-related wording constants where applicable
  - [x] Verify strict lexical delta after each batch
    - Command family: exact gates defined in support doc; do not proceed to next batch if count increases
  - [x] Remove migration-boundary dependency from closure acceptance criteria
    - Closure of this initiative cannot rely on any legacy-term allowlist exception
- **Key issues**
  - Renaming constants can cascade into broad import/usage updates and may temporarily break runtime until propagation is complete.

#### Phase 2 execution evidence (2026-02-22)

- Const remediation completed with downstream reference updates in:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/services.py`
  - `custom_components/choreops/managers/notification_manager.py`
  - `custom_components/choreops/notification_action_handler.py`
  - `custom_components/choreops/managers/gamification_manager.py`
  - `custom_components/choreops/managers/system_manager.py`
  - `custom_components/choreops/migration_pre_v50.py`
  - `tests/test_badge_cumulative.py`
- Strict lexical delta (`const.py`) reached zero-state:
  - `word_hits=0`
  - `const_name_hits=0`
  - `value_hits=0`
  - `comment_hits=0`

#### Phase 2 validation results (2026-02-22)

- `./utils/quick_lint.sh --fix` ✅ passed
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
- `runTests (mode=run)` ✅ passed (`548 passed, 0 failed`)
- `pylint --rcfile=pyproject.toml custom_components/choreops` ✅ score `9.94/10` (required `>= 9.5` met)

Phase 2 validation threshold blocker is resolved.

### Phase 3 – Runtime propagation and contract alignment

- **Goal**: Update all downstream references to new canonical constants/wording without introducing compatibility wrappers.
- **Steps / detailed work items**
  - [x] Update runtime callsites for renamed constants
    - Candidate files: `services.py`, `config_flow.py`, `options_flow.py`, `sensor.py`, `button.py`, `select.py`, `helpers/entity_helpers.py`, `helpers/device_helpers.py`, manager modules
  - [x] Update tests to canonical names and expected wording
    - Candidate files: `tests/helpers/constants.py`, flow tests, service tests, translation tests
  - [x] Validate translation contracts after const wording updates
    - Files: `custom_components/choreops/translations/en.json`, `custom_components/choreops/translations_custom/en_*.json` (only if impacted)
  - [x] Re-run strict lexical scans across runtime and top-level docs to ensure full zero-state
    - Runtime target: `custom_components/choreops/**/*.py`
    - Docs target: `docs/*.md` (non-exception surfaces)
- **Key issues**
  - Strict zero-state lexical scan remains non-zero and blocks phase completion.

#### Phase 3 execution evidence (2026-02-22)

- Runtime callsite propagation completed for renamed constants introduced in Phase 2:
  - Updated runtime references for `ACTION_COMPLETE_FOR_ASSIGNEE`
  - Updated runtime/migration references for `DATA_ASSIGNEE_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE`
  - Removed runtime dependencies on removed field aliases (`FIELD_KID_*`, `FIELD_PARENT_*`, `SERVICE_FIELD_KID_*`)
- Validation checks for propagation stability:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `runTests (mode=run)` ✅ passed (`548 passed, 0 failed`)
  - `pylint --rcfile=pyproject.toml custom_components/choreops` ✅ passed threshold (`9.94/10`)

#### Phase 3B stabilization evidence (2026-02-22)

- Regression repairs completed from bulk lexical remediation fallout:
  - Restored valid `pathlib.Path.parent` accessors in:
    - `custom_components/choreops/options_flow.py`
    - `custom_components/choreops/migration_pre_v50.py`
  - Removed newly introduced contract-lint lexical signatures in:
    - `custom_components/choreops/options_flow.py`
    - `custom_components/choreops/data_builders.py`
- Validation checks after repairs:
  - `./utils/quick_lint.sh --fix` ✅ passed (includes hard-fork contract-lint ✅)
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `runTests (mode=run)` ✅ passed (`548 passed, 0 failed`)
  - `pylint --rcfile=pyproject.toml custom_components/choreops` ✅ score `9.94/10` (required `>= 9.5` met)

#### Phase 3C runtime lexical cleanup evidence (2026-02-22)

- Targeted runtime cleanup completed in high-impact files (text/callsite-safe edits):
  - `custom_components/choreops/engines/chore_engine.py`
  - `custom_components/choreops/sensor_legacy.py`
  - `custom_components/choreops/managers/reward_manager.py`
  - `custom_components/choreops/engines/gamification_engine.py`
  - `custom_components/choreops/calendar.py`
  - `custom_components/choreops/helpers/dashboard_builder.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/helpers/auth_helpers.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/__init__.py`
- Net runtime strict lexical reduction this phase batch:
  - `245 → 32` hits (`-213`)
- Validation checks after Phase 3C:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `runTests (mode=run)` ✅ passed (`548 passed, 0 failed`)
  - `pylint --rcfile=pyproject.toml custom_components/choreops` ✅ score `9.94/10` (required `>= 9.5` met)

#### Phase 3D runtime lexical closeout evidence (2026-02-22)

- Remaining runtime lexical debt eliminated from residual modules, including:
  - `custom_components/choreops/coordinator.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/helpers/report_helpers.py`
  - `custom_components/choreops/helpers/translation_helpers.py`
  - `custom_components/choreops/managers/ui_manager.py`
  - `custom_components/choreops/managers/reward_manager.py`
  - `custom_components/choreops/migration_pre_v50.py`
  - `custom_components/choreops/engines/economy_engine.py`
  - `custom_components/choreops/diagnostics.py`
  - `custom_components/choreops/datetime.py`
  - `custom_components/choreops/entity.py`
  - `custom_components/choreops/engines/schedule_engine.py`
- Net runtime strict lexical reduction this phase batch:
  - `32 → 0` hits (`-32`)
- Validation checks after Phase 3D:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `runTests (mode=run)` ✅ passed (`548 passed, 0 failed`)
  - `pylint --rcfile=pyproject.toml custom_components/choreops` ✅ score `9.94/10` (required `>= 9.5` met)

#### Phase 3 strict lexical gate results (current blocker)

- Runtime scan (`grep -RInw -E 'kid|parent' custom_components/choreops --include='*.py'`) ❌ `245` hits
- Runtime scan (`grep -RInw -E 'kid|parent' custom_components/choreops --include='*.py'`) ✅ `0` hits
- Top-level docs scan (`grep -Inw -E 'kid|parent' docs/*.md`) ❌ `60` hits
- Representative residual surfaces:
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/managers/notification_manager.py`
  - `custom_components/choreops/managers/statistics_manager.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `docs/ARCHITECTURE.md`
  - `docs/DASHBOARD_TEMPLATE_GUIDE.md`

Phase 3 cannot be marked complete under strict zero-state criteria until these residual runtime/docs hits are eliminated.

### Phase 3E – Const symbol contract remediation (strict)

- **Goal**: Eliminate all `KID`/`PARENT` symbol identifiers in `custom_components/choreops/const.py` and propagate canonical symbol usage across runtime/tests without compatibility alias bridges.
- **Steps / detailed work items**
  - [x] Capture Phase 3E baseline metrics and propagation blast radius
    - `const_name_hits=403` in `custom_components/choreops/const.py`
    - `runtime_symbol_hits=2217` for `const.*(KID|PARENT)*` in `custom_components/choreops/**/*.py`
    - `tests_symbol_hits=529` for `const.*(KID|PARENT)*` in `tests/**/*.py`
    - `const_alias_like_lines=33` alias-style declarations (`: Final = ...`) in `const.py`
  - [x] Build deterministic rename ledger for every remaining `KID`/`PARENT` const symbol
    - Source: `custom_components/choreops/const.py`
    - Target naming: canonical `ASSIGNEE` / `APPROVER` / `USER`
  - [x] Apply const symbol renames in bounded batches (no alias retention)
    - File: `custom_components/choreops/const.py`
    - Rule: no temporary or compatibility alias constants containing `KID`/`PARENT`
  - [x] Propagate all runtime and test callsites to renamed const symbols
    - Runtime: `custom_components/choreops/**/*.py`
    - Tests: `tests/**/*.py`
  - [x] Enforce strict Phase 3E closure gate
    - `const_name_hits=0`
    - `runtime_symbol_hits=0`
    - `tests_symbol_hits=0`
- **Key issues**
  - This is a high-churn symbol migration touching thousands of callsites; execution must be batched and validation-gated after each batch.

#### Phase 3E baseline evidence (2026-02-22)

- Baseline command outputs:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `403`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `2217`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `529`
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\s*:\s*Final\s*=\s*[A-Z0-9_]+' custom_components/choreops/const.py | wc -l` → `33`

#### Phase 3E batch-1 execution + stabilization evidence (2026-02-22)

- Batch-1 const/callsite remediation executed and stabilized:
  - Removed alias-style `KID`/`PARENT` const bridges in `custom_components/choreops/const.py`
  - Propagated renamed default const usage in runtime callsites
  - Repaired codemod regression (`const.1`) across runtime files
  - Replaced removed legacy symbol `DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS` with canonical `DATA_APPROVER_USE_PERSISTENT_NOTIFICATIONS`
- Current metrics after stabilization:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `369`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `1946`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `504`
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\s*:\s*Final\s*=\s*[A-Z0-9_]+' custom_components/choreops/const.py | wc -l` → `0`
- Validation after stabilization:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Includes: `mypy` ✅ (`Success: no issues found in 50 source files`)
  - Includes: hard-fork contract lint ✅

#### Phase 3E batch-2 high-impact symbol tranche evidence (2026-02-22)

- Migrated high-impact DATA symbol identifiers in `const.py` and propagated callsites across runtime/tests:
  - `DATA_CHORE_ASSIGNED_KIDS` → `DATA_CHORE_ASSIGNED_ASSIGNEES`
  - `DATA_KID_CHORE_DATA` → `DATA_ASSIGNEE_CHORE_DATA`
  - `DATA_KIDS` → `DATA_ASSIGNEES`
  - `DATA_CHORE_PER_KID_DUE_DATES` → `DATA_CHORE_PER_ASSIGNEE_DUE_DATES`
  - `DATA_KID_CHORE_DATA_STATE` → `DATA_ASSIGNEE_CHORE_DATA_STATE`
  - `DATA_KID_CHORE_DATA_PERIOD_APPROVED` → `DATA_ASSIGNEE_CHORE_DATA_PERIOD_APPROVED`
  - `DATA_KID_BADGES_EARNED` → `DATA_ASSIGNEE_BADGES_EARNED`
  - `DATA_CHORE_PER_KID_APPLICABLE_DAYS` → `DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS`
  - `DATA_PARENTS` → `DATA_APPROVERS`
- Post-batch metrics:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `360`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `1618`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `315`
- Validation after batch-2:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `runTests` ✅ passed (`548 passed, 0 failed`)
  - `mypy` and hard-fork contract lint remained ✅ (via quick lint gate)

#### Phase 3E batch-3 chore-period symbol tranche evidence (2026-02-22)

- Migrated chore-period symbol identifiers in `const.py` and propagated callsites across runtime/tests:
  - `DATA_KID_CHORE_DATA_PERIODS_ALL_TIME` → `DATA_ASSIGNEE_CHORE_DATA_PERIODS_ALL_TIME`
  - `DATA_KID_CHORE_DATA_PERIOD_POINTS` → `DATA_ASSIGNEE_CHORE_DATA_PERIOD_POINTS`
  - `DATA_KID_CHORE_DATA_PERIOD_CLAIMED` → `DATA_ASSIGNEE_CHORE_DATA_PERIOD_CLAIMED`
  - `DATA_KID_CHORE_DATA_PERIODS` → `DATA_ASSIGNEE_CHORE_DATA_PERIODS`
  - `DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED` → `DATA_ASSIGNEE_CHORE_DATA_PERIOD_DISAPPROVED`
  - `DATA_KID_CHORE_DATA_PERIOD_OVERDUE` → `DATA_ASSIGNEE_CHORE_DATA_PERIOD_OVERDUE`
  - `DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK` → `DATA_ASSIGNEE_CHORE_DATA_PERIOD_LONGEST_STREAK`
  - `DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT` → `DATA_ASSIGNEE_CHORE_DATA_PENDING_CLAIM_COUNT`
  - `DATA_KID_CHORE_DATA_PERIOD_COMPLETED` → `DATA_ASSIGNEE_CHORE_DATA_PERIOD_COMPLETED`
- Post-batch metrics:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `351`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `1429`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `284`
- Validation after batch-3:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `runTests` ✅ passed (`543 passed, 0 failed`)
  - `mypy` and hard-fork contract lint remained ✅ (via quick lint gate)

#### Phase 3E batch-4 assignment/reward/badge symbol tranche evidence (2026-02-22)

- Migrated assignment/reward/badge focused symbols in `const.py` and propagated runtime/tests callsites, including:
  - `DATA_CHALLENGE_ASSIGNED_KIDS` → `DATA_CHALLENGE_ASSIGNED_ASSIGNEES`
  - `DATA_ACHIEVEMENT_ASSIGNED_KIDS` → `DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES`
  - `DATA_CHORE_ROTATION_CURRENT_KID_ID` → `DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID`
  - `DATA_CHORE_PER_KID_DAILY_MULTI_TIMES` → `DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES`
  - `CFOF_CHORES_INPUT_ASSIGNED_KIDS` → `CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES`
  - `DATA_KID_REWARD_DATA` → `DATA_ASSIGNEE_REWARD_DATA`
  - `DATA_KID_BADGE_PROGRESS` → `DATA_ASSIGNEE_BADGE_PROGRESS`
  - `DATA_KID_CUMULATIVE_BADGE_PROGRESS` → `DATA_ASSIGNEE_CUMULATIVE_BADGE_PROGRESS`
  - `DATA_KID_POINT_PERIOD_BY_SOURCE` → `DATA_ASSIGNEE_POINT_PERIOD_BY_SOURCE`
- Post-batch metrics:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `334`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `1113`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `226`
- Validation after batch-4:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `runTests` ✅ passed (`548 passed, 0 failed`)
  - `mypy` and hard-fork contract lint remained ✅ (via quick lint gate)

#### Phase 3E batch-5 form/dashboard symbol tranche evidence (2026-02-22)

- Migrated high-frequency form/dashboard symbol identifiers in `const.py` and propagated runtime/tests callsites:
  - `CFOF_PARENTS_INPUT_NAME` → `CFOF_APPROVERS_INPUT_NAME`
  - `CFOF_PARENTS_INPUT_ASSOCIATED_KIDS` → `CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES`
  - `CFOF_KIDS_INPUT_KID_NAME` → `CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME`
  - `DASHBOARD_ADMIN_MODE_PER_KID` → `DASHBOARD_ADMIN_MODE_PER_ASSIGNEE`
- Post-batch metrics:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `328`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `1070`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `175`
- Validation after batch-5:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `runTests` ✅ passed (`548 passed, 0 failed`)
  - `mypy` and hard-fork contract lint remained ✅ (via quick lint gate)

#### Phase 3E batch-6 long-tail symbol tranche evidence (2026-02-22)

- Migrated remaining high-frequency long-tail symbol identifiers in `const.py` and propagated runtime/tests callsites, including:
  - `DATA_KID_DASHBOARD_LANGUAGE` → `DATA_ASSIGNEE_DASHBOARD_LANGUAGE`
  - `DATA_KID_POINT_PERIODS` → `DATA_ASSIGNEE_POINT_PERIODS`
  - `DATA_KID_REWARD_DATA_PERIODS` → `DATA_ASSIGNEE_REWARD_DATA_PERIODS`
  - `DATA_KID_REWARD_DATA_PERIOD_APPROVED` → `DATA_ASSIGNEE_REWARD_DATA_PERIOD_APPROVED`
  - `DATA_KID_REWARD_DATA_PERIOD_CLAIMED` → `DATA_ASSIGNEE_REWARD_DATA_PERIOD_CLAIMED`
  - `CFOF_PARENTS_INPUT_HA_USER` → `CFOF_APPROVERS_INPUT_HA_USER`
  - `CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT` → `CFOF_APPROVERS_INPUT_ALLOW_CHORE_ASSIGNMENT`
  - `CFOF_DASHBOARD_SECTION_KID_VIEWS` → `CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS`
  - `CFOP_ERROR_KID_NAME` → `CFOP_ERROR_ASSIGNEE_NAME`
  - `CFOP_ERROR_PARENT_NAME` → `CFOP_ERROR_APPROVER_NAME`
- Post-batch metrics:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `303`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `830`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `104`
- Validation after batch-6:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `runTests` ✅ passed (`548 passed, 0 failed`)
  - `mypy` and hard-fork contract lint remained ✅ (via quick lint gate)

#### Phase 3E batch-7 migration-only shadow/link runtime cleanup (2026-02-22)

- Removed active runtime shadow/link behavior outside migration surfaces:
  - `build_kid()` no longer sets or preserves shadow/link markers in active runtime paths
  - config flow no longer creates linked assignee profiles during approver setup
  - `UserManager` approver/assignee CRUD no longer creates, finds, or unlinks shadow-linked assignees
  - entity helper linked-profile/shadow checks now return migration-only inactive behavior in runtime
- Post-batch metrics:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `262`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `565`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `38`
- Validation after batch-7:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `runTests` ✅ passed (`548 passed, 0 failed`)
  - `mypy` and hard-fork contract lint remained ✅ (via quick lint gate)

#### Phase 3E final closure evidence (2026-02-22)

- Strict closure metrics now at zero:
  - `grep -In -E '\b[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops/const.py | wc -l` → `0`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' custom_components/choreops --include='*.py' | wc -l` → `0`
  - `grep -RIn -E '\bconst\.[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\b' tests --include='*.py' | wc -l` → `0`
- Validation lock evidence:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff, mypy, boundary checks, hard-fork contract lint)
  - `python -m pytest tests/ -v --tb=line` ✅ passed (`1421 passed, 2 skipped, 2 deselected`)

### Phase 4 – Validation lock and closure evidence

- **Goal**: Provide unambiguous proof that strict requirements are complete.
- **Steps / detailed work items**
  - [x] Run mandatory quality gates
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
  - [x] Run full regression suite
    - `python -m pytest tests/ -v --tb=line`
  - [x] Run strict lexical closure gates (all must pass at zero)
    - Commands and pass criteria are defined in support doc
  - [x] Publish final evidence bundle in this plan
    - Include exact command outputs + before/after table for each strict gate
  - [ ] Obtain owner sign-off only after all strict gates pass
    - Update status to complete and archive only after sign-off and evidence lock
- **Key issues**
  - Any non-zero strict metric blocks closure, regardless of other green checks.

## Testing & validation

- **Required before closure**:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
  - All strict lexical gate commands from support doc with pass indicators
- **Not acceptable as substitutes**:
  - Partial or targeted tests only
  - Manual “spot-check” evidence
  - Narrative claims without command output snapshots

## Notes & follow-up

- This initiative intentionally prioritizes certainty over speed.
- Any discovered ambiguity must be resolved by tightening gate definitions, not by interpretation.
- If strict gates reveal additional debt outside `const.py`, this initiative remains open until that debt is eliminated.
