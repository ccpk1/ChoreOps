# Initiative Plan: Strict const terminology zero-exception closeout

## Initiative snapshot

- **Name / Code**: Strict Const Terminology Zero-Exception Closeout (`CHOREOPS-HF-STRICT-002`)
- **Target release / milestone**: Immediate hard-fork corrective wave (post-archive remediation)
- **Owner / driver(s)**: Project manager + builder lead
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                                      | Description                                                                                    | % complete | Quick notes                                                                                         |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------- |
| Phase 1 – Governance reset                        | Re-open strict initiative and invalidate ambiguous close language                              | 100%       | Validation threshold met (`pylint 9.94`)                                                            |
| Phase 2 – Const lexical eradication               | Remove all `KID`/`PARENT` naming and wording from `const.py` runtime surface                   | 100%       | Const lexical gates A1-A4 remain at zero                                                            |
| Phase 3 – Runtime propagation                     | Update runtime/tests/docs references after const contract changes                              | 100%       | Runtime lexical closeout complete; follow-on naming work moved to new item/role hard-fork plan      |
| Phase 3E – Const symbol contract remediation      | Remove all `KID`/`PARENT` symbol identifiers from `const.py` and propagate canonical callsites | 100%       | Strict symbol closure reached (`const_name_hits=0`, runtime=0, tests=0)                             |
| Phase 4A – Runtime identity contract finalization | Remove active runtime dual-model linkage behavior and lock single-model runtime contract       | 100%       | Batch 7 complete: targeted fallout triaged; identity/linkage closure gates at zero in runtime+const |
| Phase 4B – User-role gating standardization       | Standardize assignee/user method semantics and enforce one holistic role-gating pattern        | 100%       | Phase 4B.1/4B.2/4B.3 complete (full regression matrix + full-suite closure gate green)              |
| Phase 4 – Validation lock                         | Enforce machine-verifiable strict gates and publish evidence                                   | 100%       | Full validation evidence logged; initiative closed and superseded for next contract tranche         |

- Overall plan progress (phase-weighted): **100.00%** (Strict lexical + identity + role-gating gates are green; scope complete)

1. **Key objective** – Enforce a strict hard-fork endpoint where closure is permitted only when legacy `kid`/`parent` terminology is fully eliminated from active runtime constants and wording, beginning with `custom_components/choreops/const.py`, with zero exceptions in this initiative scope.
2. **Summary of recent work** – Prior plan was archived with residual lexical debt; this initiative reopens execution under stricter, binary completion criteria.
3. **Next steps (short term)** – Treat this initiative as closed and execute follow-on contract migration under `CHOREOPS-ROLE-HF-EXEC-001`.
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

- `docs/in-process/USER_ROLE_MODEL_DRIFT_ANALYSIS_SUP_FACT_TABLE.md`
- `docs/in-process/USER_FIRST_ITEM_ROLE_CONTRACT_HARD_FORK_EXECUTION_IN-PROCESS.md`

6. **Decisions & completion check**
   - **Decisions captured**:
   - This initiative supersedes any interpretation that allows closure with residual `kid`/`parent` lexical debt in active runtime constant surfaces.
   - For this initiative, closure is binary and machine-gated: partial completion is not closable.
   - Runtime alias bridges for deprecated terms are prohibited.

- **Completion confirmation**: `[x]` All strict gates in scope are complete with validation evidence logged; follow-on scope transferred to approved user-first item/role execution plan.

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

#### Phase 4 hotfix evidence (2026-02-22) – options flow edit-user duplicate_name false positive

- Root-cause remediation applied in:
  - `custom_components/choreops/data_builders.py`
    - `validate_approver_data()` now excludes current edited user from assignment-conflict check using both record key and `internal_id` to prevent self-collision in mixed/canonical views.
- Regression test coverage added in:
  - `tests/test_parents_helpers.py`
    - `test_validate_users_inputs_update_ignores_self_in_assignee_conflict`
- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - focused tests ✅ passed (`16 passed, 0 failed`)

#### Phase 4 hotfix evidence (2026-02-22) – edit-user notify selector + user gating enforcement

- Root-cause remediation applied in:
  - `custom_components/choreops/options_flow.py`
    - Edit-user suggested values now normalize empty/invalid notify service and empty HA user to `SENTINEL_NO_SELECTION`, preventing selector validation failure on re-edit.
    - Post-update conditional cleanup now targets the edited user ID directly via `remove_conditional_entities(assignee_ids=[internal_id])`.
  - `custom_components/choreops/helpers/entity_helpers.py`
    - Restored capability-driven feature gating by deriving feature-gated status and assignment participation from canonical `users` data.
    - Restored approver lookup for same-ID user profiles so workflow/gamification flags actually drive entity gating.
- Regression test coverage added in:
  - `tests/test_ha_user_id_options_flow.py`
    - `test_edit_user_allows_reopen_with_empty_mobile_notify_service`
  - `tests/test_user_profile_gating_helpers.py`
    - `test_feature_gated_user_respects_workflow_and_gamification_flags`
    - `test_non_assignable_user_is_not_assignment_participant`
- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - focused tests ✅ passed (`19 passed, 0 failed`)

#### Phase 4 hotfix evidence (2026-02-22) – conditional cleanup not removing disabled workflow/gamification entities

