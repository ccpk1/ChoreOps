# Phase 1a TypedDict Cleanup Handoff - IN-PROCESS

**Initiative**: Complete TypedDict Safety Implementation (Phase 1a)
**Status**: Infrastructure Complete, Cleanup Required
**Owner**: Builder Agent
**Target**: Fix 224 mypy errors to achieve 0 error state
**Effort**: ~4-6 hours

---

## Current State

**✅ What's Done:**

- type_defs.py created: 815 lines, 29 TypedDict classes
- All tests passing: 782/782 ✅
- Infrastructure in place: All major data structures typed

**❌ What Needs Fixing:**

- 224 mypy errors across 6 files
- Plan document claims "0 mypy errors" but reality differs
- Errors are cleanup issues, not fundamental design problems

**Why IDE Shows No Errors:**

- Pyright (VSCode default) is more permissive than mypy
- pyrightconfig.json set to "warning" for missing imports only
- mypy enforces stricter type checking rules

---

## Error Breakdown by File

### 1. **sensor.py** (~140 errors)

**Error Types:**

- `redundant-cast`: Casts to TypedDict types that are now unnecessary
- `unused-ignore`: `# type: ignore` comments that worked before TypedDicts
- `union-attr`: Calling `.lower()` on values that might not be strings
- `no-redef`: Variable redefinition (e.g., `progress_data` on line 2588/2617)
- `operator`: Unsupported operand types for `+` (object + int)

**Example Errors:**

```
Line 2460: Redundant cast to "ChallengeProgress"
Line 2588: Redundant cast to "AchievementProgress"
Line 2601: Unused "type: ignore[assignment, operator]" comment
Line 2608: Unsupported operand types for + ("object" and "int")
Line 3688: Item "None" of "list[Any] | str | float | int | None" has no attribute "lower"
```

**Fix Strategy:**

- Remove redundant `cast()` calls (TypedDicts now provide type safety)
- Delete unused `# type: ignore` comments
- Add type guards before `.lower()` calls: `if isinstance(value, str): value.lower()`
- Rename redefined variables or merge logic
- Cast or validate before arithmetic operations

### 2. **migration_pre_v50.py** (~30 errors)

**Error Types:**

- `typeddict-item`: Incompatible types for TypedDict fields
- `attr-defined`: Calling methods on `object` type
- `literal-required`: Dynamic keys instead of literal strings
- `call-overload`: Wrong argument types to `round()`

**Example Errors:**

```
Line 843: Incompatible types (expression has type "None", TypedDict item "last_claimed" has type "str")
Line 778: Argument 2 to "setdefault" has incompatible type "dict[Never, Never]"; expected "KidChoreStats"
Line 904: TypedDict key must be a string literal; expected one of ("daily", "weekly", "monthly", "yearly", "all_time")
Line 1313: TypedDict "KidData" has no key "badges"
```

**Root Causes:**

- Lines 843-847: Setting `None` for fields typed as `str` (should be empty string `""`)
- Line 778/1248/1413: Using `{}` instead of proper TypedDict initializer
- Line 904: Using variable as key instead of literal string constant
- Line 1313: Typo - should be "badge_progress" not "badges"

**Fix Strategy:**

- Replace `None` with `""` for string fields (lines 843-847)
- Use proper TypedDict constructors instead of empty dicts
- Replace dynamic keys with constants from const.py
- Fix typo: `"badge_progress"` instead of `"badges"`

### 3. **coordinator.py** (~40 errors)

**Error Types:**

- `literal-required`: Dynamic keys in TypedDict access (lines 2858, 2878, 2902, 2904, 2907, 2908)
- `dict-item`: Incompatible dict entry types (lines 2971, 3196)
- `unused-ignore`: Many cleaned-up type: ignore comments (15+ occurrences)

**Example Errors:**

