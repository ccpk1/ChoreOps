# Initiative Plan: Fix Periodic Badge Date Clearing (Issue #237)

## Initiative snapshot

- **Name / Code**: `ISSUE-237_BADGE-DATE-CLEARING`
- **Target release / milestone**: v1.5.2 or v1.6.0
- **Owner / driver(s)**: ChoreOps Maintainer
- **Status**: Implementation complete — pending review

## Summary & immediate steps

| Phase / Step                          | Description                                              | % complete | Quick notes                                      |
| ------------------------------------- | -------------------------------------------------------- | ---------- | ------------------------------------------------ |
| Phase 1 – Bug Fix: START_DATE flush   | Remove START_DATE from non-custom force-clear in validation | 100%       | Done — flow_helpers.py                           |
| Phase 2 – UI: Clear date checkboxes   | Add clear_start_date / clear_end_date affordance to badge edit form | 100%    | Done — const/schema/validation/translations      |
| Phase 3 – Testing & validation        | Unit tests for fix + clear flow, regression guard        | 100%        | 8 tests in test_badge_date_clearing.py           |
| Phase 4 – Quality gates & polish      | Lint, mypy, translations, final review                   | 100%       | Full suite green (1966 passed)                   |

1. **Key objective** – Fix two related bugs: (a) `start_date` is incorrectly force-cleared when editing a periodic badge with non-custom frequency, and (b) neither `start_date` nor `end_date` can be cleared from the badge edit UI once set.
2. **Summary of recent work** – Issue #237 reported 2026-08-13 by @geobrando with detailed root-cause analysis. Analysis confirmed accurate against `main` (commit 1bf764b).
3. **Next steps (short term)** – Implementation is complete. Next: code review, then decide on commit/PR. Phase 4 full suite: 1966 passed, 4 skipped, 18 deselected (no failures).
4. **Risks / blockers** – None. Both code paths are unchanged between v1.5.0 and main. No schema migration needed (storage format unchanged).
5. **References**:
   - Issue: https://github.com/ccpk1/ChoreOps/issues/237
   - `docs/ARCHITECTURE.md` – Data model, storage schema
   - `docs/DEVELOPMENT_STANDARDS.md` – Constants, translations, logging standards
   - `docs/CODE_REVIEW_GUIDE.md` – Phase 0 audit framework
   - `tests/AGENT_TESTING_USAGE_GUIDE.md` – Test validation patterns
6. **Decisions & completion check**
   - **Decisions captured**:
     - `start_date` is a cycle-window field (not custom-only) — confirmed by `gamification_manager.py:1649` writing it during cycle rollover
     - Clear checkboxes follow the existing chore `clear_due_date` pattern (BooleanSelector, always in schema, handled in validation)
     - Two separate clear toggles (`clear_start_date`, `clear_end_date`) rather than one combined toggle — because the two dates have different semantics (start = cycle anchor, end = stop/cycle boundary)
     - Clear checkboxes appear in both ADD and EDIT forms (consistent with chore `clear_due_date` pattern), though they're only functional in EDIT mode
     - No `data_builders.py` changes needed — `build_badge()` already handles `None` for dates via `None if start_date in (None, "") else start_date`
   - **Completion confirmation**: `[x]` All follow-up items completed before marking done.

## Detailed phase tracking

### Phase 1 – Bug Fix: Remove START_DATE from non-custom force-clear

- **Goal**: Fix the root cause of Problem 2 — `start_date` is incorrectly cleared when editing a badge with any non-custom recurring frequency.
- **Steps / detailed work items**
  1. `[x]` **`helpers/flow_helpers.py` ~line 2657**: In `validate_badge_common_inputs()`, remove `CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE: const.SENTINEL_NONE` from the `user_input.update()` block that fires when `recurring_frequency != const.FREQUENCY_CUSTOM`. Keep only `CUSTOM_INTERVAL` and `CUSTOM_INTERVAL_UNIT` in that block. Update the comment to reflect the corrected intent.
  2. `[x]` **Verify no other force-clear of START_DATE**: Search codebase for any other location that sets `START_DATE` to `SENTINEL_NONE` outside of custom-frequency logic. (Confirmed: only this one location.)
  3. `[x]` **Run quick_lint.sh + mypy**: Verify no regressions from the removal.