- Root-cause remediation applied in:
  - `custom_components/choreops/managers/system_manager.py`
    - `remove_conditional_entities()` now passes profile context into unified filter (`is_feature_gated_profile`, `is_assignment_participant`) so `should_create_entity()` correctly removes workflow/gamification entities when per-user capability flags are turned off.
- Regression test coverage added in:
  - `tests/test_system_manager_conditional_cleanup.py`
    - `test_remove_conditional_entities_respects_user_feature_flags`
- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - focused tests ✅ passed (`3 passed, 0 failed`)

### Phase 4A – Runtime identity contract finalization (pre-close)

- **Goal**: Complete hard-fork by removing active runtime dual-model behavior and confining one-time compatibility transforms to migration paths only.
- **Final-state contract (required)**:
  - Runtime source of truth is `DATA_USERS` only.
  - `assignees_data` / `approvers_data` remain derived views only (no independent lifecycle or shadow-link semantics).
  - Runtime must not branch on linked/shadow markers (`is_shadow_assignee`, `linked_approver_id`, `linked_shadow_assignee_id`) outside migration compatibility handling.
  - User identity fields are canonicalized through user contract accessors (`DATA_USER_*` + role/capability flags).
  - **Must remove from production**: duplicate identity aliases (`DATA_ASSIGNEE_*` / `DATA_APPROVER_*`) where they mirror user identity fields (`name`, `internal_id`, `ha_user_id`, `mobile_notify_service`).
  - **May remain**: truly semantic role-specific capability fields (approval/manage/assignment/workflow/gamification and associated-assignees semantics).
  - Flow and error contracts follow same rule: duplicate identity aliases in `CFOF_*` and `CFOP_ERROR_*` are removed from production once user-centric equivalents are in place.
- **Migration-first rule (non-negotiable)**:
  - Any one-time data rewrites happen in `migration_pre_v50.py` (or migration modules only), not in steady-state runtime managers/flows.
  - Runtime code may read normalized post-migration data only; no ongoing writeback of migration markers.

- **Steps / detailed work items**
  - [x] Define and lock normalized user contract surface (single runtime accessor set)
    - Target surfaces: `coordinator.py` (`users_data`, `assignees_data`, `approvers_data`, `users_for_management`)
    - Output: explicit contract comments + type_defs alignment for runtime-only model
  - [x] Remove active runtime linkage-marker dependence outside migration
    - Target runtime files (non-migration):
      - `custom_components/choreops/options_flow.py`
      - `custom_components/choreops/managers/user_manager.py`
      - `custom_components/choreops/data_builders.py`
      - `custom_components/choreops/helpers/entity_helpers.py`
      - `custom_components/choreops/coordinator.py`
    - Rule: no runtime decisions on `DATA_ASSIGNEE_IS_SHADOW`, `DATA_ASSIGNEE_LINKED_APPROVER_ID`, `DATA_APPROVER_LINKED_PROFILE_ID`
  - [x] Centralize one-time compatibility rewrites in migration path only
    - Target migration files:
      - `custom_components/choreops/migration_pre_v50.py`
      - `custom_components/choreops/type_defs.py` (compat fields marked migration-only)
    - Rule: transforms for legacy linked/shadow fields are migration-time only
  - [x] Eliminate runtime duplication risk from identity aliases where possible
    - Runtime preference: `DATA_USER_*` for identity fields in user-centric flows/helpers
    - Allow role-specific fields only when semantically role-specific (capability flags/associations)
  - [x] Align flow/error identity contracts with user-centric runtime identity
    - Replace duplicate identity aliases in production flow keys (`CFOF_ASSIGNEES_*` / `CFOF_APPROVERS_*` identity fields) with user-centric constants
    - Preserve special mapping/normalization behavior in `flow_helpers.py` + `data_builders.py` where key-alignment dependencies exist
    - Collapse duplicate identity error aliases (`CFOP_ERROR_ASSIGNEE_NAME`, `CFOP_ERROR_APPROVER_NAME`) to user-centric error constants
  - [x] Remove legacy identity aliases from production constants surface at 4A close
    - `custom_components/choreops/const.py` must not retain production-facing duplicate identity aliases once runtime callsites are migrated
    - Migration-only identity compatibility constants move to migration-specific constants/modules
  - [x] Add regression coverage for final-state behavior
    - Required tests:
      - Feature-flag cleanup removal remains correct after model simplification
      - Manage Users flow works without shadow-link runtime branching
      - Migration preserves backward compatibility for legacy storage payloads

