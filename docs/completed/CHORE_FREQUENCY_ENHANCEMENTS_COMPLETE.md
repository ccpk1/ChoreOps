# Chore Frequency Enhancements - Implementation Plan

## Initiative snapshot

- **Name / Code**: Chore Frequency Enhancements (CFE-2026-001)
- **Target release / milestone**: v0.6.0
- **Owner / driver(s)**: Strategic Planning Agent
- **Status**: ✅ Complete - Ready for Archive

## Summary & immediate steps

| Phase / Step                        | Description                                                                       | % complete | Quick notes                                   |
| ----------------------------------- | --------------------------------------------------------------------------------- | ---------- | --------------------------------------------- |
| Phase 1 – Constants & Validation    | Add 2 frequency constants, hours unit, translation keys, validation logic         | 100%       | ✅ All constants + validation complete        |
| Phase 2 – Feature 1 Core Logic      | Implement completion-based rescheduling (pass last_completed instead of due_date) | 100%       | ✅ completion_timestamp param added           |
| Phase 3 – Feature 2 Helper Flow     | Create multi-daily times helper form (like existing per-kid dates helper)         | 100%       | ✅ Helper form + parsing complete             |
| Phase 4 – Features 2 & 3 Core Logic | Implement multi-time-per-day + CUSTOM hours unit                                  | 100%       | ✅ DAILY_MULTI + hours implemented            |
| Phase 5 – Testing                   | Comprehensive test coverage for all three features                                | 100%       | ✅ 74 tests passing (audit + fixes completed) |

### Key Objectives

1. **Feature 1 (FREQUENCY_CUSTOM_FROM_COMPLETE)**: Reschedule from completion date instead of due_date (simple enhancement)
2. **Feature 2 (FREQUENCY_DAILY_MULTI)**: Support multiple times per day (complex - requires new helper form + time parsing)
3. **Feature 3 (CUSTOM + hours unit)**: Add "hours" as interval unit to existing CUSTOM frequency (simple - extends existing calculation)

### Recent Work

- Initial analysis complete
- Existing helper flow structure understood (`edit_chore_per_kid_dates` pattern)
- Approval reset interaction clarified
- **INDEPENDENT chore dual-form UX issue identified and resolved**
- **Cron syntax consideration analyzed** (future enhancement vs current simplicity)
- **Phase 1 COMPLETE**: Constants, translations, and validation all in place
- **Phase 2 COMPLETE**: Feature 1 (CUSTOM_FROM_COMPLETE) core logic implemented
- **Phase 3 COMPLETE**: Helper form for daily multi-times created with:
  - `parse_daily_multi_times()` function in kc_helpers.py
  - `async_step_chores_daily_multi()` form in options_flow.py
  - Routing from add_chore/edit_chore to helper form
  - Translation entries in en.json
- **Phase 4 COMPLETE**: Features 2 & 3 core logic implemented:
  - `_calculate_next_multi_daily_due()` method in coordinator.py
  - Updated `_calculate_next_due_date_from_info()` for DAILY_MULTI
  - `_generate_recurring_daily_multi_with_due_date()` for calendar events
  - Hours unit already supported in `adjust_datetime_by_interval()`
- **Phase 5 COMPLETE**: Comprehensive test coverage implemented:
  - 74 total tests across 4 test files
  - `test_frequency_enhanced.py`: 36 tests (F1-01 to F1-08, F2-01 to F2-18, F3-01 to F3-10)
  - `test_frequency_validation.py`: 24 tests (V-01 to V-12, P-01 to P-08, edge cases)
  - `test_options_flow_daily_multi.py`: 6 tests (OF-01 to OF-04c)
  - `test_workflow_chores.py`: 4 workflow tests (WF-01 to WF-04)
  - Audit completed: Tests rewritten to use real workflows (not shortcut constant checks)
  - All quality gates passing: mypy (0 errors), lint (clean), 617 total tests passing
- **Post-Phase 5 Enhancement**: DAILY_MULTI due_date validation added:
  - Added validation error when DAILY_MULTI selected without due_date
  - Prevents creating chores that never auto-schedule (would stay PENDING forever)
  - Added helper text explaining due_date time component is ignored for DAILY_MULTI
  - Updated all 6 options flow tests to include due_date requirement

### Next Steps

1. ~~Add constants and translation keys (Phase 1)~~ ✅
2. ~~Implement Feature 1 core logic (pass completion timestamp - Phase 2)~~ ✅
3. ~~Build Feature 2 helper form (collect times list - Phase 3)~~ ✅
4. ~~Implement Feature 2 scheduling logic (Phase 4)~~ ✅
5. ~~Add comprehensive tests (Phase 5)~~ ✅
6. ~~Add DAILY_MULTI due_date validation~~ ✅
7. **Ready for completion review** - All phases complete, ready for archive

### Risks / Blockers

- ⚠️ Feature 2 (FREQUENCY*DAILY_MULTI) **incompatible** with `AT_MIDNIGHT*\*` reset types by design (resets once at midnight, but needs multiple resets per day)
- Feature 2 requires new form step (similar to `edit_chore_per_kid_dates`)
- Time format validation required (24-hour HH:MM with pipe separator, min 2 times, max 4-6 times)
- Feature 2 INDEPENDENT+DAILY_MULTI validation in **both** config_flow AND options_flow

### References

- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - Data model, storage schema
- [DEVELOPMENT_STANDARDS.md](../../docs/DEVELOPMENT_STANDARDS.md) - Coding standards
- [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) - Test patterns
- Existing helper pattern: `options_flow.py` lines 1574+ (`async_step_edit_chore_per_kid_dates`)

### Decisions & completion check

**Key Decisions**:

1. Feature 1 (CUSTOM_FROM_COMPLETE): Simple - just pass `last_completed` timestamp to existing reschedule calculation (no new helpers needed)
2. Feature 2 (DAILY_MULTI): Complex - requires new helper form step (pattern: like per-kid dates form)
3. Feature 3 (CUSTOM hours): Simple - add "hours" as interval unit to existing CUSTOM frequency (extends existing calculation in kc_helpers)
4. DAILY*MULTI validation: Accept UPON_COMPLETION, AT_DUE_DATE_ONCE, and AT_DUE_DATE_MULTI (reject AT_MIDNIGHT*\*)
5. Time slots: Min 2, Max 6 times per day (validation on count + format)
6. UPON_COMPLETION recommended for DAILY_MULTI (immediate slot advancement vs delayed with AT_DUE_DATE_MULTI)
7. Time format: Pipe-separated 24-hour time ("|" separator enforced by validation)
8. Timezone handling: Store as ISO UTC, parse user input with system timezone. Follow existing `kc_helpers` patterns.
9. **INDEPENDENT chore restriction**: DAILY_MULTI only allowed with single kid selection - validation in **BOTH** config_flow AND options_flow
10. Feature 3 (hours unit): No special reset restrictions - works with all reset types like other CUSTOM intervals
11. **DAILY_MULTI requires due_date**: Validation prevents creating chores without due_date (would never auto-schedule)

