# KidsChores Migration Validation Framework

**Created**: December 30, 2025
**Purpose**: Easily validate ANY v40→v42 data file migration without hardcoding entity IDs or values

## Overview

This framework provides reusable tools to validate KidsChores data migrations from schema v40 to v42. Unlike the original ad-ha specific tests, this framework:

✅ Auto-discovers all entities and their IDs
✅ Validates structure without hardcoded values
✅ Works with ANY v40 data file
✅ Provides detailed validation reports
✅ Reduces test creation time from 30-45 minutes to ~5 minutes

## Quick Start

### Testing a Single File

```bash
# Test any v40 data file with full validation
pytest tests/test_migration_generic.py \
    --migration-file=tests/migration_samples/kidschores_data_ad-ha -v

# Test another file
pytest tests/test_migration_generic.py \
    --migration-file=/path/to/other_data.json -v
```

### Testing Multiple Files

Edit `tests/test_migration_generic.py` and add files to the parametrize list:

```python
@pytest.mark.parametrize("sample_file", [
    "tests/migration_samples/kidschores_data_ad-ha",
    "tests/migration_samples/kidschores_data_user2",  # Add here
    "tests/migration_samples/kidschores_data_user3",  # And here
])
```

Then run:

```bash
pytest tests/test_migration_generic.py::test_multiple_files_example -v
```

### Standalone Validation

For quick file checks without full migration:

```bash
python utils/validate_migration.py tests/migration_samples/kidschores_data_ad-ha
```