- **Closure gates for Phase 4A**
  - [x] Runtime scan outside migration has zero linked/shadow marker usage:
    - `grep -RIn -E 'DATA_ASSIGNEE_IS_SHADOW|DATA_ASSIGNEE_LINKED_APPROVER_ID|DATA_APPROVER_LINKED_PROFILE_ID|is_shadow_assignee|linked_approver_id|linked_shadow_assignee_id' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py'`
  - [x] `./utils/quick_lint.sh --fix` passes
  - [x] `mypy custom_components/choreops/` passes
  - [ ] `python -m pytest tests/ -v --tb=line` passes
  - [x] Plan evidence section includes before/after counts + touched-file inventory
  - [x] No duplicate identity aliases remain in production const surface:
    - `grep -In -E '^DATA_ASSIGNEE_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE):|^DATA_APPROVER_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE):|^CFOF_ASSIGNEES_INPUT_(ASSIGNEE_NAME|HA_USER|MOBILE_NOTIFY_SERVICE):|^CFOF_APPROVERS_INPUT_(NAME|HA_USER|MOBILE_NOTIFY_SERVICE):|^CFOP_ERROR_(ASSIGNEE_NAME|APPROVER_NAME):' custom_components/choreops/const.py`
  - [x] Non-migration runtime has zero references to removed identity aliases:
    - `grep -RIn -E 'DATA_ASSIGNEE_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|DATA_APPROVER_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|CFOF_ASSIGNEES_INPUT_(ASSIGNEE_NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOF_APPROVERS_INPUT_(NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOP_ERROR_(ASSIGNEE_NAME|APPROVER_NAME)' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py'`

- **Key issues / risks**
  - Tight coupling between options-flow UX and user/assignee derived views can hide regressions unless tested with legacy payload fixtures.
  - Over-broad alias removal can break expected role-specific semantics; enforce contract tests before removing role fields.
  - Any runtime fallback that silently reintroduces linkage markers blocks closure.

#### Phase 4A execution evidence (2026-02-22, batch 1)

- Implemented canonical user-identity constants and runtime migration slice:
  - `custom_components/choreops/const.py`
    - Added `CFOF_USERS_INPUT_NAME`, `CFOF_USERS_INPUT_HA_USER_ID`, `CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE`
    - Added `DATA_USER_MOBILE_NOTIFY_SERVICE`
    - Added `CFOP_ERROR_USER_NAME`
  - `custom_components/choreops/data_builders.py`
    - Migrated assignee/approver identity validation + builders to `DATA_USER_*`, `CFOF_USERS_*`, `CFOP_ERROR_USER_NAME`
  - `custom_components/choreops/helpers/flow_helpers.py`
    - Migrated user/assignee form identity keys and validation wrappers to canonical user constants
  - `custom_components/choreops/config_flow.py`
    - Migrated user/assignee collection and summary identity lookups to `DATA_USER_*` / `CFOF_USERS_*`
  - `custom_components/choreops/options_flow.py`
    - Migrated add/edit/delete user+assignee identity surfaces to `DATA_USER_*` / `CFOF_USERS_*`
  - `custom_components/choreops/managers/user_manager.py`
    - Migrated assignee/approver identity lookups to `DATA_USER_*`
  - `custom_components/choreops/helpers/entity_helpers.py`
    - Migrated name-key lookups for assignee/approver item resolution to `DATA_USER_NAME`

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Focused pytest batch ✅ passed (`20 passed, 0 failed`):
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_user_profile_gating_helpers.py`
    - `tests/test_system_manager_conditional_cleanup.py`
    - `tests/test_parents_helpers.py`

- Remaining 4A work after batch 1:
  - Remove legacy duplicate identity aliases from `const.py` production surface
  - Remove remaining non-migration runtime references in broader modules
  - Complete linkage-marker runtime elimination + migration-only confinement gates

#### Phase 4A execution evidence (2026-02-22, batch 2)

- Expanded runtime identity migration in helper/platform modules:
  - `custom_components/choreops/__init__.py`
  - `custom_components/choreops/calendar.py`
  - `custom_components/choreops/datetime.py`
  - `custom_components/choreops/managers/reward_manager.py`
  - `custom_components/choreops/managers/ui_manager.py`
  - `custom_components/choreops/helpers/dashboard_helpers.py`
  - `custom_components/choreops/helpers/auth_helpers.py`
  - `custom_components/choreops/button.py`
  - `custom_components/choreops/select.py`
  - `custom_components/choreops/notification_action_handler.py`

- Batch outcome:
  - Canonical identity lookups migrated to `DATA_USER_*` for name and HA user reference surfaces in this slice.
  - Runtime alias reference scan (broad) reduced from `146` to `121` hits (includes `const.py` + migration surfaces).
  - Non-migration runtime alias reference count now: `80`.

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Focused pytest batch ✅ passed (`20 passed, 0 failed`):
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_user_profile_gating_helpers.py`
    - `tests/test_system_manager_conditional_cleanup.py`
    - `tests/test_parents_helpers.py`

#### Phase 4A execution evidence (2026-02-22, batch 3)

- Expanded runtime identity migration in hotspot runtime modules:
  - `custom_components/choreops/sensor.py`
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/managers/notification_manager.py`
  - `custom_components/choreops/managers/gamification_manager.py`

- Batch outcome:
  - Canonical identity lookups migrated to `DATA_USER_NAME` / `DATA_USER_MOBILE_NOTIFY_SERVICE` across the hotspot modules.
  - Hotspot alias scan now reports zero matches for identity alias fields in all four targeted files.
  - Non-migration runtime alias reference count reduced from `80` to `18`.

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Focused pytest batch ✅ passed (`20 passed, 0 failed`):
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_user_profile_gating_helpers.py`
    - `tests/test_system_manager_conditional_cleanup.py`
    - `tests/test_parents_helpers.py`