- **Key issues**
  - The existing comment `# Note: END_DATE not cleared - can be used as reference date` was already asymmetric — it acknowledged END_DATE should survive but grouped START_DATE with custom-only fields. The fix makes the code match the comment's intent for both date fields.

### Phase 2 – UI: Add clear date checkboxes to badge edit form

- **Goal**: Provide a UI affordance to clear `start_date` and `end_date` on badge edit forms, mirroring the existing chore `clear_due_date` pattern.
- **Steps / detailed work items**

  1. `[x]` **`const.py`**: Add two new CFOF constants:
     - `CFOF_BADGES_INPUT_CLEAR_START_DATE: Final = "clear_start_date"` (in the `# BADGES` section, near line 714)
     - `CFOF_BADGES_INPUT_CLEAR_END_DATE: Final = "clear_end_date"` (in the `# BADGES` section, near line 699)

  2. `[x]` **`helpers/flow_helpers.py` — `build_badge_common_schema()`**: Add two `BooleanSelector` fields to the reset schedule schema section (after the existing date selectors, before grace period):
     - `vol.Optional(CFOF_BADGES_INPUT_CLEAR_START_DATE, default=False): selector.BooleanSelector()` — only when `is_periodic` (since start_date is only in schema for periodic badges)
     - `vol.Optional(CFOF_BADGES_INPUT_CLEAR_END_DATE, default=False): selector.BooleanSelector()` — for all non-daily reset_schedule types (periodic, cumulative, special occasion)
     - Pattern reference: `flow_helpers.py` line ~976 (`_optional_field(CFOF_CHORES_INPUT_CLEAR_DUE_DATE, False): selector.BooleanSelector()`)

  3. `[x]` **`helpers/flow_helpers.py` — `validate_badge_common_inputs()`**: Add clear-checkbox handling in the reset component validation section. The current code order is: (a) read `recurring_frequency`, (b) force-clear block (`if recurring_frequency != FREQUENCY_CUSTOM`), (c) read `start_date`/`end_date`. Insert the clear-checkbox handling immediately AFTER reading `recurring_frequency` and BEFORE the force-clear block (~line 2653, right after the `recurring_frequency = user_input.get(...)` assignment):
     ```python
     recurring_frequency = user_input.get(
         const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY,
         const.DEFAULT_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
     )

     # Handle clear date checkboxes (UI affordance — date selectors can't be emptied)
     if user_input.get(const.CFOF_BADGES_INPUT_CLEAR_START_DATE, False):
         user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] = None
     if user_input.get(const.CFOF_BADGES_INPUT_CLEAR_END_DATE, False):
         user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] = None

     # Clear custom interval fields if not custom
     if recurring_frequency != const.FREQUENCY_CUSTOM:
         ...
     ```
     - Placement rationale: Phase 1 removes `START_DATE` from the force-clear block, so the force-clear no longer touches any date field. Placing the clear-checkbox handling before it guarantees the user's explicit clear intent is applied, then the (now date-agnostic) force-clear only clears the custom-interval fields. The subsequent `start_date = user_input.get(...)` / `end_date = user_input.get(...)` reads will correctly pick up the `None` values.
     - For special occasion badges: if end_date is cleared, the existing `if is_special_occasion: user_input[START_DATE] = user_input.get(END_DATE)` at the end of validation will naturally set start_date to None as well — correct behavior.

  4. `[x]` **`translations/en.json`**: Add translation entries for the new fields. The clear checkbox fields need labels and descriptions in the sections where the corresponding date field exists **in the schema** (not in translation):
     - `add_badge_periodic` → `data.clear_start_date`, `data.clear_end_date`, `data_description.clear_start_date`, `data_description.clear_end_date`
     - `edit_badge_periodic` → same
     - `add_badge_cumulative` → `data.clear_end_date`, `data_description.clear_end_date` (cumulative has end_date in schema; NOT clear_start_date — see reverse-verification note)
     - `edit_badge_cumulative` → same
     - `add_badge_special` → `data.clear_end_date`, `data_description.clear_end_date` (special occasion has end_date; start_date is forced in validation, not in schema)
     - `edit_badge_special` → same
     - ⚠️ Do NOT add `clear_start_date` to cumulative translations — the cumulative schema only adds `start_date` when `is_periodic`; the cumulative `start_date` translation key is a pre-existing artifact that's never rendered.
     - Label pattern (follow chore `clear_due_date` style): `"clear_start_date": "🗑️ Clear Start Date"`, `"clear_end_date": "🗑️ Clear End Date"`
     - Description pattern: `"clear_start_date": "Check this box to remove the start date from this badge."`, `"clear_end_date": "Check this box to remove the end date from this badge."`

  5. `[x]` **Verify `data_builders.py` needs no changes**: `build_badge()` lines 2360-2378 already handle `None` for dates: `start_date = None if start_date in (None, "") else start_date`. When validation sets the date to `None` (via clear checkbox), `build_badge()` will store it as `null`. Confirmed: no changes needed.

  6. `[x]` **Verify `config_flow.py` compatibility**: `async_add_badge_common()` in config_flow also calls `validate_badge_common_inputs()` and `build_badge()`. The clear checkbox fields will be in the schema but are harmless in ADD mode (default=False, no existing dates to clear). Confirmed: no changes needed.

  7. `[x]` **Verify `options_flow.py` compatibility**: `async_add_edit_badge_common()` calls `build_badge_common_schema()` then applies suggested values. The clear checkbox fields will be in the schema. In EDIT mode, suggested values will populate existing dates; the clear checkboxes default to False. Confirmed: no changes needed in options_flow.py.