**Completion confirmation**:

- [x] All follow-up items completed (documentation updates, validation enhancements, test coverage)
- [x] All 5 phases complete with comprehensive test coverage (617 tests passing)
- [x] Post-phase validation enhancement added (DAILY_MULTI due_date requirement)
- [x] All quality gates passing (mypy 0 errors, lint clean, tests passing)

5. Time slots: Min 2, Max 4-6 times per day (validation on count + format)
6. UPON_COMPLETION recommended for DAILY_MULTI (immediate slot advancement vs delayed with AT_DUE_DATE_MULTI)
7. Time format: Pipe-separated 24-hour time ("|" separator enforced by validation)
8. Timezone handling: Store as ISO UTC, parse user input with system timezone. Follow existing `kc_helpers` patterns.
9. **INDEPENDENT chore restriction**: DAILY_MULTI only allowed with single kid selection - validation in **BOTH** config_flow AND options_flow
10. Feature 3 (hours unit): No special reset restrictions - works with all reset types like other CUSTOM intervals

**Completion confirmation**:

- [ ] All follow-up items completed (architecture updates, cleanup, documentation) before requesting owner approval

---

## Detailed phase tracking

### Phase 1 – Constants & Validation (100%) ✅

**Goal**: Define new frequency types, add translation keys, implement validation

**Steps**:

1. [x] **Add frequency constants to const.py** (~line 145)

   - Added: `FREQUENCY_CUSTOM_FROM_COMPLETE: Final = "custom_from_complete"` (line 142)
   - Added: `FREQUENCY_DAILY_MULTI: Final = "daily_multi"` (line 144)
   - `TIME_UNIT_HOURS` already existed (line 123), added to `CUSTOM_INTERVAL_UNIT_OPTIONS` (line 544)
   - Updated `FREQUENCY_OPTIONS` list (lines 2683, 2688) to include both new frequencies

2. [x] **Add data field constants** (~line 650)

   - Already existed: `DATA_CHORE_DAILY_MULTI_TIMES: Final = "daily_multi_times"` (line 1010)
   - Already existed: `CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: Final = "daily_multi_times"` (line 367)
   - Added: `CFOP_ERROR_DAILY_MULTI_RESET` and `CFOP_ERROR_DAILY_MULTI_KIDS` (lines 2265-2266)

3. [x] **Add translation keys** (~line 2400)

   - Already existed: Error translation keys (lines 2405-2420)
   - Added to en.json: Error messages (lines 360-365)
   - Added to en.json: Frequency options `daily_multi` and `custom_from_complete` (lines 1496, 1503)
   - Added to en.json: `hours` option in custom_interval_unit (line 1519)

4. [x] **Add validation for Feature 2 incompatibility in flow_helpers.py** (~line 1007+)

   - Added DAILY*MULTI + AT_MIDNIGHT*\* reset type validation
   - Added DAILY_MULTI + INDEPENDENT + multiple kids validation

5. [x] **Add entries to translations/en.json**
       and approval_reset_type not in [
       const.APPROVAL_RESET_UPON_COMPLETION,
       const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
       const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
       ]
       ):
       raise vol.Invalid(
       message="",
       error_message=const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET,
       )

   # Feature 2: DAILY_MULTI + INDEPENDENT incompatible with multiple kids

   # This check must also be in config_flow.py async_step_user/async_step_add_chore

   # AND in options_flow.py async_step_add_chore/async_step_edit_chore

   if (
   recurring_frequency == const.FREQUENCY_DAILY_MULTI
   and chore_type == const.CHORE_TYPE_INDEPENDENT
   and len(assigned_kid_ids) > 1
   ):
   raise vol.Invalid(
   message="",
   error_message=const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_KIDS,
   )

   # Feature 2: Validate time slot count (min 2, max 6)

   if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
   times_str = chore_data.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")
   time_slots = [t.strip() for t in times_str.split("|") if t.strip()]
   if len(time_slots) < 2:
   raise vol.Invalid(
   message="",
   error_message=const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_TOO_FEW,
   )
   if len(time_slots) > 6:
   raise vol.Invalid(
   message="",
   error_message=const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_TOO_MANY,
   )

   ```

   ```

6. **Add entries to translations/en.json**
   ```json
   {
     "options": {
       "step": {
         "chores_daily_multi": {
           "title": "Set daily times for: {chore_name}",
           "description": "Enter 2-6 times when this chore should be available each day. Use 24-hour format (HH:MM) separated by | (pipe).\n\nExample: 07:00|18:00 for morning and evening.\n\nLeave blank to use default daily schedule."
         }
       }
     },
     "config": {
       "error": {
         "cfof_error_daily_multi_requires_compatible_reset": "Daily multi frequency requires 'upon completion', 'at due date (once)', or 'at due date (multi)' reset type. Cannot use 'at midnight' reset types which block subsequent time slots.",
         "cfof_error_daily_multi_independent_multi_kids": "Daily multi frequency with independent chores only supports single kid selection. Multiple kids would require separate due dates per kid, which conflicts with shared daily time slots.",
         "cfof_error_daily_multi_times_required": "Daily multi frequency requires time list. Please enter times in HH:MM format separated by | (e.g., 08:00|17:00).",
         "cfof_error_daily_multi_times_invalid_format": "Invalid time format. Please use HH:MM format with 24-hour time separated by | (e.g., 08:00|12:00|18:00).",
         "cfof_error_daily_multi_times_too_few": "Daily multi frequency requires at least 2 times. For single time, use standard daily frequency.",
         "cfof_error_daily_multi_times_too_many": "Daily multi frequency supports maximum of 6 times per day."
       }
     },
     "selector": {
       "recurring_frequency": {
         "options": {
           "custom_from_complete": "Custom interval from completion date",
           "daily_multi": "Multiple times per day (2-6 times)"
         }
       },
       "interval_unit": {
         "options": {
           "hours": "Hours"
         }
       }
     }
   }
   ```

**Validation**:

```bash
grep -n "FREQUENCY_CUSTOM_FROM_COMPLETE\|FREQUENCY_DAILY_MULTI\|INTERVAL_UNIT_HOURS" custom_components/kidschores/const.py
./utils/quick_lint.sh --fix
```