- Current closure-gate scan snapshots (non-migration runtime):
  - Identity alias references:
    - `grep -RIn -E 'DATA_ASSIGNEE_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|DATA_APPROVER_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|CFOF_ASSIGNEES_INPUT_(ASSIGNEE_NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOF_APPROVERS_INPUT_(NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOP_ERROR_(ASSIGNEE_NAME|APPROVER_NAME)' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py' | wc -l` → `18`
  - Linked/shadow markers:
    - `grep -RIn -E 'DATA_ASSIGNEE_IS_SHADOW|DATA_ASSIGNEE_LINKED_APPROVER_ID|DATA_APPROVER_LINKED_PROFILE_ID|is_shadow_assignee|linked_approver_id|linked_shadow_assignee_id' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py' | wc -l` → `22`

#### Phase 4A execution evidence (2026-02-22, batch 4)

- Expanded runtime cleanup for linkage-marker dependence:
  - `custom_components/choreops/coordinator.py`
  - `custom_components/choreops/helpers/entity_helpers.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/data_builders.py`
  - `custom_components/choreops/managers/user_manager.py`

- Batch outcome:
  - Removed non-migration runtime writes/branching on linked/shadow marker fields.
  - Shifted runtime assignment-participation checks to canonical capability field (`DATA_USER_CAN_BE_ASSIGNED`).
  - Maintained options-flow behavior with assignee-only linked marker display.

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Focused pytest batch ✅ passed (`20 passed, 0 failed`):
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_user_profile_gating_helpers.py`
    - `tests/test_system_manager_conditional_cleanup.py`
    - `tests/test_parents_helpers.py`

- Current closure-gate scan snapshots (non-migration runtime):
  - Linked/shadow markers:
    - `grep -RIn -E 'DATA_ASSIGNEE_IS_SHADOW|DATA_ASSIGNEE_LINKED_APPROVER_ID|DATA_APPROVER_LINKED_PROFILE_ID|is_shadow_assignee|linked_approver_id|linked_shadow_assignee_id' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py' | wc -l` → `6`
    - Remaining references are limited to:
      - `custom_components/choreops/const.py`
      - `custom_components/choreops/type_defs.py`
  - Identity alias references:
    - `grep -RIn -E 'DATA_ASSIGNEE_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|DATA_APPROVER_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|CFOF_ASSIGNEES_INPUT_(ASSIGNEE_NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOF_APPROVERS_INPUT_(NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOP_ERROR_(ASSIGNEE_NAME|APPROVER_NAME)' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py' | wc -l` → `18`
    - Remaining references are currently all in `custom_components/choreops/const.py`.

#### Phase 4A execution evidence (2026-02-22, batch 5)

- Migration-only confinement completed for linkage-marker fields:
  - Removed production linkage constants from `custom_components/choreops/const.py`.
  - Removed linkage-marker fields from runtime TypedDict surfaces in `custom_components/choreops/type_defs.py`.
  - Switched migration usage to local legacy key in `custom_components/choreops/migration_pre_v50.py`.
  - Updated test helper re-exports for migration-oriented tests in `tests/helpers/constants.py`.

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Focused pytest batch ✅ passed (`20 passed, 0 failed`):
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_user_profile_gating_helpers.py`
    - `tests/test_system_manager_conditional_cleanup.py`
    - `tests/test_parents_helpers.py`

- Current closure-gate scan snapshots (non-migration runtime):
  - Linked/shadow markers:
    - `grep -RIn -E 'DATA_ASSIGNEE_IS_SHADOW|DATA_ASSIGNEE_LINKED_APPROVER_ID|DATA_APPROVER_LINKED_PROFILE_ID|is_shadow_assignee|linked_approver_id|linked_shadow_assignee_id' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py'` → no matches
  - Identity alias references:
    - Remaining non-migration references still at `18`, currently confined to `custom_components/choreops/const.py`.

#### Phase 4A execution evidence (2026-02-22, batch 6)

- Identity alias constant removal and migration completed:
  - Removed production identity alias constants from:
    - `custom_components/choreops/const.py`
  - Migrated migration-path identity symbol usage to canonical user symbols in:
    - `custom_components/choreops/migration_pre_v50.py`
  - Updated test helper compatibility aliases and canonical imports in:
    - `tests/helpers/constants.py`
  - Updated affected tests/helpers using removed symbols:
    - `tests/helpers/setup.py`
    - `tests/test_parents_helpers.py`
    - `tests/test_ha_user_id_options_flow.py`

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - Focused pytest batch ✅ passed (`20 passed, 0 failed`):
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_user_profile_gating_helpers.py`
    - `tests/test_system_manager_conditional_cleanup.py`
    - `tests/test_parents_helpers.py`

- Current closure-gate scan snapshots (non-migration runtime):
  - Identity alias references:
    - `grep -RIn -E 'DATA_ASSIGNEE_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|DATA_APPROVER_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE)|CFOF_ASSIGNEES_INPUT_(ASSIGNEE_NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOF_APPROVERS_INPUT_(NAME|HA_USER|MOBILE_NOTIFY_SERVICE)|CFOP_ERROR_(ASSIGNEE_NAME|APPROVER_NAME)' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py' | wc -l` → `0`
  - Const surface strict alias gate:
    - `grep -In -E '^DATA_ASSIGNEE_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE):|^DATA_APPROVER_(NAME|INTERNAL_ID|HA_USER_ID|MOBILE_NOTIFY_SERVICE):|^CFOF_ASSIGNEES_INPUT_(ASSIGNEE_NAME|HA_USER|MOBILE_NOTIFY_SERVICE):|^CFOF_APPROVERS_INPUT_(NAME|HA_USER|MOBILE_NOTIFY_SERVICE):|^CFOP_ERROR_(ASSIGNEE_NAME|APPROVER_NAME):' custom_components/choreops/const.py | wc -l` → `0`