This validates the v40 file structure only (doesn't run migration).

## Framework Components

### 1. `utils/validate_migration.py`

Core validation framework with:

- **MigrationValidator**: Main validation class
- **ValidationResult**: Individual check result
- **EntityCounts**: Entity counting helper

**Key Features**:

- Auto-discovers entities from data
- Validates v40/v42 schemas
- Checks entity preservation
- Validates modern structures
- Detects legacy fields
- Verifies data integrity

### 2. `tests/test_migration_generic.py`

Pytest integration with 8 test functions:

1. `test_generic_migration_v40_to_v42` - Full comprehensive validation
2. `test_generic_schema_upgrade` - Version upgrade check
3. `test_generic_entity_preservation` - Entity count validation
4. `test_generic_modern_structures` - v42 structure validation
5. `test_generic_legacy_field_removal` - Legacy field cleanup check
6. `test_generic_kid_data_integrity` - Kid data preservation
7. `test_generic_chore_data_integrity` - Chore data preservation
8. `test_generic_zero_data_loss` - Data loss detection

## Usage Patterns

### Pattern 1: Quick Test of New File

```bash
# Place new file in migration_samples/
cp /path/to/user_data.json tests/migration_samples/kidschores_data_newuser

# Test it
pytest tests/test_migration_generic.py \
    --migration-file=tests/migration_samples/kidschores_data_newuser -v
```

**Time: ~30 seconds** (vs. 30-45 minutes for manual test creation)

### Pattern 2: Batch Testing Multiple Files

```python
# In test_migration_generic.py, update parametrize:
@pytest.mark.parametrize("sample_file", [
    "tests/migration_samples/kidschores_data_ad-ha",
    "tests/migration_samples/kidschores_data_user2",
    "tests/migration_samples/kidschores_data_user3",
    "tests/migration_samples/kidschores_data_user4",
])
```

Then:

```bash
pytest tests/test_migration_generic.py::test_multiple_files_example -v
```

**Result**: All files tested in one run with individual pass/fail reporting

### Pattern 3: Programmatic Validation

```python
from utils.validate_migration import MigrationValidator

# In your code
validator = MigrationValidator("path/to/data_file")
validator.load_v40_data()

# Check if file is valid v40
result = validator.validate_v40_schema()
if result.passed:
    print(f"✅ Valid v40 file with {validator.before_counts.total()} entities")
else:
    print(f"❌ Invalid: {result.message}")

# Full migration test (requires hass instance)
results = await validator.validate_all(hass)
validator.print_report()
```

## Validation Checks

The framework performs these validations:

### ✅ V40 Schema Check

- Confirms data is v40 format
- Validates required v40 structure
- Counts all entities

### ✅ Migration Execution

- Loads data into integration
- Triggers migration logic
- Captures v42 result

### ✅ V42 Schema Check

- Confirms schema_version = 42
- Validates meta section
- Checks migration_applied list

### ✅ Entity Preservation

- Compares before/after counts
- Validates no entities lost
- Reports discrepancies

### ✅ Modern Structures

- Checks chore_stats nested dict
- Checks point_stats nested dict
- Validates completion_criteria field

### ✅ Legacy Field Removal

- Ensures old fields removed
- Checks for shared_chore (should be gone)
- Validates completed*chores*\* removed

### ✅ Kid Data Integrity

- Validates names preserved
- Checks points preserved
- Verifies all kid fields

### ✅ Chore Data Integrity

- Validates names preserved
- Checks default_points preserved
- Verifies shared_chore → completion_criteria

### ✅ Zero Data Loss

- Measures data size before/after
- Detects significant data loss
- Allows for structure changes

## Output Examples

### Successful Validation

```
======================================================================
MIGRATION VALIDATION REPORT
======================================================================

Data File: tests/migration_samples/kidschores_data_ad-ha

Before Migration: 26 entities
  - Kids: 2
  - Chores: 9
  - Badges: 4
  - Rewards: 3
  - Penalties: 5
  - Other: 3

After Migration: 26 entities

----------------------------------------------------------------------
VALIDATION RESULTS
----------------------------------------------------------------------

✅ PASS: V40 Schema Check - Valid v40 data with 26 entities
  schema_version: 40
  entity_counts: {'kids': 2, 'chores': 9, 'badges': 4, ...}

✅ PASS: Migration - Migration completed successfully

✅ PASS: V42 Schema Check - Valid v42 schema with complete meta section
  schema_version: 42
  migrations_applied: 8

✅ PASS: Entity Preservation - All 26 entities preserved
  before: {'kids': 2, 'chores': 9, ...}
  after: {'kids': 2, 'chores': 9, ...}

✅ PASS: Modern Structures - All v42 modern structures present and valid

✅ PASS: Legacy Field Removal - All legacy fields properly removed

✅ PASS: Kid Data Integrity - All 2 kids validated successfully

✅ PASS: Chore Data Integrity - All 9 chores validated successfully

======================================================================
SUMMARY: 8 passed, 0 failed
======================================================================

🎉 ALL VALIDATIONS PASSED! Migration successful.
```

### Failed Validation

```
❌ FAIL: Entity Preservation - Entity count mismatch: chores: 9 → 8 (lost 1)
  before: {'kids': 2, 'chores': 9, 'badges': 4}
  after: {'kids': 2, 'chores': 8, 'badges': 4}

❌ FAIL: Modern Structures - Found 1 structure issues
  issues: ['Missing completion_criteria field in chore (v42 field)']

======================================================================
SUMMARY: 6 passed, 2 failed
======================================================================

⚠️  2 validation(s) failed. Review issues above.
```

## Comparison: Old vs New Approach

### Old Approach (ad-ha specific tests)

**Time to create**: 30-45 minutes per file
**Code**: 746 lines (360 + 386)
**Maintenance**: High (hardcoded UUIDs, names, values)
**Reusability**: Low (requires manual adaptation)

**Steps required**:

1. Open data file and inspect structure
2. Copy entity IDs (kids, chores, badges, etc.)
3. Hardcode expected values (points, names, etc.)
4. Write assertions for each entity
5. Debug constant naming issues
6. Fix assertions until tests pass

### New Approach (generic framework)

**Time to create**: ~5 minutes per file
**Code**: ~650 lines (reusable framework)
**Maintenance**: Low (no hardcoded values)
**Reusability**: High (works with any v40 file)

**Steps required**:

1. Copy file to migration_samples/
2. Run pytest command with --migration-file flag
3. Review validation report

**Savings**: 25-40 minutes per file (87% time reduction)

## Advanced Usage

### Custom Validations

Extend the framework with custom checks:

```python
from utils.validate_migration import MigrationValidator, ValidationResult

class CustomValidator(MigrationValidator):
    def validate_custom_requirement(self) -> ValidationResult:
        """Your custom validation logic."""
        if some_condition:
            return ValidationResult(
                name="Custom Check",
                passed=True,
                message="Custom requirement satisfied"
            )
        return ValidationResult(
            name="Custom Check",
            passed=False,
            message="Custom requirement failed"
        )

    async def validate_all(self, hass):
        results = await super().validate_all(hass)
        results.append(self.validate_custom_requirement())
        return results
```

### Filtering Validations

Run only specific checks:

```python
validator = MigrationValidator("path/to/file")
validator.load_v40_data()
await validator.migrate_with_integration(hass)

# Run only entity preservation check
result = validator.validate_entity_preservation()
assert result.passed
```

### Integration in CI/CD

```yaml
# .github/workflows/migration-tests.yml
name: Migration Tests

on: [push, pull_request]

jobs:
  test-migrations:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Test all migration samples
        run: |
          pytest tests/test_migration_generic.py::test_multiple_files_example -v
```

## Troubleshooting

### Issue: "No --migration-file specified"

**Solution**: Provide file path:

```bash
pytest tests/test_migration_generic.py --migration-file=path/to/file -v
```

### Issue: "Migration file not found"

**Solution**: Check file path is correct and file exists:

```bash
ls -la tests/migration_samples/
```

### Issue: Validation fails with "Missing required v40 structure"

**Solution**: File might not be v40 format. Check:

```python
python utils/validate_migration.py path/to/file
```

### Issue: "Home Assistant dependencies required"

**Solution**: Install test dependencies:

```bash
pip install pytest-homeassistant-custom-component
```

## File Structure

```
kidschores-ha/
├── utils/
│   └── validate_migration.py          # Core validation framework
├── tests/
│   ├── test_migration_generic.py       # Pytest integration (NEW)
│   ├── test_migration_adha_sample.py   # Original ad-ha specific tests
│   └── migration_samples/
│       ├── kidschores_data_ad-ha       # Production data file
│       ├── kidschores_data_user2       # Add more files here
│       └── kidschores_data_user3
└── utils/
    └── MIGRATION_VALIDATION_FRAMEWORK.md  # This file
```

## Future Enhancements

Possible improvements:

1. **Visual diff reporting**: Show before/after data changes
2. **Performance benchmarking**: Measure migration execution time
3. **Data anonymization**: Sanitize sensitive data before testing
4. **Regression detection**: Compare against known good migrations
5. **Badge validation**: Detailed badge progress verification
6. **Challenge validation**: Challenge progress and completion checks

## Credits

- **Original Work**: test_migration_adha_sample.py (ad-ha specific, 746 lines)
- **Framework**: Refactored into reusable pattern (December 30, 2025)
- **Time Saved**: 25-40 minutes per data file tested

## References

- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) - v42 architecture details
- [test_migration_adha_sample.py](test_migration_adha_sample.py) - Original specific implementation
- [ADHA_MIGRATION_VALIDATION_COMPLETE.md](ADHA_MIGRATION_VALIDATION_COMPLETE.md) - ad-ha validation summary

---

**Framework Version**: 1.0
**Last Updated**: December 30, 2025
**Status**: Production Ready ✅
