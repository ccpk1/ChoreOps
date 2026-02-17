#!/bin/bash
# Quick lint check - run after every change using ruff
# Usage: ./utils/quick_lint.sh [--fix]

# === LINT TARGET ROOT (change here if repo moves) ===
LINT_TARGET_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# If you move the repo, this resolves automatically from script location.

cd "$LINT_TARGET_ROOT" || exit 1

run_mypy_quick() {
    echo ""
    echo "🔍 Running mypy type checking..."

    if [[ "${FULL_MYPY:-0}" == "1" ]]; then
        echo "FULL_MYPY=1 set; running full mypy on integration + tests"
        mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops tests
        return $?
    fi

    echo "Default mode: checking production integration code only"
    mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops
}

echo "🔍 Running ruff linting..."
echo ""

if [[ "$1" == "--fix" ]]; then
    # Auto-fix issues with ruff
    echo "🔧 Running ruff check with auto-fix..."
    ruff check --fix custom_components/choreops tests
    ruff_check_exit=$?

    echo ""
    echo "🔧 Running ruff format..."
    ruff format custom_components/choreops tests
    ruff_format_exit=$?

    run_mypy_quick
    mypy_exit=$?

    echo ""
    echo "🏛️ Running architectural boundary checks..."
    python utils/check_boundaries.py
    boundary_exit=$?

    if [ $ruff_check_exit -eq 0 ] && [ $ruff_format_exit -eq 0 ] && [ $mypy_exit -eq 0 ] && [ $boundary_exit -eq 0 ]; then
        echo ""
        echo "✅ All auto-fixes applied! Verify changes and commit."
        exit 0
    else
        echo ""
        echo "⚠️ Some issues remain after auto-fix. Review output above."
        exit 1
    fi
else
    # Check only (no auto-fix)
    echo "Running ruff check (read-only)..."
    ruff check custom_components/choreops tests
    ruff_check_exit=$?

    echo ""
    echo "Checking code formatting..."
    ruff format --check custom_components/choreops tests
    ruff_format_exit=$?

    run_mypy_quick
    mypy_exit=$?

    echo ""
    echo "🏛️ Running architectural boundary checks..."
    python utils/check_boundaries.py
    boundary_exit=$?

    if [ $ruff_check_exit -eq 0 ] && [ $ruff_format_exit -eq 0 ] && [ $mypy_exit -eq 0 ] && [ $boundary_exit -eq 0 ]; then
        echo ""
        echo "✅ All checks passed! Ready to commit."
        exit 0
    else
        echo ""
        echo "❌ Linting issues found. Run with --fix to auto-correct:"
        echo "  ./utils/quick_lint.sh --fix"
        exit 1
    fi
fi
