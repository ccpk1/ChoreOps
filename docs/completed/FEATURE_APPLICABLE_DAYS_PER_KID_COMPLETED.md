# Per-Kid Applicable Days Feature - Implementation Plan

**Code**: PKAD-2026-001
**Target Release**: v0.5.0
**Storage Schema**: v50 (migration required for existing INDEPENDENT chores)
**Status**: Ready for Implementation
**Last Updated**: Strategic Planner review with user decisions

---

## Initiative Snapshot

| Aspect             | Details                                                  |
| ------------------ | -------------------------------------------------------- |
| **Name**           | Per-Kid Applicable Days + Per-Kid Multi-Times (Option B) |
| **Code**           | PKAD-2026-001                                            |
| **Target Release** | v0.5.0                                                   |
| **Owner**          | Strategic Planning / Builder Agent                       |
| **Status**         | Planning → Ready for Implementation                      |
| **Scope**          | Full feature with per-kid days, times, consolidated form |

---

## Approved Data Model (User Decisions)

**Q1 Answer**: Remove `applicable_days` from main chore for INDEPENDENT (like `due_date` handling). Template shows on form for single kid but never stores at chore level for INDEPENDENT.

**Q2 Answer**: Blank `per_kid_applicable_days` = all days applicable (default). Selected days = only those days.

**Q3 Answer**: Yes, per-kid times for DAILY_MULTI (each kid can have different time slots).

**Q4 Answer**: When switching SHARED→INDEPENDENT: use first kid's info for chore-level values.

**Q5 Answer**: Follow existing due_date template pattern with "Apply to All" button (see `async_step_edit_chore_per_kid_dates()` at options_flow.py:1615).

**Q6 Answer**: Add migration to `migration_pre_v50.py` for existing INDEPENDENT chores.

**Data Model Summary**:

- **INDEPENDENT chores**:
  - `per_kid_applicable_days: {kid_id: [0,3], ...}` — per-kid weekdays (0=Mon...6=Sun)
  - `per_kid_daily_multi_times: {kid_id: "08:00|17:00", ...}` — per-kid time slots (if DAILY_MULTI)
  - Chore-level `applicable_days` cleared to `None` (like `due_date`)
- **SHARED chores**: Only chore-level `applicable_days` (per-kid unused)
- **Empty list = all days applicable** (not "never on schedule")
- **Templating**: Main form values pre-populate helper → "Apply to All" button

---

## Summary Table

| Phase                 | Description                                        | % Complete | Notes                                              |
| --------------------- | -------------------------------------------------- | ---------- | -------------------------------------------------- |
| Phase 1 – Setup       | Constants, validation, lift validation restriction | 100%       | ✅ All steps complete, lint+mypy+tests pass        |
| Phase 2 – UI Flow     | Extend helper form with days+times+templating      | 100%       | ✅ Unified form created, routing updated           |
| Phase 3 – Coordinator | Update scheduling to use per-kid applicable_days   | 100%       | ✅ Per-kid injection, conversions, lint+mypy+tests |
| Phase 4 – Integration | Calendar, dashboard helper use per-kid lookup      | 100%       | ✅ Helper methods, assigned_days attributes added  |
| Phase 5 – Testing     | Comprehensive scenarios, migration, edge cases     | 100%       | ✅ 29 tests across 7 categories implemented        |

---

## Detailed Phase Breakdown

### Phase 1: Setup (1.5-2 hours)

**Goal**: Add constants, validation, lift DAILY_MULTI restriction, add migration

#### Step 1.1: Add Constants (30 min)

**File**: `const.py`

**Location**: Insert near line ~650 (DATA*CHORE*\* constants section)

```python
# Per-kid applicable days and times
DATA_CHORE_PER_KID_APPLICABLE_DAYS: Final = "per_kid_applicable_days"
DATA_CHORE_PER_KID_DAILY_MULTI_TIMES: Final = "per_kid_daily_multi_times"
```

**Location**: Insert near line ~1050 (CFOP/CFOF constants section)

```python
# Per-kid configuration flow input keys
CFOP_CHORES_INPUT_APPLICABLE_DAYS_PER_KID: Final = "per_kid_applicable_days"
CFOP_CHORES_INPUT_DAILY_MULTI_TIMES_PER_KID: Final = "per_kid_daily_multi_times"
CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL: Final = "apply_days_to_all"
CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL: Final = "apply_times_to_all"
```

**Location**: Insert near line ~1500 (TRANS*KEY_CFOF_ERROR*\* section)

```python
# Per-kid applicable days error keys
TRANS_KEY_CFOF_ERROR_PER_KID_APPLICABLE_DAYS_INVALID: Final = "per_kid_applicable_days_invalid"
TRANS_KEY_CFOF_ERROR_PER_KID_DAILY_MULTI_TIMES_INVALID: Final = "per_kid_daily_multi_times_invalid"
```

**Testing**:

```bash
grep -n "DATA_CHORE_PER_KID_APPLICABLE_DAYS" custom_components/kidschores/const.py
./utils/quick_lint.sh --fix
```

#### Step 1.2: Add Validation Functions (30 min)

**File**: `flow_helpers.py`

**Location**: Insert after `validate_daily_multi_times()` (around line ~320)