```
Line 2858: TypedDict key must be a string literal; expected one of ("state", "pending_claim_count", "name", ...)
Line 2971: Dict entry 0 has incompatible type "str": "str | None"; expected "str": "str"
Line 3382: Unused "type: ignore[assignment, call-overload, operator]" comment
```

**Root Cause:**

- Line 2858 uses `field_name` variable instead of literal string
- Dict literals mixing `str | None` values where only `str` expected
- Type ignore comments from pre-TypedDict era

**Fix Strategy:**

- Replace `kid_chores_data[chore_id][field_name]` with explicit key access
- Add type guards: `if value is not None: dict[key] = value`
- Remove all unused type: ignore comments

### 4. **kc_helpers.py** (~2 errors)

**Error Types:**

- `attr-defined`: Line 275 - calling `.items()` on object
- `return-value`: Line 352 - returning `ParentData | None` instead of `dict[str, Any] | None`

**Example:**

```python
# Line 275 - entity_map unpacking issue
data_dict, name_key = entity_map[entity_type]
for entity_id, entity_info in data_dict.items():  # ❌ data_dict is object type

# Line 352 - return type mismatch
return coordinator.parents_data.get(parent_id)  # ❌ Returns ParentData, expects dict
```

**Fix Strategy:**

- Line 275: Type annotate `data_dict` or cast to proper dict type
- Line 352: Either cast return or change function signature to return `ParentData | None`

### 5. **select.py** (~1 error)

**Error Type:**

- `call-overload`: Line 325 - wrong argument types to dict.get()

**Example:**

```
Line 325: No overload variant of "get" of "dict" matches argument types "str", "str"
```

**Fix Strategy:**

- Check dict.get() call signature - likely passing wrong type for default value

### 6. **calendar.py** (~1 error)

**Error Type:**

- `arg-type`: Line 346 - wrong type passed to RecurrenceEngine

**Example:**

```
Line 346: Argument 1 to "RecurrenceEngine" has incompatible type "dict[str, object]"; expected "ScheduleConfig"
```

**Fix Strategy:**

- Cast to ScheduleConfig TypedDict or construct proper ScheduleConfig object

---

## Validation Commands

**Before starting:**

```bash
cd /workspaces/kidschores-ha
mypy custom_components/kidschores/ 2>&1 | grep "Found"
# Should show: Found 224 errors in 6 files
```

**After each file fixed:**

```bash
mypy custom_components/kidschores/sensor.py 2>&1 | grep "error:"
mypy custom_components/kidschores/migration_pre_v50.py 2>&1 | grep "error:"
# etc.
```

**Final validation (ALL REQUIRED):**

```bash
# 1. Zero mypy errors
mypy custom_components/kidschores/
# Expected: Success: no issues found in 22 source files

# 2. Tests pass
pytest tests/ -v --tb=line
# Expected: 782 passed, 2 deselected

# 3. Lint passes (9.5+/10)
./utils/quick_lint.sh --fix
# Expected: ✅ All checks passed (Ruff/PyLint/mypy clean)
```

---

## Implementation Order

**Recommended sequence (easiest → hardest):**

1. **calendar.py** (1 error) - Simple cast fix
2. **select.py** (1 error) - Simple type fix
3. **kc_helpers.py** (2 errors) - Type annotations
4. **coordinator.py** (40 errors) - Mostly removing unused type: ignore
5. **migration_pre_v50.py** (30 errors) - None → "", dict constructors
6. **sensor.py** (140 errors) - Remove casts, type guards for .lower()

---

## Common Patterns

### Remove Redundant Cast

**Before:**

```python
progress_data: ChallengeProgress = cast("ChallengeProgress", badge_progress.get(badge_id, {}))
```

**After:**

```python
progress_data = badge_progress.get(badge_id, {})  # Already typed via TypedDict
```

### Remove Unused type: ignore

**Before:**

```python
attributes[const.ATTR_DESCRIPTION] = badge_info.get(const.DATA_BADGE_DESCRIPTION)  # type: ignore[assignment,call-overload,operator]
```

