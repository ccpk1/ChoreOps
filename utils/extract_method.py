#!/usr/bin/env python3
"""Utility script for safely extracting methods from Python files.

This script:
1. Finds exact method boundaries (start/end lines)
2. Extracts method content verbatim (no modifications)
3. Validates line counts before/after extraction
4. Supports dry-run mode for verification

Usage:
    # Find method boundaries
    python utils/extract_method.py coordinator.py claim_chore --info

    # Extract method to stdout (for verification)
    python utils/extract_method.py coordinator.py claim_chore --extract

    # Extract method to file
    python utils/extract_method.py coordinator.py claim_chore --extract --output extracted.txt

    # Extract multiple methods
    python utils/extract_method.py coordinator.py claim_chore approve_chore --extract
"""

import argparse
from pathlib import Path
import re
import sys


def find_method_boundaries(
    lines: list[str], method_name: str
) -> tuple[int, int] | None:
    """Find the start and end line numbers for a method.

    Args:
        lines: List of file lines (0-indexed)
        method_name: Name of method to find (without 'def' or parentheses)

    Returns:
        Tuple of (start_line, end_line) as 1-indexed line numbers, or None if not found.
        The range is inclusive [start, end].
    """
    # Pattern to match method definition
    method_pattern = re.compile(rf"^\s+(async\s+)?def\s+{re.escape(method_name)}\s*\(")

    start_line = None
    start_indent = None

    for i, line in enumerate(lines):
        if start_line is None:
            # Looking for method start
            match = method_pattern.match(line)
            if match:
                start_line = i
                # Calculate indentation (number of leading spaces)
                start_indent = len(line) - len(line.lstrip())
        else:
            # Looking for method end
            # Method ends when we hit another def/class at same or lower indent level
            # or a non-empty line at lower indent level
            stripped = line.rstrip()
            if not stripped:
                continue  # Skip blank lines

            current_indent = len(line) - len(line.lstrip())

            # Check if this is a new method/class at same or lower indent
            if current_indent <= start_indent:
                if re.match(r"\s*(async\s+)?def\s+\w+\s*\(", line) or re.match(
                    r"\s*class\s+\w+", line
                ):
                    # Found next method/class - previous line is end
                    # But we need to backtrack past any trailing blank lines/comments
                    end_line = i - 1
                    while end_line > start_line and not lines[end_line].strip():
                        end_line -= 1
                    return (start_line + 1, end_line + 1)  # Convert to 1-indexed

    # Method goes to end of file
    if start_line is not None:
        end_line = len(lines) - 1
        while end_line > start_line and not lines[end_line].strip():
            end_line -= 1
        return (start_line + 1, end_line + 1)  # Convert to 1-indexed

    return None


def extract_method(lines: list[str], start: int, end: int) -> list[str]:
    """Extract method lines (1-indexed, inclusive).

    Args:
        lines: List of file lines (0-indexed)
        start: Start line (1-indexed)
        end: End line (1-indexed, inclusive)

    Returns:
        List of extracted lines
    """
    return lines[start - 1 : end]


def get_method_info(filepath: Path, method_name: str) -> dict | None:
    """Get information about a method.

    Returns dict with:
        - name: method name
        - start_line: 1-indexed start line
        - end_line: 1-indexed end line
        - line_count: number of lines
        - is_async: whether method is async
        - first_line: the def line (for verification)
    """
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    bounds = find_method_boundaries(lines, method_name)
    if bounds is None:
        return None

    start, end = bounds
    extracted = extract_method(lines, start, end)
    first_line = extracted[0] if extracted else ""

    return {
        "name": method_name,
        "start_line": start,
        "end_line": end,
        "line_count": end - start + 1,
        "is_async": "async def" in first_line,
        "first_line": first_line.strip(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract methods from Python files safely",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("filepath", type=Path, help="Path to Python file")
    parser.add_argument("methods", nargs="+", help="Method name(s) to find/extract")
    parser.add_argument(
        "--info", action="store_true", help="Show method info only (no extraction)"
    )
    parser.add_argument("--extract", action="store_true", help="Extract method content")
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify extraction matches line count"
    )

    args = parser.parse_args()

    if not args.filepath.exists():
        print(f"Error: File not found: {args.filepath}", file=sys.stderr)
        sys.exit(1)

    with open(args.filepath, encoding="utf-8") as f:
        lines = f.readlines()

    results = []
    all_extracted = []

    for method_name in args.methods:
        info = get_method_info(args.filepath, method_name)

        if info is None:
            print(
                f"Error: Method '{method_name}' not found in {args.filepath}",
                file=sys.stderr,
            )
            sys.exit(1)

        results.append(info)

        if args.extract:
            extracted = extract_method(lines, info["start_line"], info["end_line"])
            all_extracted.extend(extracted)
            if len(args.methods) > 1:
                all_extracted.append("\n")  # Blank line between methods

    # Output info
    if args.info or not args.extract:
        print(f"{'Method':<45} {'Lines':<12} {'Count':<8} {'Async':<6}")
        print("-" * 75)
        for info in results:
            async_str = "Yes" if info["is_async"] else "No"
            print(
                f"{info['name']:<45} {info['start_line']}-{info['end_line']:<8} {info['line_count']:<8} {async_str:<6}"
            )
        print("-" * 75)
        total = sum(r["line_count"] for r in results)
        print(f"{'TOTAL':<45} {'':<12} {total:<8}")
        print()
        print("First lines (for verification):")
        for info in results:
            print(f"  {info['start_line']}: {info['first_line'][:70]}...")

    # Output extracted content
    if args.extract:
        content = "".join(all_extracted)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"\nExtracted {len(all_extracted)} lines to {args.output}")

            # Verify
            if args.verify:
                expected = (
                    sum(r["line_count"] for r in results) + len(args.methods) - 1
                )  # +blank lines
                actual = len(all_extracted)
                if actual == expected:
                    print(f"✓ Line count verified: {actual} lines")
                else:
                    print(
                        f"✗ Line count mismatch: expected {expected}, got {actual}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        else:
            print("\n" + "=" * 80)
            print("EXTRACTED CONTENT:")
            print("=" * 80)
            print(content)
            print("=" * 80)


if __name__ == "__main__":
    main()