```python
def validate_per_kid_applicable_days(per_kid_days: dict[str, list[int]]) -> tuple[bool, str | None]:
    """Validate per-kid applicable days structure.

    Args:
        per_kid_days: {kid_id: [0, 3], ...} where 0=Mon, 6=Sun

    Returns:
        Tuple of (is_valid, error_key_or_none)

    Validation Rules:
    - Empty dict allowed (use chore-level defaults)
    - Each kid value must be list of integers (0-6)
    - Empty list = all days applicable (valid)
    - No duplicate days in single kid's list
    """
    if not per_kid_days:
        return (True, None)  # Empty = use defaults

    for kid_id, days in per_kid_days.items():
        if not isinstance(days, list):
            return (False, const.TRANS_KEY_CFOF_ERROR_PER_KID_APPLICABLE_DAYS_INVALID)

        if not days:
            continue  # Empty list = all days (valid)

        for day in days:
            if not isinstance(day, int) or day < 0 or day > 6:
                return (False, const.TRANS_KEY_CFOF_ERROR_PER_KID_APPLICABLE_DAYS_INVALID)

        # Check for duplicates
        if len(days) != len(set(days)):
            return (False, const.TRANS_KEY_CFOF_ERROR_PER_KID_APPLICABLE_DAYS_INVALID)

    return (True, None)


def validate_per_kid_daily_multi_times(
    per_kid_times: dict[str, str],
    frequency: str,
) -> tuple[bool, str | None]:
    """Validate per-kid daily multi-times (only for DAILY_MULTI frequency).

    Args:
        per_kid_times: {kid_id: "08:00|17:00", ...}
        frequency: Chore recurring frequency

    Returns:
        Tuple of (is_valid, error_key_or_none)

    Note: Reuses existing validate_daily_multi_times() for format validation.
    """
    if frequency != const.FREQUENCY_DAILY_MULTI:
        return (True, None)  # Not applicable

    if not per_kid_times:
        return (True, None)  # Empty = use chore-level times

    for kid_id, times_str in per_kid_times.items():
        if not times_str or not times_str.strip():
            continue  # Empty = use chore-level default

        # Reuse existing validation
        is_valid, error_key = kh.validate_daily_multi_times(times_str)
        if not is_valid:
            return (False, const.TRANS_KEY_CFOF_ERROR_PER_KID_DAILY_MULTI_TIMES_INVALID)

    return (True, None)
```

#### Step 1.3: Modify DAILY_MULTI Validation Restriction (15 min)

**File**: `flow_helpers.py`

**Location**: `validate_daily_multi_kids()` at lines 228-256

**Current Code** (lines 240-256):

```python
def validate_daily_multi_kids(
    recurring_frequency: str,
    completion_criteria: str,
    assigned_kids: list[str],
) -> dict[str, str]:
    """Validate DAILY_MULTI kid assignment rules."""
    errors: dict[str, str] = {}

    if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
        # DAILY_MULTI + INDEPENDENT requires single kid
        # Rationale: Multiple kids with INDEPENDENT have per-kid dates,
        # but DAILY_MULTI means "same times for everyone" - conceptual conflict
        if (
            completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            and len(assigned_kids) > 1
        ):
            errors[const.CFOP_ERROR_DAILY_MULTI_KIDS] = (
                const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_KIDS
            )

    return errors
```

**CHANGE TO**:

```python
def validate_daily_multi_kids(
    recurring_frequency: str,
    completion_criteria: str,
    assigned_kids: list[str],
    per_kid_times: dict[str, str] | None = None,
) -> dict[str, str]:
    """Validate DAILY_MULTI kid assignment rules.

    Args:
        recurring_frequency: The chore's recurring frequency.
        completion_criteria: The chore's completion criteria.
        assigned_kids: List of assigned kid IDs or names.
        per_kid_times: Per-kid times dict (if provided, allows multi-kids).

    Returns:
        Dictionary of errors (empty if validation passes).

    PKAD-2026-001: Now allows DAILY_MULTI + INDEPENDENT + multi-kids
    when per_kid_times is provided (each kid has own time slots).
    """
    errors: dict[str, str] = {}

    if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
        # DAILY_MULTI + INDEPENDENT: allowed if per_kid_times exists
        # (each kid gets their own time slots)
        if (
            completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            and len(assigned_kids) > 1
            and not per_kid_times
        ):
            errors[const.CFOP_ERROR_DAILY_MULTI_KIDS] = (
                const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_KIDS
            )

    return errors
```

**Call Site Update**: Update calls to `validate_daily_multi_kids()` to pass `per_kid_times` parameter.

**Location**: Find with `grep -n "validate_daily_multi_kids" custom_components/kidschores/`

#### Step 1.4: Add Migration for Existing INDEPENDENT Chores (30 min)

**File**: `migration_pre_v50.py`

**Location**: Add new method after `_migrate_independent_chores()` (around line ~443)

**Pattern**: Follow existing `_migrate_independent_chores()` pattern (lines 382-443)

```python
def _migrate_per_kid_applicable_days(self) -> None:
    """Populate per_kid_applicable_days for INDEPENDENT chores (one-time migration).

    For each INDEPENDENT chore with chore-level applicable_days:
    1. Create per_kid_applicable_days with same value for all assigned kids
    2. Clear chore-level applicable_days to None

    Empty list means "all days applicable" (not "never scheduled").
    SHARED chores keep chore-level applicable_days unchanged.
    """
    chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
    migrated_count = 0

    for chore_id, chore_info in chores_data.items():
        # Only INDEPENDENT chores need per-kid migration
        if (
            chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            != const.COMPLETION_CRITERIA_INDEPENDENT
        ):
            continue

        # Skip if per_kid_applicable_days already exists
        if const.DATA_CHORE_PER_KID_APPLICABLE_DAYS in chore_info:
            continue

        # Get template from chore-level applicable_days
        template_days = chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Populate per-kid structure
        chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
            kid_id: template_days[:] for kid_id in assigned_kids  # Copy list
        }

        # Clear chore-level applicable_days (single source of truth)
        if const.DATA_CHORE_APPLICABLE_DAYS in chore_info:
            del chore_info[const.DATA_CHORE_APPLICABLE_DAYS]

        migrated_count += 1
        const.LOGGER.debug(
            "Migrated INDEPENDENT chore '%s' with per-kid applicable_days",
            chore_info.get(const.DATA_CHORE_NAME),
        )

    if migrated_count > 0:
        const.LOGGER.info(
            "Migrated %d INDEPENDENT chores to per-kid applicable_days",
            migrated_count,
        )
```

**Registration**: Add to `run_all_migrations()` (around line ~375):

```python
self._migrate_per_kid_applicable_days()
```

**Increment SCHEMA_VERSION_STORAGE_ONLY**: Update from 43 to 50 in const.py (per user schema plan)

#### Step 1.5: Add Translation Keys (15 min)

**File**: `translations/en.json`

**Location**: Under `config.error` section:

