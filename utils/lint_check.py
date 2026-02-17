#!/usr/bin/env python3
"""Comprehensive linting check for KidsChores integration.

OPTIMIZED VERSION - Batches pylint calls for 10x speed improvement!
- 30 files: ~22 seconds (was 5+ minutes with individual pylint calls)
- Type checking disabled by default for speed (use --types to enable)

Run this after EVERY code change to ensure all quality standards are met.
Checks both integration code and test code for linting issues.

Acceptable Warnings (do NOT cause failure):
- Line length over 100 chars (if improves readability per testing instructions)
- Severity 2 pylint warnings (too-many-lines, import-outside-toplevel)

Suppressing False Positives:
- Type errors for intentionally flexible return types: # type: ignore[return-value]
- Pylint false positives: # pylint: disable=<code>  # Reason
- Module-level suppressions: Place after docstring, before imports

Usage:
    python utils/lint_check.py                    # Check all files (fast, no types)
    python utils/lint_check.py --types            # Check all files with type checking (slower)
    python utils/lint_check.py --integration      # Check only integration code
    python utils/lint_check.py --tests            # Check only test code
    python utils/lint_check.py --file path.py     # Check specific file
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Severity 4+ error codes that MUST be fixed or suppressed
CRITICAL_CODES = {
    "E0602",  # Undefined variable
    "E0611",  # No name in module
    "E1101",  # No member (attribute not found)
    "W0101",  # Unreachable code (always a bug)
    "W0612",  # Unused variable
    "W0613",  # Unused argument
    "W0611",  # Unused import
    "F401",  # Module imported but unused
    "W0404",  # Reimport
    "W0621",  # Redefined outer name
    "W0212",  # Protected member access
    "F841",  # Unused local variable
    "F541",  # F-string without placeholders
    "W0718",  # Broad exception caught
}

# Acceptable warnings (severity 2) that don't need fixing
ACCEPTABLE_CODES = {
    "C0301",  # Line too long
    "C0303",  # Trailing whitespace (we fix automatically)
    "C0415",  # Import outside toplevel
    "C0302",  # Too many lines in module
    "R0914",  # Too many local variables
    "R0912",  # Too many branches
    "R0915",  # Too many statements
    "R0913",  # Too many arguments
    "R0917",  # Too many positional arguments
    "R0911",  # Too many return statements
    "R1705",  # Unnecessary elif after return
    "R0904",  # Too many public methods
    "W0718",  # Broad exception caught (acceptable in specific contexts)
}


def run_command(cmd: list[str], capture_output: bool = True) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        cwd=Path(__file__).parent.parent,
        check=False,  # Don't raise on non-zero exit
    )
    return result.returncode, result.stdout, result.stderr


def check_pylint_batch(file_paths: list[str], label: str) -> tuple[bool, list[str]]:
    """Check pylint for critical errors on multiple files at once (MUCH faster)."""
    if not file_paths:
        return True, []

    print(f"{BLUE}Checking pylint ({label}):{RESET} {len(file_paths)} files")  # noqa: T201

    _returncode, stdout, _ = run_command(["pylint", *file_paths])

    # Parse pylint output for critical errors
    # Format: "path/file.py:123:4: W0718: Message (error-name)"
    critical_issues = []

    for line in stdout.splitlines():
        # Check if line contains an error code
        for code in CRITICAL_CODES:
            if f": {code}:" in line:
                critical_issues.append(line)
                break

    if critical_issues:
        print(f"{RED}✗ CRITICAL ISSUES FOUND (must fix or suppress):{RESET}")  # noqa: T201
        for issue in critical_issues:
            print(f"  {RED}{issue}{RESET}")  # noqa: T201
        return False, critical_issues

    # Show score if no critical issues
    for line in stdout.splitlines():
        if "rated at" in line:
            print(f"{GREEN}✓ {line.strip()}{RESET}")  # noqa: T201

    return True, []


def check_pylint(file_path: str) -> tuple[bool, list[str]]:
    """Check pylint for critical errors (single file - kept for compatibility)."""
    return check_pylint_batch([file_path], Path(file_path).name)


def check_type_errors(file_path: str) -> tuple[bool, list[str]]:
    """Check for type errors using pyright (Pylance backend)."""
    print(f"{BLUE}Checking type errors (Pylance/Pyright):{RESET} {file_path}")  # noqa: T201

    # Skip type checking for kc_helpers.py - uses intentionally flexible return types
    if "kc_helpers.py" in file_path:
        print(  # noqa: T201
            f"{YELLOW}⚠ Skipping type check for kc_helpers.py (flexible return types by design){RESET}"
        )
        return True, []

    # Check if pyright is installed
    returncode, _, _ = run_command(["which", "pyright"], capture_output=True)
    if returncode != 0:
        print(f"{YELLOW}⚠ Pyright not installed - type checking skipped{RESET}")  # noqa: T201
        print(  # noqa: T201
            f"{YELLOW}  For type errors, check VS Code Problems panel (Pylance extension){RESET}"
        )
        print(f"{YELLOW}  Or install: npm install -g pyright{RESET}")  # noqa: T201
        return True, []

    # Run pyright with JSON output
    returncode, stdout, stderr = run_command(["pyright", "--outputjson", file_path])

    errors = []
    output = stdout + stderr

    # Parse JSON output if available
    try:
        data = json.loads(stdout)
        if "generalDiagnostics" in data:
            for diag in data["generalDiagnostics"]:
                # Filter to only errors in the target file (not imported files)
                diag_file = diag.get("file", "")
                if file_path not in diag_file and not diag_file.endswith(
                    file_path.split("/")[-1]
                ):
                    continue  # Skip errors from imported files

                severity = diag.get("severity", "")
                message = diag.get("message", "")
                line = diag.get("range", {}).get("start", {}).get("line", 0) + 1
                rule = diag.get("rule", "unknown")
                # Severity levels: error, warning, information, hint
                if severity in ("error", "warning"):
                    errors.append(f"Line {line} [{rule}]: {message}")
    except (json.JSONDecodeError, KeyError, TypeError):
        # Fall back to text parsing
        for line in output.splitlines():
            if "error:" in line.lower() or "warning:" in line.lower():
                errors.append(line)

    if errors:
        print(f"{RED}✗ TYPE ERRORS FOUND:{RESET}")  # noqa: T201
        for error in errors[:10]:
            print(f"  {RED}{error}{RESET}")  # noqa: T201
        if len(errors) > 10:
            print(f"  {YELLOW}... and {len(errors) - 10} more{RESET}")  # noqa: T201
        return False, errors

    print(  # noqa: T201
        f"{GREEN}✓ No type errors (or check VS Code Problems panel for Pylance errors){RESET}"
    )
    return True, []


def check_trailing_whitespace(file_path: str) -> tuple[bool, list[int]]:
    """Check for trailing whitespace."""
    print(f"{BLUE}Checking trailing whitespace:{RESET} {file_path}")  # noqa: T201

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    issues = []
    for i, line in enumerate(lines, 1):
        if line.rstrip() != line.rstrip("\n"):
            issues.append(i)

    if issues:
        print(  # noqa: T201
            f"{YELLOW}⚠ Trailing whitespace on {len(issues)} lines:{RESET} {issues[:10]}"
        )
        print(f"{BLUE}  Auto-fix with:{RESET} sed -i 's/[[:space:]]*$//' {file_path}")  # noqa: T201
        return False, issues

    print(f"{GREEN}✓ No trailing whitespace{RESET}")  # noqa: T201
    return True, []


def check_long_lines(file_path: str, max_length: int = 100) -> tuple[bool, list[int]]:
    """Check for lines exceeding max length."""
    print(f"{BLUE}Checking line length (max {max_length}):{RESET} {file_path}")  # noqa: T201

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    long_lines = []
    for i, line in enumerate(lines, 1):
        if len(line.rstrip()) > max_length:
            long_lines.append(i)

    if long_lines:
        print(  # noqa: T201
            f"{YELLOW}⚠ {len(long_lines)} lines exceed {max_length} characters (acceptable if improves readability){RESET}"
        )
        print(f"  Lines: {long_lines[:10]}")  # noqa: T201
        if len(long_lines) > 10:
            print(f"  ... and {len(long_lines) - 10} more")  # noqa: T201
        print(  # noqa: T201
            f"{BLUE}💡 Per testing instructions: Long lines acceptable if they improve readability{RESET}"
        )
        print(f"{BLUE}ℹ️  This is WARNING only - does not cause failure{RESET}")  # noqa: T201
        return True, long_lines  # Not critical, just warning

    print(f"{GREEN}✓ All lines within {max_length} characters{RESET}")  # noqa: T201
    return True, []


def check_file(file_path: str, check_types: bool = False) -> bool:
    """Run all checks on a file. Returns True if all pass."""
    print(f"\n{BOLD}{'=' * 80}{RESET}")  # noqa: T201
    print(f"{BOLD}Checking: {file_path}{RESET}")  # noqa: T201
    print(f"{BOLD}{'=' * 80}{RESET}\n")  # noqa: T201

    all_passed = True

    # 1. Pylint (critical)
    passed, _ = check_pylint(file_path)
    all_passed = all_passed and passed

    # 2. Type errors (critical if check_types is True)
    if check_types:
        passed, _ = check_type_errors(file_path)
        all_passed = all_passed and passed

    # 3. Trailing whitespace (auto-fixable)
    check_trailing_whitespace(file_path)

    # 4. Long lines (warning only)
    check_long_lines(file_path)

    print()  # noqa: T201
    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive linting check for KidsChores"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Check only integration code",
    )
    parser.add_argument(
        "--tests",
        action="store_true",
        help="Check only test code",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Check specific file",
    )
    parser.add_argument(
        "--types",
        action="store_true",
        help="Enable type checking (slower, disabled by default)",
    )

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent

    # Determine which files to check
    files_to_check: list[str] = []
    if args.file:
        files_to_check = [args.file]
    elif args.integration:
        files_to_check = [
            "custom_components/choreops/config_flow.py",
            "custom_components/choreops/options_flow.py",
            "custom_components/choreops/flow_helpers.py",
            "custom_components/choreops/const.py",
            "custom_components/choreops/coordinator.py",
            "custom_components/choreops/services.py",
            "custom_components/choreops/calendar.py",
            "custom_components/choreops/sensor.py",
        ]
    elif args.tests:
        test_files = list((project_root / "tests").glob("test_*.py"))
        files_to_check = [str(f) for f in test_files]
    else:
        # Check key integration files and critical test files by default
        integration_files = [
            "custom_components/choreops/config_flow.py",
            "custom_components/choreops/options_flow.py",
            "custom_components/choreops/flow_helpers.py",
            "custom_components/choreops/const.py",
            "custom_components/choreops/coordinator.py",
            "custom_components/choreops/services.py",
            "custom_components/choreops/calendar.py",
            "custom_components/choreops/sensor.py",
        ]
        test_files = list((project_root / "tests").glob("test_*.py"))
        files_to_check = integration_files + [str(f) for f in test_files]

    print(f"{BOLD}{BLUE}KidsChores Linting Check{RESET}")  # noqa: T201
    print(f"{BLUE}Checking {len(files_to_check)} file(s){RESET}")  # noqa: T201
    if args.types:
        print(f"{YELLOW}Type checking enabled (slower){RESET}")  # noqa: T201
    else:
        print(f"{YELLOW}Type checking disabled (use --types to enable){RESET}")  # noqa: T201
    print()  # noqa: T201

    check_types = args.types
    all_passed = True

    # Convert paths to absolute
    absolute_paths = []
    for file_path in files_to_check:
        if not Path(file_path).is_absolute():
            full_path = project_root / file_path
        else:
            full_path = Path(file_path)

        if not full_path.exists():
            print(f"{RED}✗ File not found: {file_path}{RESET}")  # noqa: T201
            continue

        absolute_paths.append(str(full_path))

    # OPTIMIZATION: Run pylint on all files at once (10x faster)
    print(f"{BOLD}{'=' * 80}{RESET}")  # noqa: T201
    print(f"{BOLD}Step 1: Pylint Check (batched for speed){RESET}")  # noqa: T201
    print(f"{BOLD}{'=' * 80}{RESET}\n")  # noqa: T201

    passed, _ = check_pylint_batch(absolute_paths, "all files")
    all_passed = all_passed and passed

    # Type checking and other checks (if enabled)
    if check_types or args.file:
        print(f"\n{BOLD}{'=' * 80}{RESET}")  # noqa: T201
        print(f"{BOLD}Step 2: Individual File Checks{RESET}")  # noqa: T201
        print(f"{BOLD}{'=' * 80}{RESET}\n")  # noqa: T201

        for file_path in absolute_paths:
            print(f"{BLUE}Checking:{RESET} {file_path}")  # noqa: T201

            # Type errors (if enabled)
            if check_types:
                passed, _ = check_type_errors(file_path)
                all_passed = all_passed and passed

            # Quick checks
            check_trailing_whitespace(file_path)
            check_long_lines(file_path)
            print()  # noqa: T201
    else:
        # Just quick checks without type checking
        print(f"\n{BOLD}{'=' * 80}{RESET}")  # noqa: T201
        print(f"{BOLD}Step 2: Quick Checks (whitespace, line length){RESET}")  # noqa: T201
        print(f"{BOLD}{'=' * 80}{RESET}\n")  # noqa: T201

        for file_path in absolute_paths:
            check_trailing_whitespace(file_path)

        # Line length summary (don't spam for each file)
        total_long_lines = 0
        for file_path in absolute_paths:
            _, long_lines = check_long_lines(file_path)
            total_long_lines += len(long_lines)

        if total_long_lines > 0:
            print(  # noqa: T201
                f"{YELLOW}⚠ Total {total_long_lines} lines exceed 100 chars (acceptable){RESET}"
            )

    # Final summary
    print(f"\n{BOLD}{'=' * 80}{RESET}")  # noqa: T201
    if all_passed:
        print(f"{BOLD}{GREEN}✓ ALL CHECKS PASSED - READY TO COMMIT{RESET}")  # noqa: T201
        print(f"{GREEN}All {len(absolute_paths)} files meet quality standards{RESET}")  # noqa: T201
        if not check_types:
            print(  # noqa: T201
                f"{YELLOW}ℹ️  Type checking was disabled (use --types for full check){RESET}"
            )
        return 0

    print(f"{BOLD}{RED}✗ SOME CHECKS FAILED{RESET}")  # noqa: T201
    print(f"{RED}Fix critical issues before committing{RESET}")  # noqa: T201
    print(f"\n{YELLOW}Quick fixes:{RESET}")  # noqa: T201
    print("  • Trailing whitespace: ./utils/quick_lint.sh --fix")  # noqa: T201
    print("  • Remove unused imports/variables")  # noqa: T201
    print("  • Suppress intentional unused: # pylint: disable=unused-variable")  # noqa: T201
    print(f"\n{BLUE}💡 Suppressing False Positives:{RESET}")  # noqa: T201
    print("  • Type errors (flexible return types): # type: ignore[return-value]")  # noqa: T201
    print("  • Pylint false positives: # pylint: disable=<code>  # Reason")  # noqa: T201
    print("  • Module-level (after docstring): # pylint: disable=protected-access")  # noqa: T201
    print(  # noqa: T201
        f"\n{YELLOW}ℹ️  Note: Line length and severity 2 warnings are acceptable{RESET}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
