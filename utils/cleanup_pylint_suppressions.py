#!/usr/bin/env python3
"""Clean up pylint suppressions and convert to ruff format.

This script:
1. Removes obsolete pylint suppressions (no ruff equivalent)
2. Converts remaining ones to ruff format
3. Reports what was changed
"""

from pathlib import Path
import re

# Mapping: pylint rule -> (ruff_code, should_convert)
# should_convert = False means: rule is globally ignored in pyproject.toml, safe to remove
PYLINT_TO_RUFF: dict[str, tuple[str | None, bool]] = {
    # Complexity rules - already ignored globally in pyproject.toml
    "too-many-lines": (None, False),  # No ruff equivalent
    "too-many-public-methods": (None, False),  # No ruff equivalent
    "too-many-locals": ("PLR0914", False),  # Ignored in pyproject.toml
    "too-many-branches": ("PLR0912", False),  # Ignored in pyproject.toml
    "too-many-statements": ("PLR0915", False),  # Ignored in pyproject.toml
    "too-many-arguments": ("PLR0913", False),  # Ignored in pyproject.toml
    "too-many-positional-arguments": (None, False),  # No ruff equivalent
    "too-many-instance-attributes": ("PLR0902", False),  # Ignored in pyproject.toml
    # Rules that need conversion to ruff
    "unused-argument": ("ARG001", True),  # Convert to ruff
    "broad-except": ("BLE001", True),  # Convert to ruff
    "broad-exception-caught": ("BLE001", True),  # Convert to ruff
    "protected-access": ("SLF001", True),  # Convert to ruff
    # Rules with no ruff equivalent - safe to remove
    "abstract-method": (None, False),  # No ruff equivalent
    "line-too-long": (None, False),  # Formatter handles this
}


def process_line(line: str) -> tuple[str, bool, str]:
    """Process a single line and return (modified_line, was_changed, change_type).

    Returns:
        (modified_line, was_changed, change_type)
        change_type: "removed", "converted", "kept"
    """
    # Match various pylint disable patterns
    patterns = [
        r"# pylint: disable=([a-z0-9,-]+)",
        r"#pylint: disable=([a-z0-9,-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, line)
        if not match:
            continue

        rules = match.group(1).split(",")
        rules_to_keep = []
        ruff_rules = []

        for rule in rules:
            rule = rule.strip()

            if rule in PYLINT_TO_RUFF:
                ruff_code, should_convert = PYLINT_TO_RUFF[rule]

                if should_convert and ruff_code:
                    # Convert to ruff format
                    if ruff_code not in ruff_rules:
                        ruff_rules.append(ruff_code)
                # else: rule is ignored or has no equivalent, remove it
            else:
                # Unknown rule, keep it for manual review
                rules_to_keep.append(rule)

        # Build replacement
        if not rules_to_keep and not ruff_rules:
            # Remove entire comment
            modified = re.sub(pattern, "", line).rstrip()
            # Clean up trailing whitespace and extra spaces
            modified = re.sub(r"\s+$", "", modified)
            # If line is now just a comment marker or whitespace, remove the entire line
            if modified.strip() in ["#", ""] or modified.strip().startswith("#"):
                return "", True, "removed"
            return modified, True, "removed"

        if ruff_rules:
            # Convert to ruff format
            ruff_comment = f"# ruff: noqa: {', '.join(ruff_rules)}"
            modified = re.sub(pattern, ruff_comment, line)
            return modified, True, "converted"

        if rules_to_keep:
            # Keep unknown rules for manual review
            pylint_comment = f"# pylint: disable={','.join(rules_to_keep)}"
            modified = re.sub(pattern, pylint_comment, line)
            return modified, False, "kept"

    return line, False, "kept"


def process_file(file_path: Path, dry_run: bool = True) -> dict[str, int]:
    """Process a single file."""
    stats = {
        "removed": 0,
        "converted": 0,
        "kept": 0,
    }

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")  # noqa: T201
        return stats

    modified_lines = []
    file_changed = False

    for line in lines:
        modified_line, was_changed, change_type = process_line(line)

        # If line was completely removed (empty string), don't add it
        if modified_line == "" and was_changed and change_type == "removed":
            file_changed = True
            stats[change_type] += 1
            # Skip adding this line entirely
            continue

        modified_lines.append(modified_line if was_changed else line)

        if was_changed:
            file_changed = True
            if change_type != "removed":  # Already counted above
                stats[change_type] += 1

    if file_changed and not dry_run:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(modified_lines)
        except Exception as e:
            print(f"Error writing {file_path}: {e}")  # noqa: T201

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Clean up pylint suppressions")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed changes",
    )
    args = parser.parse_args()

    base_path = Path(__file__).parent.parent
    patterns = [
        "custom_components/**/*.py",
        "tests/**/*.py",
    ]

    total_stats = {
        "removed": 0,
        "converted": 0,
        "kept": 0,
        "files_processed": 0,
        "files_changed": 0,
    }

    print("=" * 70)  # noqa: T201
    print("Pylint Suppression Cleanup Tool")  # noqa: T201
    print("=" * 70)  # noqa: T201
    print(f"Mode: {'APPLY CHANGES' if args.apply else 'DRY RUN (no changes)'}")  # noqa: T201
    print()  # noqa: T201

    files_to_process: list[Path] = []
    for pattern in patterns:
        files_to_process.extend(base_path.glob(pattern))

    for file_path in files_to_process:
        stats = process_file(file_path, dry_run=not args.apply)

        if sum(stats.values()) > 0:
            total_stats["files_changed"] += 1
            total_stats["removed"] += stats["removed"]
            total_stats["converted"] += stats["converted"]
            total_stats["kept"] += stats["kept"]

            if args.verbose:
                rel_path = file_path.relative_to(base_path)
                print(f"{rel_path}:")  # noqa: T201
                print(f"  Removed: {stats['removed']}")  # noqa: T201
                print(f"  Converted: {stats['converted']}")  # noqa: T201
                print(f"  Kept: {stats['kept']}")  # noqa: T201

        total_stats["files_processed"] += 1

    print()  # noqa: T201
    print("=" * 70)  # noqa: T201
    print("Summary")  # noqa: T201
    print("=" * 70)  # noqa: T201
    print(f"Files processed: {total_stats['files_processed']}")  # noqa: T201
    print(f"Files changed: {total_stats['files_changed']}")  # noqa: T201
    print(f"Suppressions removed: {total_stats['removed']}")  # noqa: T201
    print(f"Suppressions converted to ruff: {total_stats['converted']}")  # noqa: T201
    print(f"Suppressions kept (unknown): {total_stats['kept']}")  # noqa: T201
    print()  # noqa: T201

    if not args.apply:
        print("⚠️  This was a DRY RUN - no files were modified")  # noqa: T201
        print("Run with --apply to make actual changes")  # noqa: T201
    else:
        print("✅ Changes applied successfully!")  # noqa: T201

    print()  # noqa: T201


if __name__ == "__main__":
    main()