```json
{
  "config": {
    "error": {
      "per_kid_applicable_days_invalid": "Invalid applicable days format for one or more kids",
      "per_kid_daily_multi_times_invalid": "Invalid daily times format for one or more kids"
    }
  }
}
```

**Location**: Under `options.step` section (for helper form):

```json
{
  "options": {
    "step": {
      "edit_chore_per_kid_details": {
        "title": "Per-Kid Schedule Settings",
        "description": "Configure schedule and times for each kid. Template values from main form are pre-filled.",
        "data": {
          "apply_days_to_all": "Apply template days to all kids",
          "apply_times_to_all": "Apply template times to all kids"
        }
      }
    }
  }
}
```

---

### Phase 2: Config Flow & Helper Form (3-4 hours)

**Goal**: Extend existing helper form with per-kid days + times + templating

**KEY INSIGHT**: Consolidate two existing forms:

- `async_step_edit_chore_per_kid_dates()` (options_flow.py:1615) — due dates + templating
- `async_step_chores_daily_multi()` (options_flow.py:1863) — DAILY_MULTI times

**NEW FORM**: `async_step_edit_chore_per_kid_details()` — unified days + times + dates

#### Step 2.1: Create Unified Helper Form (2-3 hours)

**File**: `options_flow.py`

**Location**: Replace or extend `async_step_edit_chore_per_kid_dates()` (lines 1615-1860)

**Design Pattern** (from existing code):

```python
# Template pattern from async_step_edit_chore_per_kid_dates (line 1673-1685):
raw_template_date = getattr(self, "_chore_template_date_raw", None)
template_date_str = None
if raw_template_date:
    # ... normalize and store
```

**New Method Skeleton**:

```python
async def async_step_edit_chore_per_kid_details(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Unified helper: per-kid days + times + due dates with templating.

    Features (per PKAD-2026-001):
    - Applicable days multi-select per kid (always shown for INDEPENDENT)
    - Daily multi times text input per kid (if frequency = DAILY_MULTI)
    - Due date picker per kid (existing functionality)
    - Template section with "Apply to All" buttons
    - Pre-populates from main form values
    """
    coordinator = self._get_coordinator()
    errors: dict[str, str] = {}

    chore_data = getattr(self, "_chore_being_edited", None)
    if not chore_data:
        const.LOGGER.error("Per-kid details step called without chore data")
        return await self.async_step_init()

    internal_id = chore_data.get(const.DATA_INTERNAL_ID)
    if not internal_id:
        const.LOGGER.error("Per-kid details step: missing internal_id")
        return await self.async_step_init()

    # Only for INDEPENDENT chores
    completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
    if completion_criteria != const.COMPLETION_CRITERIA_INDEPENDENT:
        const.LOGGER.debug(
            "Per-kid details skipped - not INDEPENDENT (criteria: %s)",
            completion_criteria,
        )
        return await self.async_step_init()

    assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    if not assigned_kids:
        const.LOGGER.debug("Per-kid details skipped - no assigned kids")
        return await self.async_step_init()

    # Single-kid optimization (from line 1424-1457 pattern)
    # Skip popup if only one kid - apply template directly
    if len(assigned_kids) == 1:
        # Apply template values to single kid and continue
        # ... (implement single-kid shortcut)
        pass

    recurring_frequency = chore_data.get(
        const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
    )
    is_daily_multi = recurring_frequency == const.FREQUENCY_DAILY_MULTI

    # Get template values from main form (stored before build_chores_data cleared them)
    template_applicable_days = getattr(self, "_chore_template_applicable_days", [])
    template_daily_multi_times = getattr(self, "_chore_template_daily_multi_times", "")
    template_due_date = getattr(self, "_chore_template_date_raw", None)

    # Build name-to-id mapping
    name_to_id: dict[str, str] = {}
    for kid_id in assigned_kids:
        kid_info = coordinator.kids_data.get(kid_id, {})
        kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
        name_to_id[kid_name] = kid_id

    if user_input is not None:
        # Process "Apply to All" actions
        apply_days_to_all = user_input.get(const.CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL, False)
        apply_times_to_all = user_input.get(const.CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL, False)

        per_kid_applicable_days: dict[str, list[int]] = {}
        per_kid_daily_multi_times: dict[str, str] = {}
        per_kid_due_dates: dict[str, str | None] = {}

        for kid_name, kid_id in name_to_id.items():
            # Process applicable days
            if apply_days_to_all and template_applicable_days:
                per_kid_applicable_days[kid_id] = template_applicable_days[:]
            else:
                days_field = f"days_{kid_name}"
                per_kid_applicable_days[kid_id] = user_input.get(days_field, [])

            # Process daily multi times (if applicable)
            if is_daily_multi:
                if apply_times_to_all and template_daily_multi_times:
                    per_kid_daily_multi_times[kid_id] = template_daily_multi_times
                else:
                    times_field = f"times_{kid_name}"
                    per_kid_daily_multi_times[kid_id] = user_input.get(times_field, "")

            # Process due dates (existing logic from line 1709-1733)
            # ... (preserve existing due date handling)

        # Validate per-kid structures
        is_valid_days, days_error = fh.validate_per_kid_applicable_days(per_kid_applicable_days)
        if not is_valid_days:
            errors["base"] = days_error

        if is_daily_multi:
            is_valid_times, times_error = fh.validate_per_kid_daily_multi_times(
                per_kid_daily_multi_times, recurring_frequency
            )
            if not is_valid_times:
                errors["base"] = times_error

        if not errors:
            # Store per-kid data
            chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = per_kid_applicable_days
            if is_daily_multi:
                chore_data[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = per_kid_daily_multi_times
            chore_data[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

            # Clear chore-level fields (single source of truth for INDEPENDENT)
            chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None
            if is_daily_multi:
                chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

            # Persist and return
            coordinator.update_chore_entity(internal_id, chore_data)
            coordinator._persist()
            coordinator.async_update_listeners()

            self._mark_reload_needed()
            self._chore_being_edited = None
            return await self.async_step_init()

    # Build form schema
    # Get existing per-kid data for defaults
    stored_chore = coordinator.chores_data.get(internal_id, {})
    existing_per_kid_days = stored_chore.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
    existing_per_kid_times = stored_chore.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
    existing_per_kid_dates = stored_chore.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})

    schema_dict: dict[vol.Required | vol.Optional, Any] = {}

    # Template section (if template values exist)
    if template_applicable_days:
        schema_dict[vol.Optional(const.CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL, default=False)] = (
            selector.BooleanSelector()
        )
    if is_daily_multi and template_daily_multi_times:
        schema_dict[vol.Optional(const.CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL, default=False)] = (
            selector.BooleanSelector()
        )

    # Per-kid fields
    for kid_name, kid_id in name_to_id.items():
        # Applicable days multi-select (always shown for INDEPENDENT)
        default_days = existing_per_kid_days.get(kid_id, template_applicable_days)
        schema_dict[vol.Optional(f"days_{kid_name}", default=default_days)] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(const.WEEKDAY_OPTIONS.keys()),
                    multiple=True,
                    translation_key=const.CFOF_CHORES_INPUT_APPLICABLE_DAYS,
                )
            )
        )

        # Daily multi times (conditional on DAILY_MULTI)
        if is_daily_multi:
            default_times = existing_per_kid_times.get(kid_id, template_daily_multi_times)
            schema_dict[vol.Optional(f"times_{kid_name}", default=default_times)] = (
                selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                )
            )

        # Due date (existing functionality)
        # ... (preserve existing due date picker pattern from lines 1790-1810)

    schema = vol.Schema(schema_dict)
    chore_name = chore_data.get(const.DATA_CHORE_NAME, "Unknown")

    return self.async_show_form(
        step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS,
        data_schema=schema,
        errors=errors,
        description_placeholders={"chore_name": chore_name},
    )
```