**After:**

```python
attributes[const.ATTR_DESCRIPTION] = badge_info.get(const.DATA_BADGE_DESCRIPTION)
```

### Fix None for String Fields

**Before:**

```python
const.DATA_KID_CHORE_DATA_LAST_CLAIMED: None,  # ❌ TypedDict expects str
```

**After:**

```python
const.DATA_KID_CHORE_DATA_LAST_CLAIMED: "",  # ✅ Empty string for no value
```

### Type Guard for .lower()

**Before:**

```python
if entity_info.get(const.ATTR_STATE, "").lower() == "active":  # ❌ Might be int/float
```

**After:**

```python
state = entity_info.get(const.ATTR_STATE, "")
if isinstance(state, str) and state.lower() == "active":  # ✅ Type guard
```

### Replace Dynamic Keys with Literals

**Before:**

```python
kid_chores_data[chore_id][field_name] = kid_name  # ❌ field_name is variable
```

**After:**

```python
# Option 1: Explicit branches
if field_name == const.DATA_KID_CHORE_DATA_CLAIMED_BY_NAME:
    kid_chores_data[chore_id][const.DATA_KID_CHORE_DATA_CLAIMED_BY_NAME] = kid_name
elif field_name == const.DATA_KID_CHORE_DATA_COMPLETED_BY_NAME:
    kid_chores_data[chore_id][const.DATA_KID_CHORE_DATA_COMPLETED_BY_NAME] = kid_name

# Option 2: Type ignore (if dynamic access truly needed)
kid_chores_data[chore_id][field_name] = kid_name  # type: ignore[literal-required]
```

---

## Definition of Done

- [x] mypy reports: "Success: no issues found in 22 source files"
- [x] No `# type: ignore` comments except where truly necessary
- [x] All 782 tests pass
- [x] `./utils/quick_lint.sh --fix` scores 9.5+/10
- [x] Plan document updated to reflect completion

---

## ✅ COMPLETION STATUS

**Date Completed**: January 19, 2026
**Final Validation Results**:

- MyPy: `Success: no issues found in 22 source files` ✅
- Tests: `782 passed, 2 deselected in 94.70s` ✅
- Lint: All checks passed ✅

**Summary**:
Eliminated 220+ mypy errors through systematic TypedDict integration cleanup. Removed redundant casts, unused type ignore comments, and added proper type guards. Additionally addressed 10 Pylance-specific warnings with strategic suppressions for hybrid type scenarios in cumulative badge maintenance logic.

**Key Achievements**:

- TypedDict infrastructure (29 classes, 815 lines) now fully integrated
- Silver Quality type safety requirements achieved
- Hybrid type system validated: TypedDict for storage contracts, runtime flexibility for intermediates
- All 6 affected files cleaned: sensor.py, coordinator.py, migration_pre_v50.py, kc_helpers.py, select.py, calendar.py

---

## Notes

**Why This Wasn't Caught Earlier:**

- Pyright (VSCode default type checker) is more lenient than mypy
- Plan document was aspirational, not tracking actual state
- Tests pass because they don't validate type hints

**Why This Matters:**

- Silver Quality requires 100% type hints + mypy clean
- Type safety prevents runtime errors
- Enables better IDE support and refactoring

**Estimated Effort:**

- calendar.py: 5 min
- select.py: 5 min
- kc_helpers.py: 15 min
- coordinator.py: 60 min
- migration_pre_v50.py: 90 min
- sensor.py: 120 min
- **Total: 4-6 hours**

---

## References

- Original plan: `docs/in-process/TYPEDEFS_SAFETY_IMPLEMENTATION_IN-PROCESS.md`
- Type definitions: `custom_components/kidschores/type_defs.py` (815 lines)
- Quality standards: `docs/QUALITY_REFERENCE.md` (Silver tier)
- MyPy config: `pyproject.toml` (strict mode enabled)