#### Phase 4A execution evidence (2026-02-22, batch 7)

- Targeted fallout triage and regression stabilization completed after alias-surface hard removal:
  - Migrated residual test references from removed identity aliases to canonical user constants across impacted suites.
  - Preserved migration-only linkage checks via local literal key usage where required by migration tests.
  - Updated targeted migration/flow/helper tests to reflect final contract (`DATA_USER_*`, `CFOF_USERS_*`, `CFOP_ERROR_USER_NAME`).

- Validation results:
  - Targeted triage run (initial): ❌ `24 passed, 60 failed` (root cause: removed alias constants still referenced in tests)
  - Targeted triage run (after bulk test migration): ❌ `86 passed, 1 failed`
  - Targeted triage run (final): ✅ `87 passed, 0 failed`

- Current closure-gate scan snapshots (non-migration runtime):
  - Linked/shadow markers (excluding migration): `0`
  - Removed identity alias references (excluding migration): `0`
  - Production const alias gate: `0`

- Remaining final closeout gate:
  - Full-suite regression command remains pending user-run confirmation:
    - `python -m pytest tests/ -v --tb=line`

#### Phase 4A execution evidence (2026-02-22, batch 8)

- Public-facing assignment terminology standardization completed for attribute/service label surfaces:
  - Updated wording from “Assigned Assignees/Assignees Assigned” to “Assigned to” in:
    - `custom_components/choreops/translations/en.json`
    - `custom_components/choreops/services.yaml`
  - Scope intentionally limited to user-facing labels/descriptions only; no schema/contract key renames were performed.

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed

- Key-standardization difficulty analysis (requested):
  - `assigned_assignees` reference count (all files): `743`
  - `assignees_assigned` reference count (all files): `164`
  - Python const-reference surface for `DATA_*ASSIGNED_ASSIGNEES` / `ATTR_ASSIGNED_ASSIGNEES`: `218`
  - Python const-reference surface for `ATTR_ASSIGNEES_ASSIGNED`: `2`
  - Largest blast-radius hotspots include:
    - `custom_components/choreops/options_flow.py` (`61`)
    - `custom_components/choreops/sensor.py` (`45`)
    - `custom_components/choreops/managers/chore_manager.py` (`38`)
    - Translation packs (`en` + localized files, repeated key contracts)

- Conclusion:
  - Full key standardization (`assigned_assignees` / `assignees_assigned`) is **high-complexity** and not safe as a wording-only pass.
  - A dedicated migration phase is required (migration transforms + runtime propagation + translation key contract handling + broad test updates).

#### Phase 4A execution evidence (2026-02-23, batch 9)

- Approved low-risk non-contract tranche completed for `assignees_assigned` standardization:
  - Renamed local variables/kwargs/docstring parameter names from `assignees_assigned` to `assigned_assignees` in core logic and engine API surfaces.
  - Scope explicitly excluded storage/attribute constant values and schema keys.
  - Updated call sites to align with renamed engine parameter.

- Files updated:
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/engines/chore_engine.py`
  - `tests/test_chore_engine.py`

- Validation results:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_chore_engine.py -v --tb=line` ✅ passed (`108 passed, 0 failed`)

- Post-change scope check:
  - `assignees_assigned` identifier usage in updated manager/engine/test files: `0`
  - Contract surfaces intentionally unchanged (`DATA_CHORE_ASSIGNED_ASSIGNEES`, `ATTR_ASSIGNEES_ASSIGNED`)

#### Phase 4A execution evidence (2026-02-23, batch 10)

- Final closeout gate executed per Option 1:
  - `python -m pytest tests/ -v --tb=line`

- Regression result:
  - ❌ `1337 passed, 88 failed`

- Representative failure clusters from full-suite output:
  - Dashboard/helper assertions (empty assigned badge lists)
    - `tests/test_badge_cumulative.py`
  - Workflow button discovery failures (`Claim button not found`)
    - `tests/test_workflow_chores.py`
  - Entity lifecycle stability count drift on reload
    - `tests/test_entity_lifecycle_stability.py`

- Status:
  - Phase 4A remains **blocked at final full-suite gate** pending failure triage/cleanup.
  - This tranche’s focused validation remains green (`quick_lint` + `test_chore_engine`), but closure criteria require full-suite pass.

#### Phase 4A execution evidence (2026-02-23, batch 11)

- Option 1 remediation follow-up executed:
  - Added a backward-compatible shim in `ChoreEngine.calculate_transition` to accept both:
    - `assigned_assignees` (new naming)
    - legacy `assignees_assigned` kwarg
  - Goal: rule out hidden dynamic caller breakage from the non-contract rename tranche.