**Key Issues**:

- Feature 2 fundamentally incompatible with AT*MIDNIGHT*\* reset types (validation prevents these combinations)
- Rationale: DAILY*MULTI needs immediate advancement to next slot, but AT_MIDNIGHT*\* keeps chore APPROVED until midnight (blocks subsequent time slots)
- Time slot validation: Min 2, Max 6 times per day

### CRITICAL BEHAVIOR: Overdue Completion Timing

**Discovered Issue**: When using `AT_DUE_DATE_MULTI` with DAILY_MULTI, overdue completions create delayed slot advancement:

**Scenario**:

- Chore due at 7am (AT_DUE_DATE overdue handling)
- Kid completes at 8am (1 hour overdue)
- Parent approves immediately
- **Reset doesn't happen until 6pm** (next due time passes)
- **Next day's 7am slot scheduled at 6pm**, not at approval time

**Root Cause** (coordinator.py line 8717+):

```python
# Reset only triggers when due_date passes, not at approval time
if current_datetime >= chore_due_date and reset_type == AT_DUE_DATE_MULTI:
    # Reschedule to next slot
```

**Recommendation**: **UPON_COMPLETION strongly preferred** for DAILY_MULTI

- Immediate slot advancement regardless of completion timing
- No delayed rescheduling behavior
- Consistent user experience (complete → next slot available immediately)

**AT_DUE_DATE_MULTI acceptable** if user understands delayed advancement for overdue completions.

### Feature 2: Daily Multi Times UI Flow (Detailed Example)

**Main Chore Form** (`add_chore` or `edit_chore`):

1. User selects "Multiple times per day (requires time list)" from frequency dropdown
2. User fills other fields (name, points, reset type, etc.)
3. User clicks "Submit"
4. **System routes to helper form** (instead of creating chore immediately)

**Helper Form** (`chores_daily_multi` step):

```
┌─────────────────────────────────────────────────────────────┐
│ Set daily times for: Feed the pets                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Enter times when this chore should be available each day.  │
│ Use 24-hour format (HH:MM) separated by | (pipe).         │
│                                                             │
│ Example: 07:00|12:00|18:00 for morning, midday, and        │
│ evening.                                                    │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Daily Times: │08:00|17:00                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌──────────┐  ┌────────┐                                  │
│ │ Submit   │  │ Back   │                                  │
│ └──────────┘  └────────┘                                  │
└─────────────────────────────────────────────────────────────┘
```

**Processing**:

- Parse "08:00|17:00" → `[time(8,0), time(17,0)]`
- Store as `daily_multi_times` field in chore data
- First due date = today at 8:00 AM (or 5:00 PM if past 8:00 AM)

**Validation Examples**:

- ✅ `"08:00|17:00"` → Two times (8am, 5pm) - minimum valid
- ✅ `"07:00|12:00|18:00"` → Three times (7am, noon, 6pm)
- ✅ `"06:00|10:00|14:00|18:00|22:00"` → Five times
- ✅ `"23:30|06:45"` → Late night and early morning (sorted: 06:45, 23:30)
- ❌ `"8am|5pm"` → Invalid format (not 24-hour HH:MM)
- ❌ `"25:00|17:00"` → Invalid hour (25 doesn't exist)
- ❌ `"08:00"` → Only one time (use regular DAILY instead)
- ❌ `""` → Empty (validation error)
- ❌ `"06:00|08:00|10:00|12:00|14:00|16:00|18:00"` → Seven times (max 6 allowed)

### Feature 2: Timezone Handling Strategy

**Challenge**: User enters times in local timezone ("08:00|17:00"), but system stores/works with UTC.

**Solution**: Use existing `kc_helpers` timezone infrastructure:

1. **UI Input**: User enters pipe-separated local times: `"08:00|17:00"`
2. **Parsing**: `parse_daily_multi_times()` combines with reference date + `const.DEFAULT_TIME_ZONE`
   - `"08:00"` + today's date + system timezone → timezone-aware datetime
   - Convert to UTC for storage/comparison: `dt_util.as_utc(dt_with_tz)`
3. **Scheduling**: Next slot calculation compares UTC times from parsed slots
4. **Storage**: Times string stored as-is (`"08:00|17:00"`), timezone applied at parse-time

**Follows existing patterns**:

- `flow_helpers.py` line 924+: `kh.normalize_datetime_input()` with `DEFAULT_TIME_ZONE`
- DateTimeSelector usage (line 831): Already handles local→UTC conversion
- All due dates stored as UTC ISO strings in `.storage/kidschores_data`

**Cross-timezone behavior**: Times interpreted in system's `const.DEFAULT_TIME_ZONE` (like all other chore scheduling)

### Feature 2: INDEPENDENT Chore Flow Complexity

**Problem**: INDEPENDENT chores with multiple kids create dual helper forms:

**Current Flow** (options_flow.py line 1459):

1. User creates INDEPENDENT chore with multiple kids selected
2. After main chore form: **First helper** = `edit_chore_per_kid_dates()` (different due dates per kid)
3. If DAILY_MULTI selected: **Second helper** = `chores_daily_multi()` (collect times)
4. Result: Two consecutive popup forms = confusing UX

**Solution**: **Restrict DAILY_MULTI to single kid for INDEPENDENT chores**

**Allowed Combinations**:

- ✅ **SHARED + DAILY_MULTI**: All kids, any number → only `chores_daily_multi()` helper
- ✅ **INDEPENDENT + single kid + DAILY_MULTI**: Only `chores_daily_multi()` helper
- ❌ **INDEPENDENT + multiple kids + DAILY_MULTI**: Blocked by validation

**Rationale**:

- DAILY_MULTI means "same times for everyone" (7am, 6pm)
- Multiple kids with different due dates conflicts with "same times" concept
- Single kid INDEPENDENT + DAILY_MULTI = valid use case (kid can do morning OR evening slot)

### Alternative Scheduling Syntax Consideration

**Current Format**: Pipe-separated times (`"08:00|17:00"`)

- ✅ Simple for users to understand
- ✅ Clear validation (`HH:MM` format only)
- ❌ Limited to daily recurrence only

**Cron-style Format**: Standard Unix cron syntax

- Examples:
  - `"0 8,17 * * *"` → 8am and 5pm daily
  - `"0 8,17 * * 1-5"` → 8am and 5pm weekdays only
  - `"*/30 9-17 * * *"` → Every 30 minutes during business hours
- ✅ Industry standard, very flexible
- ✅ Could support weekly patterns, specific days, etc.
- ❌ Complex for average users to learn
- ❌ Requires cron parsing library
- ❌ Much broader scope than current "daily multi-times" feature

**Recommendation**: **Start with simple pipe format, consider cron as future enhancement**

- Phase 1: Implement `"HH:MM|HH:MM"` for daily multi-times only
- Future consideration: Add cron syntax as advanced option (keeping pipe format for simplicity)

### Feature 3: CUSTOM Frequency Hours Unit Analysis

**What it is**: Add "hours" as an interval unit option to existing CUSTOM frequency (alongside days/weeks/months)

**Use Cases**:

- "Take medication every 4 hours"
- "Check on baby every 2 hours"
- "Exercise every 36 hours"

**Implementation**: Simple extension of existing CUSTOM frequency logic

- Existing: `INTERVAL_UNIT_DAYS`, `INTERVAL_UNIT_WEEKS`, `INTERVAL_UNIT_MONTHS`
- Add: `INTERVAL_UNIT_HOURS`
- Existing calculation in `kc_helpers.py` `adjust_datetime_by_interval()` already supports hours parameter
- Just need to expose hours in UI selector and pass to existing function

**No Reset Type Restrictions**: Unlike DAILY_MULTI, the hours unit works with all reset types:

- CUSTOM frequency with hours still advances to next interval after approval
- AT*MIDNIGHT*\* resets at midnight regardless of interval (consistent with days/weeks/months)
- User chooses reset behavior - no validation restriction needed

**Existing Pattern** (coordinator.py line 8912+):

```python
# CUSTOM frequency already uses adjust_datetime_by_interval
next_due_utc = kh.adjust_datetime_by_interval(
    base_date=base_date,
    interval_unit=custom_unit,  # "days", "weeks", "months" - add "hours"
    delta=custom_interval,
    require_future=True,
    return_type=const.HELPER_RETURN_DATETIME,
)
```

**Implementation Steps**:

1. Add `INTERVAL_UNIT_HOURS` constant
2. Add to interval unit selector options
3. Verify `adjust_datetime_by_interval()` handles hours (likely already does)
4. Update translations

---

### Phase 2 – Feature 1 Core Logic (100%) ✅

**Goal**: Implement completion-based rescheduling by passing last_completed timestamp

**Steps**:

1. [x] **Modify `_calculate_next_due_date_from_info()` in coordinator.py** (line 9000)

   - Added parameter: `completion_timestamp: datetime | None = None`
   - Added branch for FREQUENCY_CUSTOM_FROM_COMPLETE (line 9080)
   - Validates custom_unit includes TIME_UNIT_HOURS (line 9033)
   - Uses completion_timestamp as base, falls back to current_due_utc

2. [x] **Update `_reschedule_chore_next_due_date()` (SHARED chores)** (line 9131)

   - Extracts `last_completed` from chore_info (line 9152)
   - Parses to UTC with `kh.parse_datetime_to_utc()`
   - Passes `completion_timestamp=completion_utc` to calculation function (line 9159)

3. [x] **Update `_reschedule_chore_next_due_date_for_kid()` (INDEPENDENT chores)** (line 9189)
   - Extracts per-kid `last_approved` from `kid_chore_data` (line 9257)
   - Parses to UTC and passes to calculation function (line 9262)
   - Uses per-kid approval timestamp as completion reference

**Validation**: ✅ Passed

```bash
./utils/quick_lint.sh --fix  # ✅ Passed
mypy custom_components/kidschores/  # ✅ Zero errors
```

**Key Issues**: None - implementation complete

- Fallback required: If no last_completed timestamp, use due_date (for manual rescheduling)
- SHARED vs INDEPENDENT: Different timestamp sources (chore-level vs per-kid chore data)

---

### Phase 3 – Feature 2 Helper Flow (0%)

**Goal**: Create multi-daily times collection form (pattern: like `edit_chore_per_kid_dates`)

**Steps**:

1. **Add step constant to const.py** (~line 200)

   ```python
   CFOF_STEP_CHORES_DAILY_MULTI: Final = "chores_daily_multi"
   ```

2. **Create `async_step_chores_daily_multi()` in options_flow.py** (~after line 1800, after `edit_chore_per_kid_dates`)

   - **Pattern**: Similar to `async_step_edit_chore_per_kid_dates()` (lines 1574+)
   - Show title with chore name
   - Description: Explain pipe-separated format (`07:00|12:00|18:00`)
   - Single text field for times input
   - Validation: Parse times using new `kh.parse_daily_multi_times()` helper
   - On submit: Store in `daily_multi_times` field
   - Return to main menu or edit chore form

3. **Modify `async_step_add_chore()` and `async_step_edit_chore()` to route to helper**

   - After chore form submit, check:
     ```python
     if (
         user_input.get(const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY) == const.FREQUENCY_DAILY_MULTI
         and const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES not in user_input
     ):
         # Store chore data in temp state
         self._chore_being_edited = updated_chore_data
         # Route to helper form
         return await self.async_step_chores_daily_multi()
     ```

4. **Add helper function `parse_daily_multi_times()` to kc_helpers.py** (~line 1450)

   ```python
   def parse_daily_multi_times(
       times_str: str,
       reference_date: str | date | datetime | None = None,
       timezone_info: tzinfo | None = None
   ) -> list[datetime]:
       """Parse pipe-separated time strings into timezone-aware datetime objects.

       Args:
           times_str: Pipe-separated times in HH:MM format (e.g., "08:00|12:00|18:00")
           reference_date: Date to combine with times (defaults to today)
           timezone_info: Timezone for the times (defaults to const.DEFAULT_TIME_ZONE)

       Returns:
           List of timezone-aware datetime objects sorted chronologically.
           Empty list if parsing fails or no valid times found.

       Example:
           >>> parse_daily_multi_times("08:00|17:00")
           [datetime(2026, 1, 13, 8, 0, tzinfo=...), datetime(2026, 1, 13, 17, 0, tzinfo=...)]
       """
       if not times_str or not isinstance(times_str, str):
           return []

       # Default to today's date if no reference provided
       if reference_date is None:
           base_date = get_today_local_date()
       else:
           # Use normalize_datetime_input to handle various date formats
           normalized_dt = normalize_datetime_input(
               reference_date,
               return_type=const.HELPER_RETURN_DATE
           )
           base_date = normalized_dt if isinstance(normalized_dt, date) else get_today_local_date()

       # Default to system timezone if none provided
       tz_info = timezone_info or const.DEFAULT_TIME_ZONE

       result = []
       for time_part in times_str.split("|"):
           time_part = time_part.strip()
           if not time_part:
               continue

           try:
               hour, minute = time_part.split(":")
               time_obj = time(int(hour), int(minute))

               # Combine date + time and apply timezone
               dt_local = datetime.combine(base_date, time_obj)
               dt_with_tz = dt_local.replace(tzinfo=tz_info)

               result.append(dt_with_tz)
           except (ValueError, AttributeError):
               const.LOGGER.warning(
                   "Invalid time format in daily_multi_times: %s (expected HH:MM)",
                   time_part,
               )
               continue

       return sorted(result)
   ```

**Validation**:

```bash
pytest tests/test_options_flow.py::test_daily_multi_helper_form -v
./utils/quick_lint.sh --fix
```

**Key Issues**:

- Helper form follows existing pattern (`edit_chore_per_kid_dates`)
- Validation happens in helper step (not main chore form)
- Store as string (`"08:00|12:00|18:00"`), parse when needed

---

### Phase 4 – Features 2 & 3 Core Logic (0%)

**Goal**: Implement multi-time-per-day scheduling (Feature 2) and hourly intervals (Feature 3)

**Steps**:

1. **Implement next time slot calculation in coordinator.py** (~line 9000)

   ```python
   def _calculate_next_multi_daily_due(
       self,
       chore_info: dict[str, Any],
       base_due_utc: datetime
   ) -> datetime | None:
       """Calculate next due datetime for DAILY_MULTI frequency.

       Args:
           chore_info: Chore data containing daily_multi_times
           base_due_utc: Current due datetime

       Returns:
           Next due datetime (same day if before last slot, next day if past)
       """
       times_str = chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")
       if not times_str:
           const.LOGGER.warning("DAILY_MULTI frequency missing times string")
           return None

       # Convert base_due_utc to local timezone for date reference
       base_local = dt_util.as_local(base_due_utc)
       base_date = base_local.date()

       # Parse times with timezone awareness (converts to local, then to UTC)
       time_slots_local = kh.parse_daily_multi_times(
           times_str,
           reference_date=base_date,
           timezone_info=const.DEFAULT_TIME_ZONE
       )

       if not time_slots_local:
           const.LOGGER.warning("DAILY_MULTI frequency has no valid times")
           return None

       # Convert time slots to UTC for comparison
       time_slots_utc = [dt_util.as_utc(dt) for dt in time_slots_local]
       current_utc = dt_util.utcnow()

       # Find next available slot
       for slot_utc in time_slots_utc:
           if slot_utc > current_utc:
               return slot_utc

       # Past all slots today, wrap to first slot tomorrow
       tomorrow_local = (base_local + timedelta(days=1)).replace(
           hour=time_slots_local[0].hour,
           minute=time_slots_local[0].minute,
           second=0,
           microsecond=0
       )
       return dt_util.as_utc(tomorrow_local)
   ```

2. **Update `_calculate_next_due_date_from_info()` to handle DAILY_MULTI** (~line 8912)

   ```python
   if freq == const.FREQUENCY_DAILY_MULTI:
       return self._calculate_next_multi_daily_due(chore_info, current_due_utc)
   ```

3. **Extend `_generate_events_for_chore()` in calendar.py** (~line 321)

   - Add branch for FREQUENCY_DAILY_MULTI
   - Parse time slots using `kh.parse_daily_multi_times()`
   - Generate separate CalendarEvent for each time slot per day
   - Event summary: "Chore Name (Morning)" / "(Midday)" / "(Evening)" based on time
   - Event start/end: slot_time to slot_time+15min

4. **Update approval reset to work with DAILY_MULTI**
   - After approval with AT_MIDNIGHT_MULTI, call reschedule to advance to next slot
   - Chore remains available multiple times per day until midnight

**Validation**:

```bash
pytest tests/test_frequency_daily_multi.py -v
pytest tests/test_calendar.py::test_daily_multi_events -v
```

**Key Issues**:

- Calendar generates N events per day (1 per time slot)
- Next slot calculation wraps to next day after last slot
- Recommended reset type for DAILY_MULTI: UPON_COMPLETION (immediate slot advancement)

**Feature 3: CUSTOM Hours Unit Implementation**

4. **Verify/update `adjust_datetime_by_interval()` in kc_helpers.py** (~line 1450)

   Check if function already supports hours parameter. If not, add:

   ```python
   def adjust_datetime_by_interval(
       base_dt: datetime,
       interval_unit: str,
       delta: int,
       ...
   ) -> datetime:
       """Adjust datetime by specified interval.

       interval_unit: "days", "weeks", "months", or "hours" (Feature 3)
       """
       if interval_unit == const.INTERVAL_UNIT_HOURS:
           return base_dt + timedelta(hours=delta)
       elif interval_unit == const.INTERVAL_UNIT_DAYS:
           return base_dt + timedelta(days=delta)
       # ... existing weeks/months logic
   ```

5. **Add hours to interval unit selector** (flow_helpers.py ~line 500)

   - Find existing `build_interval_unit_selector()` or similar
   - Add `const.INTERVAL_UNIT_HOURS` to options list
   - UI will show: Days, Weeks, Months, Hours

6. **Update translations for hours unit**
   - Add selector option: "Hours"
   - Example help text: "Every X hours (e.g., every 4 hours)"

**Feature 3 Validation**:

```bash
pytest tests/test_frequency_custom.py -v  # Existing CUSTOM tests should still pass
pytest tests/test_frequency_custom_hours.py -v  # New tests for hours unit
./utils/quick_lint.sh --fix
```

---

### Phase 5 – Comprehensive Testing (0%)

**Goal**: Validate all scenarios and edge cases for all three features

---

#### Test Scenarios Checklist

##### A. Test Scenario File: `tests/scenarios/scenario_enhanced_frequencies.yaml`

| ID    | Chore Name                         | Feature | Frequency            | Completion Criteria | Reset Type        | Details                                              |
| ----- | ---------------------------------- | ------- | -------------------- | ------------------- | ----------------- | ---------------------------------------------------- |
| EF-01 | "Custom From Complete SHARED"      | F1      | custom_from_complete | shared              | upon_completion   | interval=10 days, 2 kids                             |
| EF-02 | "Custom From Complete INDEPENDENT" | F1      | custom_from_complete | independent         | at_due_date_once  | interval=7 days, 2 kids                              |
| EF-03 | "Daily Multi Morning Evening"      | F2      | daily_multi          | shared              | upon_completion   | times="07:00\|18:00"                                 |
| EF-04 | "Daily Multi Three Times"          | F2      | daily_multi          | shared              | at_due_date_multi | times="08:00\|12:00\|17:00"                          |
| EF-05 | "Daily Multi Single Kid"           | F2      | daily_multi          | independent         | upon_completion   | times="09:00\|21:00", 1 kid only                     |
| EF-06 | "Custom Hours 4h"                  | F3      | custom               | shared              | upon_completion   | interval=4, unit=hours                               |
| EF-07 | "Custom Hours 8h Cross Midnight"   | F3      | custom               | independent         | at_due_date_once  | interval=8, unit=hours, due=22:00 (crosses midnight) |
| EF-08 | "Existing Daily Regression"        | -       | daily                | shared              | at_midnight_once  | Regression test - existing behavior                  |
| EF-09 | "Existing Custom Days Regression"  | -       | custom               | independent         | at_due_date_once  | interval=5 days - regression test                    |

---

##### B. Test File: `tests/test_frequency_enhanced.py`

**B1. Feature 1: CUSTOM_FROM_COMPLETE Tests** (8 scenarios)

| ID    | Test Name                              | Setup                                   | Action                             | Expected Result                             |
| ----- | -------------------------------------- | --------------------------------------- | ---------------------------------- | ------------------------------------------- |
| F1-01 | test_early_completion_shared           | Due Jan 15, interval=10d, SHARED        | Complete Jan 12 (3 days early)     | Next due = Jan 22 (completion + 10 days)    |
| F1-02 | test_late_completion_shared            | Due Jan 15, interval=10d, SHARED        | Complete Jan 18 (3 days late)      | Next due = Jan 28 (completion + 10 days)    |
| F1-03 | test_on_time_completion                | Due Jan 15, interval=10d                | Complete Jan 15 (exactly on due)   | Next due = Jan 25 (same as standard CUSTOM) |
| F1-04 | test_no_completion_timestamp_fallback  | Due Jan 15, no last_completed set       | Reschedule triggered               | Uses due_date as base → Jan 25              |
| F1-05 | test_independent_per_kid_timestamps    | INDEPENDENT, 2 kids, interval=7d        | Kid1 completes Jan 10, Kid2 Jan 12 | Kid1 next=Jan 17, Kid2 next=Jan 19          |
| F1-06 | test_shared_uses_chore_level_timestamp | SHARED, 2 kids, interval=7d             | Kid1 completes (chore level)       | Both kids see next due from chore timestamp |
| F1-07 | test_with_upon_completion_reset        | CUSTOM_FROM_COMPLETE + UPON_COMPLETION  | Complete and approve               | Immediate reset to PENDING, next due set    |
| F1-08 | test_with_at_due_date_once_reset       | CUSTOM_FROM_COMPLETE + AT_DUE_DATE_ONCE | Complete and approve               | Stays APPROVED until due date passes        |

**B2. Feature 2: DAILY_MULTI Tests** (18 scenarios)

| ID    | Test Name                                    | Setup                                            | Action                          | Expected Result                             |
| ----- | -------------------------------------------- | ------------------------------------------------ | ------------------------------- | ------------------------------------------- |
| F2-01 | test_next_slot_before_first                  | times="08:00\|17:00", current=06:00              | Calculate next due              | Returns 08:00 today                         |
| F2-02 | test_next_slot_between_slots                 | times="08:00\|17:00", current=12:00              | Calculate next due              | Returns 17:00 today                         |
| F2-03 | test_next_slot_after_last_wrap               | times="08:00\|17:00", current=20:00              | Calculate next due              | Returns 08:00 tomorrow                      |
| F2-04 | test_three_slots_middle                      | times="07:00\|12:00\|18:00", current=10:00       | Calculate next due              | Returns 12:00 today                         |
| F2-05 | test_complete_advances_to_next_slot          | times="08:00\|17:00", at 08:00                   | Claim + approve                 | Next due = 17:00 same day                   |
| F2-06 | test_complete_last_slot_advances_to_tomorrow | times="08:00\|17:00", at 17:00                   | Claim + approve                 | Next due = 08:00 tomorrow                   |
| F2-07 | test_calendar_generates_multiple_events      | times="08:00\|17:00", window=3 days              | Get calendar events             | 6 events total (2 per day × 3 days)         |
| F2-08 | test_calendar_event_labels                   | times="07:00\|12:00\|18:00"                      | Get calendar events             | Labels: Morning, Afternoon, Evening         |
| F2-09 | test_shared_all_kids_same_schedule           | SHARED + 2 kids + times="08:00\|18:00"           | Both kids see chore             | Both see same time slots                    |
| F2-10 | test_independent_single_kid_allowed          | INDEPENDENT + 1 kid + DAILY_MULTI                | Create chore                    | Succeeds - single kid allowed               |
| F2-11 | test_upon_completion_reset_behavior          | DAILY_MULTI + UPON_COMPLETION                    | Complete slot 1 at 08:00        | Immediate reset, advances to 17:00          |
| F2-12 | test_at_due_date_multi_reset_behavior        | DAILY_MULTI + AT_DUE_DATE_MULTI                  | Complete slot 1 at 08:00        | Can complete again before 17:00 passes      |
| F2-13 | test_at_due_date_once_reset_behavior         | DAILY_MULTI + AT_DUE_DATE_ONCE                   | Complete slot 1 at 08:00        | Must wait until 17:00 passes to claim again |
| F2-14 | test_overdue_completion_slot_advancement     | times="07:00\|18:00", complete 09:00 (late)      | Claim + approve late completion | Advances to 18:00 (not 07:00 tomorrow)      |
| F2-15 | test_empty_times_returns_none                | times="" (empty)                                 | Calculate next due              | Returns None, logs warning                  |
| F2-16 | test_invalid_times_format_ignored            | times="8am\|5pm" (invalid)                       | Calculate next due              | Returns None (parsing fails gracefully)     |
| F2-17 | test_six_times_max_supported                 | times="06:00\|08:00\|10:00\|12:00\|14:00\|16:00" | Create chore                    | Succeeds - 6 times allowed                  |
| F2-18 | test_timezone_local_to_utc_conversion        | times="08:00\|17:00", timezone=America/NY        | Calculate next due              | Correct UTC times (13:00/22:00 UTC in EST)  |

**B3. Feature 3: CUSTOM Hours Unit Tests** (10 scenarios)

| ID    | Test Name                           | Setup                          | Action                | Expected Result                           |
| ----- | ----------------------------------- | ------------------------------ | --------------------- | ----------------------------------------- |
| F3-01 | test_4_hour_interval_same_day       | interval=4h, due=06:00         | Approve at 06:00      | Next due = 10:00 same day                 |
| F3-02 | test_8_hour_interval_cross_midnight | interval=8h, due=22:00         | Approve at 22:00      | Next due = 06:00 next day                 |
| F3-03 | test_36_hour_interval               | interval=36h, due=Jan 1 12:00  | Approve at noon Jan 1 | Next due = Jan 3 00:00 (midnight)         |
| F3-04 | test_1_hour_minimum                 | interval=1h, due=10:00         | Approve at 10:00      | Next due = 11:00 (1 hour later)           |
| F3-05 | test_hours_with_upon_completion     | interval=4h + UPON_COMPLETION  | Approve               | Immediate reset, due = +4 hours           |
| F3-06 | test_hours_with_at_midnight_once    | interval=6h + AT_MIDNIGHT_ONCE | Approve               | Stays APPROVED until midnight, then +6h   |
| F3-07 | test_hours_with_at_due_date_once    | interval=4h + AT_DUE_DATE_ONCE | Approve               | Stays APPROVED until due passes, then +4h |
| F3-08 | test_regression_days_still_works    | interval=5, unit=days          | Approve               | Next due = +5 days (regression check)     |
| F3-09 | test_regression_weeks_still_works   | interval=2, unit=weeks         | Approve               | Next due = +14 days (regression check)    |
| F3-10 | test_regression_months_still_works  | interval=1, unit=months        | Approve               | Next due = +1 month (regression check)    |

---

##### C. Test File: `tests/test_frequency_validation.py`

**C1. DAILY_MULTI Validation Tests** (12 scenarios)

| ID   | Test Name                                        | Input                                      | Expected Result                 |
| ---- | ------------------------------------------------ | ------------------------------------------ | ------------------------------- |
| V-01 | test_daily_multi_upon_completion_valid           | DAILY_MULTI + UPON_COMPLETION              | ✅ Accepted                     |
| V-02 | test_daily_multi_at_due_date_once_valid          | DAILY_MULTI + AT_DUE_DATE_ONCE             | ✅ Accepted                     |
| V-03 | test_daily_multi_at_due_date_multi_valid         | DAILY_MULTI + AT_DUE_DATE_MULTI            | ✅ Accepted                     |
| V-04 | test_daily_multi_at_midnight_once_rejected       | DAILY_MULTI + AT_MIDNIGHT_ONCE             | ❌ Validation error             |
| V-05 | test_daily_multi_at_midnight_multi_rejected      | DAILY_MULTI + AT_MIDNIGHT_MULTI            | ❌ Validation error             |
| V-06 | test_daily_multi_independent_single_kid_ok       | DAILY_MULTI + INDEPENDENT + 1 kid          | ✅ Accepted                     |
| V-07 | test_daily_multi_independent_multi_kids_rejected | DAILY_MULTI + INDEPENDENT + 2+ kids        | ❌ Validation error             |
| V-08 | test_daily_multi_shared_multi_kids_ok            | DAILY_MULTI + SHARED + 3 kids              | ✅ Accepted                     |
| V-09 | test_invalid_time_format_rejected                | times="8am\|5pm"                           | ❌ Validation error (not HH:MM) |
| V-10 | test_single_time_rejected                        | times="08:00" (only 1)                     | ❌ Validation error (min 2)     |
| V-11 | test_seven_times_rejected                        | times="06:00\|07:00\|...\|12:00" (7 times) | ❌ Validation error (max 6)     |
| V-12 | test_empty_times_rejected                        | times=""                                   | ❌ Validation error             |

**C2. Parse Function Unit Tests** (8 scenarios)

| ID   | Test Name                         | Input                                      | Expected Result                  |
| ---- | --------------------------------- | ------------------------------------------ | -------------------------------- |
| P-01 | test_parse_two_times_valid        | "08:00\|17:00"                             | [08:00, 17:00] sorted            |
| P-02 | test_parse_six_times_valid        | "06:00\|08:00\|10:00\|12:00\|14:00\|16:00" | 6 times, sorted                  |
| P-03 | test_parse_unsorted_gets_sorted   | "17:00\|08:00\|12:00"                      | [08:00, 12:00, 17:00] sorted     |
| P-04 | test_parse_invalid_hour_skipped   | "25:00\|08:00\|17:00"                      | [08:00, 17:00] (25:00 skipped)   |
| P-05 | test_parse_invalid_minute_skipped | "08:70\|17:00"                             | [17:00] only (08:70 skipped)     |
| P-06 | test_parse_non_numeric_skipped    | "morning\|17:00"                           | [17:00] only ("morning" skipped) |
| P-07 | test_parse_whitespace_handled     | " 08:00 \| 17:00 "                         | [08:00, 17:00] (trimmed)         |
| P-08 | test_parse_returns_timezone_aware | "08:00\|17:00" + timezone                  | Datetimes have tzinfo set        |

---

##### D. Test File: `tests/test_options_flow_daily_multi.py`

**D1. Options Flow Helper Form Tests** (6 scenarios)

| ID    | Test Name                                    | Flow Action                          | Expected Result                          |
| ----- | -------------------------------------------- | ------------------------------------ | ---------------------------------------- |
| OF-01 | test_add_chore_daily_multi_routes_to_helper  | Add chore with DAILY_MULTI frequency | Routes to chores_daily_multi step        |
| OF-02 | test_edit_chore_daily_multi_routes_to_helper | Edit chore, change to DAILY_MULTI    | Routes to chores_daily_multi step        |
| OF-03 | test_helper_form_saves_times                 | Enter "08:00\|17:00" in helper form  | Chore saved with daily_multi_times field |
| OF-04 | test_helper_form_validates_format            | Enter "8am\|5pm" (invalid)           | Error shown, form redisplayed            |
| OF-05 | test_helper_form_back_returns_to_init        | Click back on helper form            | Returns to init without saving           |
| OF-06 | test_edit_preserves_existing_times           | Edit DAILY_MULTI chore               | Helper pre-filled with existing times    |

---

##### E. Integration/Workflow Tests (in existing test files)

**E1. Add to `test_workflow_chores.py`** (4 scenarios)

| ID    | Test Name                                      | Setup                                | Expected Result                            |
| ----- | ---------------------------------------------- | ------------------------------------ | ------------------------------------------ |
| WF-01 | test_daily_multi_claim_approve_advances_slot   | DAILY_MULTI chore, claim slot 1      | After approve, due advances to slot 2      |
| WF-02 | test_custom_from_complete_uses_completion_time | CUSTOM_FROM_COMPLETE, complete early | Next due based on completion, not due_date |
| WF-03 | test_hours_interval_claim_approve_cycle        | CUSTOM hours=4, complete cycle       | Due advances by 4 hours each approval      |
| WF-04 | test_existing_daily_not_affected               | Standard DAILY chore                 | Regression: behavior unchanged             |

---

#### Implementation Steps

1. [ ] **Create scenario file**: `tests/scenarios/scenario_enhanced_frequencies.yaml` (9 chores)
2. [ ] **Create test file**: `tests/test_frequency_enhanced.py` (36 tests)
   - [ ] Feature 1 tests (F1-01 to F1-08)
   - [ ] Feature 2 tests (F2-01 to F2-18)
   - [ ] Feature 3 tests (F3-01 to F3-10)
3. [ ] **Create test file**: `tests/test_frequency_validation.py` (20 tests)
   - [ ] Validation tests (V-01 to V-12)
   - [ ] Parse function tests (P-01 to P-08)
4. [ ] **Create test file**: `tests/test_options_flow_daily_multi.py` (6 tests)
   - [ ] Options flow helper tests (OF-01 to OF-06)
5. [ ] **Add to existing files**: `test_workflow_chores.py` (4 tests)
   - [ ] Workflow integration tests (WF-01 to WF-04)
6. [ ] **Run full validation**:
   ```bash
   pytest tests/test_frequency_*.py -v
   pytest tests/test_options_flow_daily_multi.py -v
   pytest tests/ -v --tb=line
   ./utils/quick_lint.sh --fix
   mypy custom_components/kidschores/
   ```

---

**Total Test Count**: 66 new tests

- Feature 1 (CUSTOM_FROM_COMPLETE): 8 tests
- Feature 2 (DAILY_MULTI): 18 + 12 + 6 = 36 tests
- Feature 3 (Hours unit): 10 tests
- Workflow integration: 4 tests

**Validation Criteria**:

- All 66 new tests pass
- All 543 existing tests still pass (no regressions)
- Lint score ≥9.5/10
- MyPy: zero errors
- Coverage >95% for new code paths

---

## Notes & Context

### Feature 1: FREQUENCY_CUSTOM_FROM_COMPLETE

**What it is**: Reschedule from completion date instead of due date

**Example**:

- Chore due: January 10
- Kid completes: January 7 (3 days early)
- Current: Next due = January 10 + 10 days = January 20
- **Enhanced**: Next due = January 7 + 10 days = January 17

**Implementation**: Simple - just pass `last_completed` timestamp to existing reschedule calculation

**Works with**: All approval reset types (no conflicts)

### Feature 2: FREQUENCY_DAILY_MULTI

**What it is**: Multiple specific times per day (e.g., "Feed pet: 7am and 6pm")

**Example**:

- Times: "07:00|12:00|18:00"
- Kid sees 3 opportunities per day to complete chore
- Each completion advances to next time slot (or next day after last slot)

**Implementation**: Complex - requires helper form (collect times), time parsing, calendar multi-event, next-slot calculation

**Works with**: UPON*COMPLETION, AT_DUE_DATE_ONCE, or AT_DUE_DATE_MULTI (NOT AT_MIDNIGHT*\*)

**Why AT*MIDNIGHT*\* is restricted**:

- DAILY_MULTI needs immediate slot advancement after approval
- AT*MIDNIGHT*\* keeps chore APPROVED until midnight, blocking subsequent time slots
- Example: 7am slot completed at 8am → with AT_MIDNIGHT, stays APPROVED all day → 6pm slot never activates

### Existing Helper Pattern Reference

**Per-kid dates helper** (`options_flow.py` lines 1574+):

- Shows after main chore form for INDEPENDENT chores
- Collects individual due dates per kid
- Validates dates, applies template date option
- Stores in `per_kid_due_dates` dictionary

**Daily multi times helper** (to be created):

- Shows after main chore form for DAILY_MULTI frequency
- Collects pipe-separated time list
- Validates format (HH:MM|HH:MM)
- Stores in `daily_multi_times` string field

---

## Open Questions / Decisions Needed

### Before Implementation

1. **~~HOURLY Form Field~~**: ✅ RESOLVED - Feature 3 is just adding "hours" to existing interval unit selector (days/weeks/months/hours). No new form field needed.

2. **~~DAILY_MULTI + Single Kid INDEPENDENT~~**: ✅ RESOLVED

   - Single kid INDEPENDENT already skips per-kid dates helper (existing logic)
   - Reuse/complement that same logic for DAILY_MULTI flow
   - Validation in `build_chores_data()` covers both config_flow and options_flow automatically
   - Simplest approach: Let validation handle it, no special UI filtering needed

3. **Time Slot Limits**: ✅ RESOLVED - Min 2, Max 6 times per day

   - Single time → use regular DAILY frequency instead
   - Max 6 prevents overly complex parsing and calendar clutter

4. **Timezone Handling**: ✅ RESOLVED - Follow existing patterns
   - Store as ISO UTC
   - Parse user input with system timezone
   - Already many good patterns in codebase to follow

### During Implementation

5. **Edit Chore Flow**: How to pre-populate helper form when editing existing DAILY_MULTI chore?

   - Need to pass current `daily_multi_times` string to form as default value

6. **Calendar Event Per-Slot**: Each time slot = separate event, or one event with all times?

   - **Recommendation**: Separate events (easier to see which slots remain)
   - **Follow-up**: What happens to event when slot is completed? (show strikethrough? remove?)

7. **Dashboard Helper Sensor**: Does `ui_dashboard_helper` need new attributes for DAILY_MULTI?
   - Current: Returns chores list with due_date
   - May need: `daily_multi_times`, `next_slot_time` attributes per chore

### Post-Implementation

8. **Feature 1 Fallback**: ✅ RESOLVED - When no last_completed timestamp:
   - Occurs on: First ever completion, manual reschedule via service call
   - Fallback to due_date is correct behavior

---

**Status**: ✅ All blocking questions resolved. Phase 1 implementation in progress.

### Summary of Clarifications Applied

1. **Feature 3 corrected**: NOT a new HOURLY frequency - it's adding "hours" as interval unit to existing CUSTOM frequency
2. **INDEPENDENT validation**: `build_chores_data()` is shared - validation covers both flows automatically
3. **Single kid INDEPENDENT**: Already skips per-kid dates helper - reuse that logic pattern
4. **Time slot limits**: Min 2, Max 6 times per day with validation
5. **Timezone handling**: Store UTC, parse with system timezone, follow existing patterns