- **Key issues**
  - **Nuance: cumulative badges have end_date but not start_date in schema**. The `build_badge_common_schema()` only adds `start_date` when `is_periodic` is True (line ~2326). Cumulative badges get `end_date` (for maintenance cycle end) but not `start_date`. So `clear_start_date` should only be added when `is_periodic`, while `clear_end_date` should be added for all non-daily reset_schedule types.
  - **Nuance: special occasion badges**. Special occasion has `end_date` in schema. `start_date` is forced to equal `end_date` in validation (line ~2704), not exposed in schema. So only `clear_end_date` is needed for special occasion. Clearing end_date will cascade to start_date via the existing validation logic.
  - **Nuance: daily badges**. Daily badges have `include_reset_schedule` but the schema hides all reset schedule fields (`if not is_daily:` guard at line ~2270). So no clear checkboxes needed for daily badges.
  - **Translation scope**: 6 form sections × 2 fields (label + description) = up to 24 new translation entries. Cumulative and special occasion only need `clear_end_date` (not `clear_start_date`), reducing the actual count.

### Phase 3 – Testing & validation

- **Goal**: Ensure the fix works correctly and doesn't regress existing behavior.
- **Steps / detailed work items**

  1. `[x]` **Test: Phase 1 fix — start_date preserved on non-custom frequency edit**
     - Create a periodic badge with `recurring_frequency=weekly`, `start_date="2026-08-12"`, `end_date="2026-08-24"`
     - Edit the badge (change name only, keep frequency=weekly)
     - Verify `start_date` is still `"2026-08-12"` in storage (not null)
     - Test file: `tests/test_badge_target_types.py` (alongside existing periodic badge tests)

  2. `[x]` **Test: Phase 1 fix — start_date preserved when changing between non-custom frequencies**
     - Create periodic badge with `frequency=weekly`, `start_date="2026-08-12"`
     - Edit to `frequency=monthly`
     - Verify `start_date` preserved

  3. `[x]` **Test: Phase 2 — clear_start_date checkbox clears the date**
     - Create periodic badge with `start_date="2026-08-12"`
     - Edit badge, check `clear_start_date=True`
     - Verify `start_date` is `null` in storage

  4. `[x]` **Test: Phase 2 — clear_end_date checkbox clears the date**
     - Create periodic badge with `end_date="2026-08-24"`
     - Edit badge, check `clear_end_date=True`
     - Verify `end_date` is `null` in storage

  5. `[x]` **Test: Phase 2 — clear checkboxes don't affect other fields**
     - Create periodic badge with both dates set, plus awards, target, etc.
     - Edit badge, check both clear checkboxes, change award_points
     - Verify dates are null, award_points updated, all other fields preserved

  6. `[x]` **Test: Phase 2 — cumulative badge clear_end_date**
     - Create cumulative badge with `end_date="2026-12-31"`
     - Edit badge, check `clear_end_date=True`
     - Verify `end_date` is `null` in storage

  7. `[x]` **Test: Regression — custom frequency still requires dates**
     - Create periodic badge with `frequency=custom`, no dates → should fail validation
     - Existing behavior must be preserved

  8. `[x]` **Test: Regression — special occasion clear_end_date cascades to start_date**
     - Create special occasion badge with `end_date="2026-12-25"`
     - Edit badge, check `clear_end_date=True`
     - Verify both `start_date` and `end_date` are `null` (special occasion forces start=end)

  9. `[x]` **Run full test suite**: `python -m pytest tests/ -v --tb=line` (all existing tests must pass)