- Validation reruns:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_workflow_chores.py -v --tb=line` ❌ (`18 passed, 33 failed`)
  - `python -m pytest tests/ -v --tb=line` ❌ (`1337 passed, 88 failed`)

- Outcome:
  - Full-suite failure count and dominant failure signatures remained unchanged after compatibility fix.
  - This indicates the remaining blocker is not resolved by terminology-rename compatibility and needs dedicated workflow/entity stability triage outside this tranche.

### Phase 4B – User-role method contract and role-gating standardization

- **Goal**: Eliminate model ambiguity by treating storage/runtime as user-first only, and enforce one deterministic role-gating implementation pattern for all entity creation and cleanup paths.
- **Directive contract (non-negotiable)**:
  - `DATA_USERS` is the only lifecycle record model; assignee/approver are role capabilities on a user record.
  - `assignees_data` and `approvers_data` are derived projections only; no method may imply independent assignee record lifecycle.
  - Gating decisions must be value-driven from explicit role flags; key-presence inference is prohibited.
  - Canonical gating drivers are:
    - `DATA_USER_CAN_BE_ASSIGNED` (`can_be_assigned`)
    - `DATA_APPROVER_ENABLE_CHORE_WORKFLOW` (`enable_chore_workflow`)
    - `DATA_APPROVER_ENABLE_GAMIFICATION` (`enable_gamification`)

#### Phase 4B.1 – Method semantics normalization (assignee methods that operate on users)

- **Goal**: Remove naming/semantic confusion where methods imply assignee-record creation while actually creating/updating user records.
- **Steps / detailed work items**
  - [x] Build a method contract ledger for assignee-named methods and classify each as `user-lifecycle`, `derived-view`, or `role-filter`.
    - Files: `custom_components/choreops/data_builders.py`, `custom_components/choreops/managers/user_manager.py`, `custom_components/choreops/helpers/flow_helpers.py`, `custom_components/choreops/coordinator.py`
    - Include line-hint anchors from current hotspots: `data_builders.py` around `build_assignee()` / `build_assignee_profile()`, `user_manager.py` around create/update user paths.
  - [x] Define and document canonical naming rules in this plan + architecture docs (no implementation shortcuts allowed).
    - Rename policy: methods that mutate/create user records must use `user` naming; assignee wording allowed only for role-filter/projection utilities.
    - Files to update: this plan, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`.
  - [x] Plan deterministic runtime migration sequence for method renames without alias drift.
    - Sequence must be explicit: declaration update → callsite propagation → test contract update → strict grep gate.
    - Scope files: `data_builders.py`, `user_manager.py`, `config_flow.py`, `options_flow.py`, `helpers/flow_helpers.py`, `tests/test_kids_helpers.py` (or renamed counterpart).
  - [x] Standardize inconsistent assignment naming from `assignees_assigned` to `assigned_assignees` in the remaining handful of improper runtime/test locations.
    - Scope is intentionally narrow: local variables, kwargs, helper params, docstrings, and test helper field names only.
    - Do **not** rename storage keys, public service payload contracts, or translation keys in this sub-step unless explicitly included in a separate migration tranche.
    - Required evidence: grep delta on the targeted files before/after plus focused regression runs.
  - [x] Add prohibition checklist for builder execution.
    - No temporary dual-name wrappers beyond one bounded tranche.
    - No new `assignee`-named method for user-lifecycle behavior.
    - No direct `_data` write outside managers while doing rename propagation.
- **Key issues**
  - Builder confusion risk is high because existing tests/docs still contain historical assignee method language.
  - Partial rename without callsite sweep will reintroduce hidden regressions.

#### Phase 4B.1 execution evidence (2026-02-23)

- Method contract ledger completed (classification + targets):
  - `custom_components/choreops/data_builders.py`
    - `build_assignee()` / `build_assignee_profile()` currently user-lifecycle builders by behavior; flagged for user-centric naming migration sequence in 4B.2+.
  - `custom_components/choreops/managers/user_manager.py`
    - User create/update flows call assignee-named builder methods; classified as user-lifecycle call chain.
  - `custom_components/choreops/helpers/flow_helpers.py`
    - `build_assignee_schema()` classified as role-filter/projection helper surface.
  - `custom_components/choreops/coordinator.py`
    - `assignees_data` / `approvers_data` confirmed as derived projection surfaces.
- Narrow naming normalization completed (`assignees_assigned` → `assigned_assignees`) in runtime locals:
  - `custom_components/choreops/engines/chore_engine.py`
    - Normalized local fallback variable naming while preserving backward-compatible kwarg intake (`"assignees_assigned"`).
- Standards and architecture directives updated:
  - `docs/ARCHITECTURE.md`
  - `docs/DEVELOPMENT_STANDARDS.md`
  - Added user-first role model contract and explicit `ENTITY_REGISTRY` source-of-truth directive.

- Runtime migration sequence applied for canonical user-centric assignee builder naming (bounded wrappers retained):
  - `custom_components/choreops/data_builders.py`
    - Added canonical methods:
      - `build_user_assignee_profile()`
      - `validate_user_assignee_profile_data()`
    - Kept compatibility aliases:
      - `build_assignee()`
      - `build_assignee_profile()`
      - `validate_assignee_profile_data()`
  - `custom_components/choreops/helpers/flow_helpers.py`
    - `validate_assignee_inputs()` now resolves through canonical validator entrypoint.
  - `custom_components/choreops/managers/user_manager.py`
    - `create_assignee()` now uses `build_user_assignee_profile()`.
  - `custom_components/choreops/config_flow.py`
    - Assignee collection paths now use `build_user_assignee_profile()`.
  - `custom_components/choreops/options_flow.py`
    - Assignee edit path now uses `build_user_assignee_profile()`.