#### Step 2.2: Update Main Chore Form for Template Values (30 min)

**File**: `flow_helpers.py`

**Location**: `build_chores_data()` at line ~985

**Current behavior** (lines 1235-1241): Clears `due_date` for INDEPENDENT chores.

**NEW behavior**: Also clear `applicable_days` for INDEPENDENT chores, but FIRST store as template for helper form.

**Pattern**: Follow existing `_chore_template_date_raw` storage pattern (options_flow.py:1673)

**Code Change**:

```python
# In build_chores_data() - before clearing INDEPENDENT chore fields:
# Store template values for helper form to use
if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
    # Store templates before clearing (helper form will use these)
    # Note: These are stored on flow instance, not chore_data
    flow_instance._chore_template_applicable_days = chore_data.get(
        const.DATA_CHORE_APPLICABLE_DAYS, []
    )
    flow_instance._chore_template_daily_multi_times = chore_data.get(
        const.DATA_CHORE_DAILY_MULTI_TIMES, ""
    )

    # Clear chore-level fields (per PKAD-2026-001 single source of truth)
    chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None
    chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None
```

**IMPORTANT**: `build_chores_data()` is a pure function - need to pass flow instance or store on context.

**Alternative**: Store template in `self._chore_being_edited` dict before calling `build_chores_data()`.

#### Step 2.3: Update Routing Logic (30 min)

**File**: `options_flow.py`

**Location**: After chore form submission, route to helper (around line ~1400-1460)

**Current routing** (conceptual):

1. Edit chore → main form
2. If INDEPENDENT + DAILY_MULTI: route to `async_step_chores_daily_multi()`
3. Then route to `async_step_edit_chore_per_kid_dates()`
4. Finally save

**NEW routing** (consolidated):

1. Edit chore → main form
2. If INDEPENDENT: route to `async_step_edit_chore_per_kid_details()` (unified form)
3. Finally save

**Single-kid optimization**: If only 1 kid assigned, skip helper and apply template directly (existing pattern at line 1424-1457).

---

### Phase 3: Coordinator Logic (1.5-2 hours)

**Goal**: Update scheduling to use per-kid applicable_days

**KEY INSIGHT**: `_calculate_next_due_date_from_info()` already uses `applicable_days` (line 9153-9167).
Need to ensure per-kid rescheduling passes per-kid applicable_days.

#### Step 3.1: Update Per-Kid Rescheduling to Use Per-Kid Applicable Days (1 hour)

**File**: `coordinator.py`

**Location**: `_reschedule_chore_next_due_date_for_kid()` at line 9319

**Current Code** (lines 9377-9380):

```python
# Use consolidation helper for calculation
next_due_utc = self._calculate_next_due_date_from_info(
    original_due_utc, chore_info, completion_timestamp=completion_utc
)
```

**ISSUE**: `_calculate_next_due_date_from_info()` reads `applicable_days` from `chore_info` (line 9153):

```python
raw_applicable = chore_info.get(
    const.DATA_CHORE_APPLICABLE_DAYS, const.DEFAULT_APPLICABLE_DAYS
)
```

**SOLUTION**: For INDEPENDENT chores, inject per-kid applicable_days into chore_info copy before calling helper.

**Code Change**:

```python
def _reschedule_chore_next_due_date_for_kid(
    self, chore_info: dict[str, Any], chore_id: str, kid_id: str
) -> None:
    """Reschedule per-kid due date (INDEPENDENT mode)."""
    # ... (existing code lines 9319-9374)

    # PKAD-2026-001: For INDEPENDENT chores, use per-kid applicable_days
    # Create shallow copy of chore_info with per-kid values injected
    chore_info_for_calc = chore_info.copy()
    per_kid_applicable_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
    if kid_id in per_kid_applicable_days:
        chore_info_for_calc[const.DATA_CHORE_APPLICABLE_DAYS] = per_kid_applicable_days[kid_id]

    # Also inject per-kid daily_multi_times if present
    per_kid_times = chore_info.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
    if kid_id in per_kid_times:
        chore_info_for_calc[const.DATA_CHORE_DAILY_MULTI_TIMES] = per_kid_times[kid_id]

    # Use consolidation helper with per-kid overrides
    next_due_utc = self._calculate_next_due_date_from_info(
        original_due_utc, chore_info_for_calc, completion_timestamp=completion_utc
    )

    # ... (rest of existing code)
```

