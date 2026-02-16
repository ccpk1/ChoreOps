# Linting Scripts

Comprehensive linting tools to ensure code quality before committing.

## Quick Start

```bash
# After EVERY code change, run:
./utils/quick_lint.sh

# Auto-fix trailing whitespace:
./utils/quick_lint.sh --fix
```

## Scripts

### quick_lint.sh

Fast check of integration code with auto-fix capability.

**Usage:**

```bash
./utils/quick_lint.sh           # Check integration files
./utils/quick_lint.sh --fix     # Auto-fix trailing whitespace first
```

**What it checks:**

- Pylint errors (critical severity 4+)
- Type errors (Pyright/Pylance)
- Trailing whitespace (auto-fixable)
- Line length warnings

### lint_check.py

Comprehensive linting with granular control.

**Usage:**

```bash
# Check all integration files
python utils/lint_check.py --integration

# Check all test files
python utils/lint_check.py --tests

# Check specific file
python utils/lint_check.py --file custom_components/kidschores/coordinator.py

# Skip type checking (faster)
python utils/lint_check.py --integration --no-types
```

## What Gets Checked

### ❌ Critical Errors (MUST FIX)

These will cause the script to fail:

- **E0602**: Undefined variable
- **E0611**: No name in module
- **W0612**: Unused variable → Remove or use `_` prefix
- **W0611/F401**: Unused import → Remove it
- **W0404**: Reimport → Don't import same module twice
- **W0621**: Redefined outer name → Use module-level suppression for fixtures
- **W0212**: Protected member access → Use module-level suppression in tests
- **F841**: Unused local variable → Remove it
- **F541**: F-string without placeholders → Convert to regular string
- **Type errors**: From Pyright/Pylance

### ⚠️ Warnings (Should Fix)

- **C0303**: Trailing whitespace → Run with `--fix` flag
- **C0301**: Line too long → Reformat if reasonable

### ✅ Acceptable (No Action)

- **C0302**: Too many lines in module
- **R0914/R0912/R0915**: Too many locals/branches/statements
- **R0913/R0917**: Too many arguments/positional arguments
- **R0904**: Too many public methods
- **C0415**: Import outside toplevel
- **C0301**: Line too long (if improves readability per testing instructions)

## Suppressing False Positives

When the linter reports issues that are intentional or unavoidable:

### Type Errors - Flexible Return Types

```python
# For helper functions designed to return multiple types
def parse_datetime_to_utc(value: Any) -> datetime | date | str | None:
    \"\"\"Parse various datetime formats.\"\"\"
    # Implementation returns different types based on input
    ...

# Usage site where you know the specific type
result = parse_datetime_to_utc(some_value)
if isinstance(result, datetime):
    # type: ignore[arg-type]  # parse_datetime_to_utc returns datetime here
    use_datetime(result)
```

### Type Errors - Attribute Access

```python
# Dynamic attributes
my_value = obj.dynamic_attr  # type: ignore[attr-defined]  # Dynamic attribute
```

### PyLint Warnings

```python
# Inline suppression with reason
result = _internal_function()  # pylint: disable=protected-access  # Testing internal API

# Module-level suppression (after docstring, before imports)
\"\"\"Test module for config flow.\"\"\"
# pylint: disable=protected-access  # This test module accesses internal APIs

from unittest.mock import AsyncMock
```

### When to Suppress

✅ **Suppress when**:

- Intentional design choice (e.g., flexible return types for helpers like `parse_datetime_to_utc`)
- Testing requires access to internals (`_method`, `_attribute`)
- Known limitation of static analysis tools
- Long lines improve readability (complex f-strings, etc.)

❌ **Don't suppress when**:

- Actual bugs or type mismatches
- Code can be refactored to satisfy the checker
- Unclear why the error occurs (investigate first)

## Integration into Workflow

### Before Every Commit

```bash
# 1. Make your changes
# 2. Run tests
pytest tests/ -x --tb=short -q

# 3. Run linting
./utils/quick_lint.sh --fix

# 4. Fix any critical issues found
# 5. Commit
```

### In Pre-commit Hook (Optional)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
./utils/quick_lint.sh
if [ $? -ne 0 ]; then
    echo "Linting failed. Run './utils/quick_lint.sh --fix' to auto-fix."
    exit 1
fi
```

## Common Fixes

### Trailing Whitespace

```bash
# Auto-fix all files
./utils/quick_lint.sh --fix

# Or manually:
sed -i 's/[[:space:]]*$//' path/to/file.py
```

### Unused Imports

```python
# Before
from typing import Dict, List, Optional
from . import const

# After (if Dict not used)
from typing import List, Optional
from . import const
```

### Protected Access in Tests

```python
# At top of test file, after docstring
# pylint: disable=protected-access  # Accessing _context/_persist for testing

# Now you can use ._context, ._persist, etc. without warnings
```

### Type Errors

```python
# Option 1: Fix the type issue
def get_value() -> str | None:  # Declare it can return None
    return None

# Option 2: Add type: ignore
value = obj.method()  # type: ignore[attr-defined]

# Option 3: Use proper type guards
if value is not None:
    result = value.upper()  # Now pyright knows value is str
```

## Troubleshooting

### "pyright not found"

```bash
pip install pyright
```

### "Too many errors"

Focus on critical errors first (marked with ❌). Warnings can be addressed later.

### "False positives"

Use inline suppressions:

```python
value = data["key"]  # type: ignore[index]  # Dynamic key access
```

## Exit Codes

- **0**: All checks passed
- **1**: Critical issues found (must fix before commit)