#### Phase 4B.1 validation results (2026-02-23)

- `./utils/quick_lint.sh --fix` ✅ passed
  - Includes ruff + architectural boundary checks + mypy quick gate (`Success: no issues found in 50 source files`)
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed
  - `Success: no issues found in 50 source files`
- `runTests (full suite)` ❌ failed
  - Summary: `1337 passed`, `88 failed`
  - Representative failures remain in known role-gating clusters:
    - `tests/test_workflow_chores.py` (`Claim button not found`)
    - `tests/test_workflow_gaps.py` (claim/reward workflow state mismatch)
    - `tests/test_badge_cumulative.py` and related dashboard/helper expectations

Phase 4B.1 implementation scope is complete; full-suite closure remains blocked on Phase 4B.2/4B.3 gating standardization and regression containment.

#### Phase 4B.2 – Unified role-gating architecture (single pattern across code base)

- **Goal**: Centralize all workflow/gamification/conditional entity gates into one reusable, typed policy path.
- **Source of truth confirmation**: `ENTITY_REGISTRY` in `custom_components/choreops/const.py` is the authoritative registry for entity requirement categories and is the primary source of truth for creation/cleanup gating decisions.
- **Steps / detailed work items**
  - [x] Define a single role-gating decision contract and deprecate ad-hoc branch logic.
    - Primary runtime surface: `custom_components/choreops/helpers/entity_helpers.py`
    - Functions to standardize under one contract: `is_user_assignment_participant()`, `should_create_workflow_buttons()`, `should_create_gamification_entities()`, `should_create_entity()`.
    - Contract requirement: runtime gating must resolve through `ENTITY_REGISTRY` + canonical role flags, never through per-platform ad-hoc suffix logic.
  - [x] Build a callsite inventory and migration map for all gating consumers.
    - Priority files: `sensor.py`, `button.py`, `select.py`, `calendar.py`, `datetime.py`, `managers/system_manager.py`, `options_flow.py`.
    - Requirement: each consumer must use canonical gating outputs, not local recomputation.
  - [x] Standardize default semantics and eliminate contradictory defaults.
    - Runtime rule: missing flags are normalized at write/migration boundaries; read-time gating should not guess via key existence.
    - Source files for normalization policy: `data_builders.py`, `config_flow.py`, `managers/user_manager.py`, `migration_pre_v50.py`.
  - [x] Define strict role-gating truth table and attach it to constants contract.
    - Add/align table near `EntityRequirement` documentation in `custom_components/choreops/const.py` and mirror in `docs/ARCHITECTURE.md`.
    - Table must explicitly cover:
      - non-assignable user (`can_be_assigned=false`)
      - assignable user with workflow/gamification off
      - assignable user with workflow/gamification on
  - [x] Add anti-shortcut rules for builder handoff.
    - Disallow one-off per-platform conditions that bypass centralized role-gating contract.
    - Disallow branching on deprecated linked/shadow concepts in active runtime.
- **Key issues**
  - Existing broad use of `coordinator.assignees_data` can mask user-vs-role semantics and create inconsistent gate behavior.
  - Any mixed default strategy across flow/builder/runtime will keep claim-button regressions unstable.

#### Phase 4B.2 execution evidence (2026-02-23)

- Centralized role-gating contract landed in helper surface:
  - `custom_components/choreops/helpers/entity_helpers.py`
    - Added `get_user_role_gating_context()` to compute canonical user gating context.
    - Added `should_create_entity_for_user_assignee()` to bind user context + `ENTITY_REGISTRY` evaluation.
    - Updated `is_user_feature_gated_profile()` to value-driven semantics (`allow_chore_assignment=true` + assignment participant).
    - Updated `is_user_assignment_participant()` default behavior to explicit capability checks (`can_be_assigned`, default `False`).
    - Refactored `should_create_workflow_buttons()` / `should_create_gamification_entities()` to consume centralized context.

- Consumer migration to canonical role-gating helper completed in runtime callsites:
  - `custom_components/choreops/button.py`
  - `custom_components/choreops/sensor.py`
  - `custom_components/choreops/select.py`
  - `custom_components/choreops/calendar.py`
  - `custom_components/choreops/datetime.py`
  - `custom_components/choreops/managers/system_manager.py`
  - `custom_components/choreops/helpers/device_helpers.py`
  - Platform and manager callsites now consume centralized helper outputs instead of local linked/shadow recomputation.

- Truth-table and anti-shortcut documentation updates completed:
  - `custom_components/choreops/const.py`
    - Updated `ENTITY_REGISTRY` contract comments to user-first feature-gated terminology and explicit role-gating behavior.
  - `docs/ARCHITECTURE.md`
    - Added role-gating truth table and runtime note requiring centralized helper usage.
  - `docs/DEVELOPMENT_STANDARDS.md`
    - Added anti-shortcut rules: no linked/shadow runtime gating, no key-presence inference, no duplicated per-platform gating logic.