**ALTERNATIVE**: Modify `_calculate_next_due_date_from_info()` signature to accept optional per-kid overrides.

#### Step 3.2: Verify Rescheduling Trigger Points (30 min)

**Verify these call sites pass per-kid data correctly**:

| Call Site                                   | Line | Trigger                  | Status         |
| ------------------------------------------- | ---- | ------------------------ | -------------- |
| `approve_chore()`                           | 3034 | UPON_COMPLETION approval | Update needed  |
| `_reschedule_independent_recurring_chore()` | 8749 | Scheduled resets         | Update needed  |
| `_handle_chore_add_remove_kid()`            | 9682 | Kid assignment changes   | Update needed  |
| `_reschedule_chore_next_due_date_for_kid()` | 9377 | Direct call              | PRIMARY change |

**Action**: Verify each call site uses updated `_reschedule_chore_next_due_date_for_kid()` method.

#### Step 3.3: Handle Completion Criteria Switch (30 min)

**User Decision Q4**: When switching SHARED→INDEPENDENT: use first kid's info for chore-level.

**File**: `coordinator.py` (or `flow_helpers.py`)

**Location**: Where completion_criteria changes are processed

**Code Pattern**:

```python
def _handle_completion_criteria_change(
    self, chore_data: dict[str, Any], old_criteria: str, new_criteria: str
) -> None:
    """Handle completion criteria changes between SHARED and INDEPENDENT.

    PKAD-2026-001 Q4: When switching SHARED → INDEPENDENT:
    - Populate per_kid_applicable_days from chore-level
    - Clear chore-level applicable_days

    When switching INDEPENDENT → SHARED:
    - Use first kid's applicable_days for chore-level
    - Clear per_kid_applicable_days
    """
    assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

    if old_criteria == const.COMPLETION_CRITERIA_SHARED and new_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        # SHARED → INDEPENDENT: propagate to per-kid
        chore_days = chore_data.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
        chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
            kid_id: chore_days[:] for kid_id in assigned_kids
        }
        chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None

    elif old_criteria == const.COMPLETION_CRITERIA_INDEPENDENT and new_criteria in (
        const.COMPLETION_CRITERIA_SHARED, const.COMPLETION_CRITERIA_SHARED_FIRST
    ):
        # INDEPENDENT → SHARED: use first kid's values
        per_kid_days = chore_data.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        if assigned_kids and assigned_kids[0] in per_kid_days:
            chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = per_kid_days[assigned_kids[0]]
        chore_data[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = None
```

---

### Phase 4: Integration (1-1.5 hours)

**Goal**: Update calendar and dashboard helper to use per-kid lookup

#### Step 4.1: Calendar Per-Kid Applicable Days Lookup (45 min)

**File**: `calendar.py`

**Location**: Line 590 — current code reads chore-level only:

```python
applicable_days = chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
```

**CHANGE TO**:

```python
# PKAD-2026-001: Use per-kid applicable_days for INDEPENDENT chores
applicable_days = self._get_applicable_days_for_kid(chore)
```

**New Helper Method** (add around line ~550):

```python
def _get_applicable_days_for_kid(self, chore: dict[str, Any]) -> list[int]:
    """Get applicable days for this calendar's kid.

    For INDEPENDENT chores: use per_kid_applicable_days[kid_id]
    For SHARED chores: use chore-level applicable_days
    Empty list = all days applicable (fallback behavior preserved)

    Args:
        chore: Chore data dict

    Returns:
        List of weekday integers (0=Mon...6=Sun), or empty for all days
    """
    completion_criteria = chore.get(
        const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
    )

    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        per_kid_days = chore.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        if self._kid_id in per_kid_days:
            return per_kid_days[self._kid_id]
        # Fallback to chore-level (backward compat for un-migrated data)
        return chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])

    # SHARED chores: use chore-level
    return chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
```

**Update all call sites** in calendar.py that pass `applicable_days`:

- Line 619: `_generate_non_recurring_without_due_date()`
- Line 686: `_generate_recurring_*()` methods
- Line 722: Other generator methods

#### Step 4.2: Dashboard Helper Per-Kid Attributes (30 min)

**File**: `sensor.py` (dashboard helper section)

**Location**: Where chore dicts are built for dashboard helper attributes

**Add `assigned_days` field** to chore dict:

```python
# In dashboard helper chore dict building:
per_kid_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
kid_days = per_kid_days.get(kid_id, chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []))

chore_dict["assigned_days"] = self._format_applicable_days(kid_days)
chore_dict["assigned_days_raw"] = kid_days  # For automation filtering
```

**Helper Method** (add to sensor.py or kc_helpers.py):

```python
def _format_applicable_days(self, days: list[int]) -> str:
    """Format weekday list as human-readable string.

    Args:
        days: [0, 3] = Mon, Thu (0=Mon...6=Sun)

    Returns:
        "Mon, Thu" or "All days" if empty
    """
    if not days:
        return "All days"  # Empty = all days applicable

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return ", ".join(day_names[d] for d in sorted(days))
```

---

### Phase 5: Testing (2-3 hours) ✅ COMPLETE

**Goal**: Comprehensive coverage for per-kid applicable days feature

**Test File**: `tests/test_per_kid_applicable_days.py` (838 lines, 29 tests across 7 categories)

**Fixture Used**: `scenario_shared` (Stårblüm family) with per-kid data injection

