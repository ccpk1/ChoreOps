#!/usr/bin/env python3
"""Test the cleanup script logic on specific real examples."""

import sys

sys.path.insert(0, "/workspaces/kidschores-ha/utils")

from cleanup_pylint_suppressions import process_line

# Test cases from actual coordinator.py
test_cases = [
    # Case 1: Module-level, should be removed entirely
    {
        "input": "# pylint: disable=too-many-lines,too-many-public-methods\n",
        "expected_removed": True,
        "description": "Module-level complexity suppressions (lines 12)",
    },
    # Case 2: Inline broad-except, should convert to BLE001
    {
        "input": "        except Exception as err:  # pylint: disable=broad-exception-caught\n",
        "expected_output": "        except Exception as err:  # ruff: noqa: BLE001\n",
        "description": "Inline broad-exception-caught (line 181)",
    },
    # Case 3: Multiple complexity rules on separate line, should be removed
    {
        "input": "    # pylint: disable=too-many-locals,too-many-branches\n",
        "expected_removed": True,
        "description": "Function-level complexity suppressions (line 714)",
    },
    # Case 4: Inline unused-argument, should convert to ARG001
    {
        "input": "    def claim_chore(self, kid_id: str, chore_id: str, user_name: str):  # pylint: disable=unused-argument\n",
        "expected_output": "    def claim_chore(self, kid_id: str, chore_id: str, user_name: str):  # ruff: noqa: ARG001\n",
        "description": "Inline unused-argument (line 2280)",
    },
    # Case 5: Mixed - complexity + unused-argument, should convert only unused-argument
    {
        "input": "    # pylint: disable=too-many-locals,too-many-branches,unused-argument\n",
        "expected_output": "    # ruff: noqa: ARG001\n",
        "description": "Mixed complexity and unused-argument (line 2468)",
    },
    # Case 6: Many complexity rules, should all be removed
    {
        "input": "    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements\n",
        "expected_removed": True,
        "description": "Many complexity rules (line 3493)",
    },
]


def run_tests():
    """Run all test cases."""
    print("=" * 80)  # noqa: T201
    print("Testing Cleanup Script Logic on Real Examples")  # noqa: T201
    print("=" * 80)  # noqa: T201
    print()  # noqa: T201

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['description']}")  # noqa: T201
        print(f"Input:  {test['input']!r}")  # noqa: T201

        modified_line, was_changed, change_type = process_line(test["input"])

        # Check expectations
        if test.get("expected_removed"):
            # Should be removed (empty or just whitespace)
            expected_result = modified_line.strip() == ""
            result_str = (
                "REMOVED"
                if expected_result
                else f"NOT REMOVED (got: {modified_line!r})"
            )
        elif "expected_output" in test:
            # Should match expected output
            expected_result = modified_line == test["expected_output"]
            result_str = f"Output: {modified_line!r}"
        else:
            expected_result = False
            result_str = "NO EXPECTATION DEFINED"

        print(f"Result: {result_str}")  # noqa: T201
        print(f"Changed: {was_changed}, Type: {change_type}")  # noqa: T201

        if expected_result:
            print("✅ PASS")  # noqa: T201
            passed += 1
        else:
            print("❌ FAIL")  # noqa: T201
            failed += 1
        print()  # noqa: T201

    print("=" * 80)  # noqa: T201
    print(f"Results: {passed} passed, {failed} failed")  # noqa: T201
    print("=" * 80)  # noqa: T201

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