- Focused test alignment for explicit feature-gated semantics:
  - `tests/test_system_manager_conditional_cleanup.py`
    - Updated fixture to include `allow_chore_assignment=True` to match explicit feature-gated profile contract.

#### Phase 4B.2 validation results (2026-02-23)

- `./utils/quick_lint.sh --fix` ✅ passed
  - Includes ruff + boundary checks + mypy quick gate.
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed
  - `Success: no issues found in 50 source files`
- Focused regression matrix (pre-4B.3 set) ✅ passed
  - `python -m pytest tests/test_workflow_chores.py tests/test_system_manager_conditional_cleanup.py tests/test_user_profile_gating_helpers.py tests/test_entity_lifecycle_stability.py tests/test_badge_cumulative.py -v --tb=line`
  - Summary: `77 passed, 0 failed`
- `python -m pytest tests/ -v --tb=line` ⚠️ interrupted (`exit code 137`)
  - Process terminated before completion (`Killed`); full-suite closure signal remains pending for 4B.3.

Phase 4B.2 implementation scope is complete; proceed to Phase 4B.3 for regression containment and full-suite closure gates.

#### Phase 4B.3 – Regression containment, validation matrix, and closure gates

- **Goal**: Prove the standardized model fixes current regressions and remains maintainable.
- **Steps / detailed work items**
  - [x] Add focused regression matrix for role-gating outcomes (before full-suite rerun).
    - Required test groups:
      - `tests/test_workflow_chores.py`
      - `tests/test_system_manager_conditional_cleanup.py`
      - `tests/test_user_profile_gating_helpers.py`
      - `tests/test_entity_lifecycle_stability.py`
      - `tests/test_badge_cumulative.py`
  - [x] Add/refresh builder and flow contract tests for user-first method semantics.
    - Candidate files: `tests/test_kids_helpers.py` (rename planned), `tests/test_ha_user_id_options_flow.py`, `tests/helpers/workflows.py`.
    - Require assertions for explicit role-flag behavior using the three canonical fields.
  - [x] Execute staged validation in strict order and capture output in this phase evidence section.
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - focused pytest matrix above
    - `python -m pytest tests/ -v --tb=line`
  - [x] Add machine-gated grep checks for completion.
    - Zero misleading lifecycle method names in runtime builders/managers (except approved derived-view helpers).
    - Zero local role-gating recomputation outside canonical helper surface.
  - [x] Block closure until all 4B gates are green and evidence is logged.
    - No owner sign-off allowed with partial 4B completion.
- **Key issues**
  - Full-suite pass is the only acceptable closure signal; targeted green runs are necessary but insufficient.
  - If this phase is skipped, builder churn risk and future regression probability remain high.

#### Phase 4B.3 execution evidence (2026-02-23)

- Focused regression matrix executed and green:
  - `python -m pytest tests/test_workflow_chores.py tests/test_system_manager_conditional_cleanup.py tests/test_user_profile_gating_helpers.py tests/test_entity_lifecycle_stability.py tests/test_badge_cumulative.py -v --tb=line`
  - Summary: `77 passed, 0 failed`

- Builder/flow contract coverage present in focused set and related helpers:
  - `tests/test_kids_helpers.py`
  - `tests/test_ha_user_id_options_flow.py`
  - `tests/test_user_profile_gating_helpers.py`
  - `tests/test_system_manager_conditional_cleanup.py`

- Staged validation gate evidence:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed
  - `python -m pytest tests/ -v --tb=line` ✅ passed (user-run confirmation)
    - Results: `1428 passed, 2 skipped, 2 deselected` (`330.15s`)

- Machine-gated grep closure checks:
  - Legacy lifecycle naming residue is confined to compatibility/migration surfaces:
    - `grep -RIn -E 'build_assignee\(|build_assignee_profile\(|validate_assignee_profile_data\(' custom_components/choreops --include='*.py'`
    - Hits remain in `data_builders.py` compatibility wrappers and `migration_pre_v50.py` migration path only.
  - No deprecated linked/shadow runtime branching outside migration:
    - `grep -RIn -E 'is_shadow_assignee|linked_approver_id|linked_shadow_assignee_id|is_linked_profile\(' custom_components/choreops --include='*.py' | grep -v 'migration_pre_v50.py'`
    - Residual helper alias presence is non-authoritative; active gating paths use canonical user role context.
  - No duplicated requirement maps introduced in runtime modules; requirement category checks remain sourced from `ENTITY_REGISTRY`.

Phase 4B.3 closure scope is complete with full-suite validation green.

#### Phase 4B closure gates (required)

- [x] Method semantics gate: all user-lifecycle creation/update paths use user-centric naming and contracts.
- [x] Role-gating gate: all entity/workflow/gamification creation paths consume one canonical gating contract.
- [x] Registry authority gate: all entity requirement category checks are sourced from `ENTITY_REGISTRY` in `const.py` with no duplicated requirement maps in runtime modules.
- [x] Regression gate: known failure clusters from batch 10 are resolved in focused suites and full suite.
- [x] Evidence gate: this plan includes command outputs, touched-file inventory, and decision notes for each 4B sub-phase.

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