**Implementation Pattern**: Direct coordinator testing with data injection (not dynamic chore creation since `coordinator.add_chore()` doesn't exist)

**Results**: 29 tests passing, mypy clean for test file

---

#### Test Category 1: Validation Functions (9 tests) ✅

**Class**: `TestPerKidValidation`

| Test ID | Test Name                                              | Description                            | Setup                               | Action                                    | Expected                                    |
| ------- | ------------------------------------------------------ | -------------------------------------- | ----------------------------------- | ----------------------------------------- | ------------------------------------------- | ---------------------- |
| VAL-01  | `test_validate_per_kid_applicable_days_valid`          | Valid structure passes                 | `{kid_id: [0, 2, 4]}` (Mon,Wed,Fri) | Call `validate_per_kid_applicable_days()` | Returns `(True, None)`                      |
| VAL-02  | `test_validate_per_kid_applicable_days_empty_dict`     | Empty dict is valid (use defaults)     | `{}`                                | Call `validate_per_kid_applicable_days()` | Returns `(True, None)`                      |
| VAL-03  | `test_validate_per_kid_applicable_days_empty_list`     | Empty list per kid is valid (all days) | `{kid_id: []}`                      | Call `validate_per_kid_applicable_days()` | Returns `(True, None)`                      |
| VAL-04  | `test_validate_per_kid_applicable_days_invalid_day`    | Day outside 0-6 rejected               | `{kid_id: [7]}` or `{kid_id: [-1]}` | Call `validate_per_kid_applicable_days()` | Returns `(False, error_key)`                |
| VAL-05  | `test_validate_per_kid_applicable_days_duplicate_days` | Duplicate days rejected                | `{kid_id: [0, 0, 1]}`               | Call `validate_per_kid_applicable_days()` | Returns `(False, error_key)`                |
| VAL-06  | `test_validate_per_kid_daily_multi_times_valid`        | Valid times structure passes           | `{kid_id: "08:00                    | 17:00"}`, freq=DAILY_MULTI                | Call `validate_per_kid_daily_multi_times()` | Returns `(True, None)` |

**Import Requirements**:

```python
from custom_components.kidschores import flow_helpers as fh
from custom_components.kidschores import const
```

---

#### Test Category 2: Coordinator Scheduling (6 tests)

**Class**: `TestPerKidScheduling`

| Test ID  | Test Name                                           | Description                                     | Setup                                                                 | Action                            | Expected                                     |
| -------- | --------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------- | --------------------------------- | -------------------------------------------- |
| SCHED-01 | `test_reschedule_uses_per_kid_applicable_days`      | Rescheduling respects per-kid days              | Create INDEPENDENT chore, kid1=[0,2], kid2=[1,3] (Mon/Wed vs Tue/Thu) | Approve chore for kid1 on Monday  | Next due for kid1 is Wednesday (not Tuesday) |
| SCHED-02 | `test_reschedule_empty_per_kid_days_any_day`        | Empty list = all days                           | Create chore with `per_kid_applicable_days={kid_id: []}`              | Approve on Friday                 | Next due can be Saturday                     |
| SCHED-03 | `test_reschedule_missing_kid_falls_back`            | Missing kid in dict uses chore-level            | Create chore with per_kid for kid1 only, not kid2                     | Reschedule for kid2               | Uses chore-level `applicable_days`           |
| SCHED-04 | `test_reschedule_per_kid_daily_multi_times`         | Per-kid times used for DAILY_MULTI              | Create DAILY_MULTI chore, kid1="08:00", kid2="18:00"                  | Check due dates                   | kid1 due at 08:00, kid2 due at 18:00         |
| SCHED-05 | `test_daily_multi_independent_multi_kid_allowed`    | DAILY_MULTI + INDEPENDENT + multi-kid now works | Create chore: freq=DAILY_MULTI, criteria=INDEPENDENT, 2 kids          | Provide per_kid_daily_multi_times | No validation error, chore created           |
| SCHED-06 | `test_chore_completion_triggers_correct_reschedule` | Approval reschedules with correct per-kid days  | Åsa=Mon/Wed, Björn=Tue/Thu, approve Åsa on Wed                        | Check Åsa's next due              | Next Monday (skips Thu/Fri/Sat/Sun)          |

**Key Coordinator Methods to Test**:

- `coordinator._reschedule_chore_next_due_date_for_kid()`
- `coordinator.approve_chore()` → triggers rescheduling

**Test Pattern**:

```python
async def test_reschedule_uses_per_kid_applicable_days(
    hass: HomeAssistant, scenario_medium: dict
) -> None:
    coordinator = scenario_medium["coordinator"]
    kid1_id = get_kid_by_name(scenario_medium, "Åsa")

    # Create chore with per-kid days
    chore_id = await coordinator.add_chore({
        const.DATA_CHORE_NAME: "Test Chore",
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        const.DATA_CHORE_ASSIGNED_KIDS: [kid1_id, kid2_id],
        const.DATA_CHORE_PER_KID_APPLICABLE_DAYS: {
            kid1_id: [0, 2],  # Mon, Wed
            kid2_id: [1, 3],  # Tue, Thu
        },
        # ... other required fields
    })

    # Approve and verify next due
    await coordinator.approve_chore(kid1_id, chore_id)
    # Assert next due is on Mon or Wed only
```

---

#### Test Category 3: Completion Criteria Switching (4 tests)

**Class**: `TestCompletionCriteriaSwitching`

| Test ID   | Test Name                                          | Description                                                | Setup                                                                  | Action                | Expected                                                             |
| --------- | -------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------- | --------------------- | -------------------------------------------------------------------- |
| SWITCH-01 | `test_shared_to_independent_populates_per_kid`     | SHARED→INDEPENDENT copies days to all kids                 | SHARED chore with `applicable_days=[0,1,2]` (Mon-Wed)                  | Update to INDEPENDENT | `per_kid_applicable_days` = {each_kid: [0,1,2]}, chore-level cleared |
| SWITCH-02 | `test_independent_to_shared_uses_first_kid`        | INDEPENDENT→SHARED uses first kid's days                   | INDEPENDENT, Åsa=[0,1], Björn=[3,4]                                    | Update to SHARED      | Chore-level `applicable_days=[0,1]` (Åsa's), per_kid cleared         |
| SWITCH-03 | `test_independent_to_shared_first_preserves_times` | INDEPENDENT→SHARED preserves first kid's daily_multi_times | INDEPENDENT DAILY_MULTI, Åsa="08:00", Björn="18:00"                    | Update to SHARED      | Chore-level `daily_multi_times="08:00"` (Åsa's)                      |
| SWITCH-04 | `test_switch_clears_per_kid_structures`            | Switching to SHARED clears all per*kid*\* fields           | INDEPENDENT with per_kid_applicable_days and per_kid_daily_multi_times | Update to SHARED      | Both per_kid dicts removed/None                                      |