- **Key issues**
  - Test patterns: Use `add_badge_via_options_flow()` helper from `test_badge_target_types.py` for creating badges. For edit flow, follow the `test_options_flow_entity_crud.py` pattern (navigate to menu → select edit → select entity → submit form).
  - The `FlowTestHelper.navigate_to_entity_menu()` pattern from `test_options_flow_entity_crud.py` line ~592 can be adapted for badge edit tests.

### Phase 4 – Quality gates & polish

- **Goal**: Ensure all quality gates pass and the fix is ready for merge.
- **Steps / detailed work items**
  1. `[x]` **Run quick_lint.sh**: `./utils/quick_lint.sh --fix` (ruff check/format + mypy + boundary checks)
  2. `[x]` **Run mypy separately**: `mypy custom_components/choreops/` (zero errors required)
  3. `[x]` **Run full test suite**: `python -m pytest tests/ -v --tb=line` (all tests pass)
  4. `[x]` **Verify no hardcoded strings**: All user-facing text uses `const.TRANS_KEY_*` → `translations/en.json`
  5. `[x]` **Verify translation keys**: New `clear_start_date` and `clear_end_date` keys exist in all 6 relevant form sections in `en.json`
  6. `[x]` **Final review**: Verify the fix against the original issue reproduction steps

## Testing & validation

- **Tests executed**:
  - `tests/test_badge_date_clearing.py` — 8 new unit tests, all passing (Phase 1 fix + Phase 2 clear checkboxes + data-builder round-trip)
  - Targeted badge suite (`test_badge_target_types.py`, `test_badge_cumulative.py`, `test_points_helpers.py`) — 83 passed
  - Full suite — **1966 passed, 4 skipped, 18 deselected, 0 failures** (448.99s)
- **Outstanding tests**: None. Full suite green.
- **Commands**:
  ```bash
  ./utils/quick_lint.sh --fix          # ruff + mypy + boundary checks — all green
  mypy custom_components/choreops/     # zero errors
  python -m pytest tests/test_badge_date_clearing.py -v --tb=short
  python -m pytest tests/ -q --tb=line # full suite
  ```

## Notes & follow-up

- **Schema version**: No increment needed — storage format unchanged (dates are already nullable in the schema).
- **No storage migration**: The fix only changes what values are written; the storage schema already supports `null` for both date fields.
- **No dashboard impact**: Dashboard cards already handle null dates (they render no progress bar when dates are missing, which is the existing behavior for badges created without dates).
- **Future consideration**: A badge CRUD service (like chores have) would provide an alternative clearing path, but is out of scope for this fix.
- **Reporter credit**: @geobrando provided excellent root-cause analysis with line-number references. The fix directly addresses their findings.

---

## Reverse verification pass (completed 2026-08-15)

Each planned step was traced against the actual code to catch gaps. Findings:

### ✅ Phase 1 — Verified correct

- **Line 2657 removal**: The `user_input.update()` block at `flow_helpers.py:2655-2661` is the ONLY location that force-clears `START_DATE`. Removing that one key is sufficient.
- **No other force-clear**: Searched entire codebase for `SENTINEL_NONE` + `START_DATE` — only this one location.
- **No downstream impact**: `data_builders.py:2360-2368` reads `start_date` from `user_input` with fallback to `existing_schedule`. After Phase 1, `start_date` won't be in `user_input` (not force-cleared), so it falls through to `existing_schedule` — correct.

### ✅ Phase 2 — Verified with corrections applied

- **Schema placement**: `build_badge_common_schema()` adds `start_date` only when `is_periodic` (line ~2326). `end_date` is added for all non-daily reset_schedule types (line ~2335). Clear checkboxes must follow the same conditionals.
- **Validation ordering**: The current code reads `recurring_frequency` first, THEN force-clears, THEN reads `start_date`/`end_date`. The clear-checkbox handling must be inserted between the `recurring_frequency` read and the force-clear block. (Corrected in step 3 above.)
- **Cumulative badge nuance**: Cumulative badges have `start_date` in the `edit_badge_cumulative` translation section (line ~1260: `"start_date": "🔄 RESET CYCLE: Start Date (Optional)"`) BUT the schema only adds `start_date` when `is_periodic`. This means the cumulative badge translation has a `start_date` key that's never rendered in the schema. This is a pre-existing translation artifact, not something we need to fix. We should NOT add `clear_start_date` to cumulative badge translations since the field doesn't exist in the cumulative schema.
- **Config flow compatibility**: `config_flow.py:async_add_badge_common()` calls `build_badge_common_schema()` and `validate_badge_common_inputs()`. The clear checkbox fields will be in the schema (default=False). In ADD mode, no dates exist to clear, so the checkboxes are harmless. No changes needed.
- **`data_builders.py`**: `build_badge()` lines 2360-2378 handle `None` for dates correctly. The `None if start_date in (None, "") else start_date` pattern already handles the case where validation sets the date to `None`. No changes needed.
- **`options_flow.py`**: `async_add_edit_badge_common()` calls `build_badge_common_schema()` then applies suggested values via `add_suggested_values_to_schema()`. The clear checkbox fields will be in the schema with default=False. In EDIT mode, suggested values populate existing dates; clear checkboxes default to False. No changes needed in options_flow.py.
- **`gamification_manager.py`**: `update_badge()` calls `db.build_badge(updates, existing=existing, badge_type=badge_type)` which handles the cleared dates correctly. No changes needed.

### ✅ Phase 3 — Test patterns verified

- **`FlowTestHelper.edit_entity_via_options_flow()`** exists at `tests/helpers/flow_test_helpers.py:580` and supports the exact edit flow needed (navigate → edit → select entity → submit form).
- **`add_badge_via_options_flow()`** exists at `tests/test_badge_target_types.py:96` for creating badges in tests.
- **Existing test patterns**: `test_options_flow_entity_crud.py:592` (`test_edit_chore_sparse_payload_explicit_clear_stays_distinct`) is the closest analog — it tests `clear_due_date` in an edit flow. This pattern can be adapted for badge clear-checkbox tests.

### ⚠️ Edge cases identified

1. **Cumulative badge `start_date` in translations but not in schema**: The `edit_badge_cumulative` and `add_badge_cumulative` translation sections include `start_date` keys, but the schema only adds `start_date` for periodic badges. This is a pre-existing inconsistency. We should NOT add `clear_start_date` to cumulative translations since the field doesn't exist in the cumulative schema. (No action needed — just documented.)

2. **Special occasion `start_date` not in schema**: Special occasion badges have `start_date` forced to equal `end_date` in validation (line ~2704), not exposed in the schema. Only `clear_end_date` is needed. Clearing `end_date` will cascade to `start_date` via the existing `if is_special_occasion: user_input[START_DATE] = user_input.get(END_DATE)` logic.

3. **Daily badges**: Daily badges have `include_reset_schedule` but the schema hides all reset schedule fields (`if not is_daily:` guard). No clear checkboxes needed. Verified correct.