**Key Coordinator Method**: `coordinator._update_chore()` handles the switching via `_convert_independent_to_shared()` and `_convert_shared_to_independent()`

---

#### Test Category 4: Calendar Integration (4 tests)

**Class**: `TestCalendarPerKidDays`

| Test ID | Test Name                                    | Description                        | Setup                                                | Action                             | Expected                            |
| ------- | -------------------------------------------- | ---------------------------------- | ---------------------------------------------------- | ---------------------------------- | ----------------------------------- |
| CAL-01  | `test_calendar_uses_per_kid_applicable_days` | Calendar respects per-kid days     | INDEPENDENT chore, Åsa=[0,2] (Mon,Wed)               | Query Åsa's calendar for full week | Events only on Monday and Wednesday |
| CAL-02  | `test_calendar_shared_uses_chore_level`      | SHARED chore uses chore-level days | SHARED chore with `applicable_days=[0,4]` (Mon,Fri)  | Query kid calendar                 | Events on Mon and Fri               |
| CAL-03  | `test_calendar_fallback_to_chore_level`      | Missing per-kid falls back         | INDEPENDENT, per_kid_applicable_days missing kid2    | Query kid2 calendar                | Uses chore-level applicable_days    |
| CAL-04  | `test_calendar_empty_per_kid_all_days`       | Empty list = events every day      | INDEPENDENT with `per_kid_applicable_days={kid: []}` | Query calendar for week            | Events on all 7 days                |

**Test Pattern**:

```python
async def test_calendar_uses_per_kid_applicable_days(
    hass: HomeAssistant, scenario_medium: dict
) -> None:
    # Setup chore with per-kid days
    # Get calendar entity for kid
    calendar_entity = hass.states.get(f"calendar.kc_{kid_name}")

    # Get events for date range
    events = await calendar_entity.async_get_events(hass, start, end)

    # Filter events for this chore
    chore_events = [e for e in events if chore_name in e.summary]

    # Assert only on expected days
    for event in chore_events:
        assert event.start.weekday() in [0, 2]  # Mon, Wed
```

---

#### Test Category 5: Dashboard Helper (3 tests)

**Class**: `TestDashboardHelperPerKidDays`

| Test ID | Test Name                                       | Description                        | Setup                            | Action                            | Expected                                           |
| ------- | ----------------------------------------------- | ---------------------------------- | -------------------------------- | --------------------------------- | -------------------------------------------------- |
| DASH-01 | `test_dashboard_helper_assigned_days_formatted` | assigned_days shows human-readable | INDEPENDENT, kid=[0,3] (Mon,Thu) | Check dashboard helper attributes | `assigned_days="Mon, Thu"`                         |
| DASH-02 | `test_dashboard_helper_assigned_days_raw`       | assigned_days_raw has int list     | INDEPENDENT, kid=[0,3]           | Check dashboard helper attributes | `assigned_days_raw=[0, 3]`                         |
| DASH-03 | `test_dashboard_helper_empty_days_all_days`     | Empty list shows "All days"        | INDEPENDENT, kid=[]              | Check dashboard helper attributes | `assigned_days="All days"`, `assigned_days_raw=[]` |

**Assertion Pattern**:

```python
helper_state = hass.states.get(f"sensor.kc_{kid_name}_ui_dashboard_helper")
chores = helper_state.attributes.get("chores", [])
chore = next(c for c in chores if c["name"] == chore_name)
assert chore["assigned_days"] == "Mon, Thu"
assert chore["assigned_days_raw"] == [0, 3]
```

---

#### Test Category 6: Migration (3 tests)

**Class**: `TestPerKidMigration`

| Test ID | Test Name                                            | Description                     | Setup                                                        | Action        | Expected                                                                      |
| ------- | ---------------------------------------------------- | ------------------------------- | ------------------------------------------------------------ | ------------- | ----------------------------------------------------------------------------- |
| MIG-01  | `test_migration_independent_chore_populates_per_kid` | Old INDEPENDENT migrates        | Chore with chore-level `applicable_days=[0,1,2]`, no per_kid | Run migration | `per_kid_applicable_days={kid1: [0,1,2], kid2: [0,1,2]}`, chore-level cleared |
| MIG-02  | `test_migration_shared_chore_unchanged`              | SHARED chores not migrated      | SHARED chore with applicable_days                            | Run migration | No per_kid_applicable_days added, chore-level preserved                       |
| MIG-03  | `test_migration_already_has_per_kid_skipped`         | Already-migrated chores skipped | INDEPENDENT with per_kid_applicable_days present             | Run migration | No changes to existing per_kid data                                           |

**Migration Function**: `migration_pre_v50._migrate_per_kid_applicable_days()`

---

#### Test Category 7: Edge Cases (4 tests)

**Class**: `TestPerKidEdgeCases`

| Test ID | Test Name                                 | Description                         | Setup                                                              | Action                           | Expected                                       |
| ------- | ----------------------------------------- | ----------------------------------- | ------------------------------------------------------------------ | -------------------------------- | ---------------------------------------------- |
| EDGE-01 | `test_single_kid_optimization`            | Single kid uses template directly   | INDEPENDENT chore with 1 kid assigned                              | Set applicable_days in main form | per_kid_applicable_days populated for that kid |
| EDGE-02 | `test_kid_removed_cleans_per_kid_data`    | Removing kid cleans per_kid entries | INDEPENDENT with per_kid for 2 kids                                | Remove kid2 from assigned_kids   | per_kid_applicable_days[kid2] removed          |
| EDGE-03 | `test_kid_added_gets_chore_level_default` | Adding kid gets chore-level default | INDEPENDENT with per_kid for 1 kid, chore has template             | Add kid2 to assigned_kids        | kid2 gets chore-level applicable_days or empty |
| EDGE-04 | `test_all_seven_days_selected`            | Full week selection works           | Create chore with `per_kid_applicable_days={kid: [0,1,2,3,4,5,6]}` | Verify scheduling                | Events on all days, no filtering               |

---

#### Implementation Notes for Test Builder

**File Structure**:

```python
"""Tests for PKAD-2026-001: Per-Kid Applicable Days feature."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.kidschores import const
from custom_components.kidschores import flow_helpers as fh

from .conftest import get_kid_by_name, construct_entity_id


class TestPerKidValidation:
    """VAL-* tests: Validation function unit tests."""
    ...

class TestPerKidScheduling:
    """SCHED-* tests: Coordinator scheduling with per-kid days."""
    ...

class TestCompletionCriteriaSwitching:
    """SWITCH-* tests: Completion criteria changes."""
    ...

class TestCalendarPerKidDays:
    """CAL-* tests: Calendar integration."""
    ...

class TestDashboardHelperPerKidDays:
    """DASH-* tests: Dashboard helper attributes."""
    ...

class TestPerKidMigration:
    """MIG-* tests: Migration scenarios."""
    ...

class TestPerKidEdgeCases:
    """EDGE-* tests: Edge cases and boundary conditions."""
    ...
```

**Conftest Helpers Used**:

- `get_kid_by_name(scenario, name)` → returns kid_id
- `construct_entity_id(platform, kid_name, suffix)` → builds entity_id
- `scenario_medium` fixture → 2 kids (Åsa, Björn), standard chores

**Mock Requirements**:

- Mock `coordinator._notify_kid` with `AsyncMock()` to avoid notification side effects
- Use `freezegun` or `pytest_freezer` for date-sensitive scheduling tests

**Common Assertions**:

```python
# Verify per_kid_applicable_days structure
chore = coordinator.chores_data[chore_id]
assert chore.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS) == {kid_id: [0, 2]}
assert chore.get(const.DATA_CHORE_APPLICABLE_DAYS) is None  # Cleared for INDEPENDENT

# Verify due date on correct weekday
due_date = chore.get(const.DATA_CHORE_PER_KID_DUE_DATES, {}).get(kid_id)
if due_date:
    parsed = kh.parse_datetime_to_utc(due_date)
    assert parsed.weekday() in [0, 2]  # Mon or Wed
```

---

**Testing Commands**:

```bash
# Run PKAD tests only
pytest tests/test_per_kid_applicable_days.py -v --tb=short

# Run with coverage
pytest tests/test_per_kid_applicable_days.py \
    --cov=custom_components.kidschores.coordinator \
    --cov=custom_components.kidschores.calendar \
    --cov=custom_components.kidschores.sensor \
    --cov=custom_components.kidschores.flow_helpers \
    --cov-report=term-missing \
    -v

# Validate no regressions
pytest tests/ -v --tb=line
```

**Expected Test Count**: 30 tests across 7 categories
**Expected File Size**: ~400 lines

---

## Files to Modify

| File                                    | Changes                                                                         | Effort | Lines ~Affected         |
| --------------------------------------- | ------------------------------------------------------------------------------- | ------ | ----------------------- |
| `const.py`                              | Add DATA*CHORE_PER_KID*_, TRANS*KEY*_, CFOP\_\* constants                       | Low    | +20                     |
| `flow_helpers.py`                       | Add validation functions, modify `validate_daily_multi_kids()`                  | Low    | +60, ~15 modified       |
| `options_flow.py`                       | New unified helper form `async_step_edit_chore_per_kid_details()`               | High   | +200, replace 1615-1950 |
| `coordinator.py`                        | Update `_reschedule_chore_next_due_date_for_kid()`, add criteria switch handler | Medium | +50, ~20 modified       |
| `calendar.py`                           | Add `_get_applicable_days_for_kid()`, update line 590                           | Low    | +25, ~5 modified        |
| `sensor.py`                             | Dashboard helper per-kid attributes                                             | Low    | +15                     |
| `migration_pre_v50.py`                  | Add `_migrate_per_kid_applicable_days()`                                        | Medium | +50                     |
| `translations/en.json`                  | Add error keys, helper form strings                                             | Low    | +15                     |
| `tests/test_per_kid_applicable_days.py` | New test file                                                                   | Medium | +350                    |

**Total Estimated Effort**: 12-16 hours

---

## Decisions & Completion Check

### Decisions Captured

| Decision                                                 | Answer                                 | Rationale                                              |
| -------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------ |
| Q1: Remove applicable_days from INDEPENDENT chore level? | Yes                                    | Matches due_date pattern, single source of truth       |
| Q2: Empty per_kid_applicable_days meaning?               | All days applicable                    | User-friendly default, matches current behavior        |
| Q3: Per-kid times for DAILY_MULTI?                       | Yes                                    | Full flexibility, each kid can have different schedule |
| Q4: SHARED→INDEPENDENT switch behavior?                  | First kid's info for chore-level       | Predictable, preserves data                            |
| Q5: Templating pattern?                                  | Follow due_date "Apply to All" pattern | Code reuse, consistent UX                              |
| Q6: Migration location?                                  | migration_pre_v50.py                   | Follows existing pattern                               |

### Completion Requirements

- [ ] All Phase 1-5 steps completed
- [ ] `./utils/quick_lint.sh --fix` passes (9.5+/10)
- [ ] `mypy custom_components/kidschores/` returns zero errors
- [ ] `pytest tests/ -v` all tests pass
- [ ] Test coverage >95% for new code
- [ ] No hardcoded strings (all use TRANS*KEY*\*)
- [ ] Documentation updated (if any API changes)

### Sign-off

- [ ] Strategic Planner: Plan approved for implementation
- [ ] Builder Agent: Implementation complete
- [ ] QA: Tests pass, manual verification done

---

## References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data structure, chore schema, per_kid_due_dates pattern
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Constants naming, logging, type hints
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) - Phase 0 audit checklist
- [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) - Test scenarios, patterns
- [migration_pre_v50.py](../../custom_components/kidschores/migration_pre_v50.py) - Migration pattern reference
- [options_flow.py lines 1615-1950](../../custom_components/kidschores/options_flow.py) - Existing helper form patterns

---

## Next Steps

1. ✅ **Strategic review complete** — Plan updated with user decisions and code references
2. **Builder implements** Phases 1-5 in order
3. **Move to** `docs/completed/` after PR merge
