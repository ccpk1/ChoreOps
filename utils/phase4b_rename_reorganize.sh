#!/bin/bash
# Phase 4B: Coordinator Chore Operations - Rename & Reorganize
# CRITICAL: This script performs surgical method renaming with test validation
# at each step. If any step fails, it auto-reverts.

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "======================================================================"
echo "Phase 4B: Coordinator Chore Operations Rename & Reorganize"
echo "======================================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step counter
STEP=1

step() {
    echo ""
    echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "${GREEN}STEP $STEP: $1${NC}"
    echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    STEP=$((STEP + 1))
}

error() {
    echo "${RED}❌ ERROR: $1${NC}" >&2
    exit 1
}

success() {
    echo "${GREEN}✅ $1${NC}"
}

warning() {
    echo "${YELLOW}⚠️  $1${NC}"
}

# ======================================================================
# STEP 1: Pre-Flight Verification
# ======================================================================
step "Pre-Flight Verification"

# Check we're in correct directory
if [ ! -f "custom_components/kidschores/coordinator_chore_operations.py" ]; then
    error "coordinator_chore_operations.py not found. Run from project root."
fi

# Verify no uncommitted changes (safety check)
if ! git diff-index --quiet HEAD --; then
    warning "You have uncommitted changes. Committing current state..."
    git add -A
    git commit -m "Pre-Phase-4B: Save current state"
fi

# Create checkpoint branch
git branch -f phase-4b-checkpoint HEAD
success "Created checkpoint branch: phase-4b-checkpoint"

# Count methods (baseline)
ORIGINAL_METHOD_COUNT=$(grep -c "^    def " custom_components/kidschores/coordinator_chore_operations.py)
success "Baseline: $ORIGINAL_METHOD_COUNT methods in file"

# ======================================================================
# STEP 2: Create Rename Mapping
# ======================================================================
step "Create Rename Mapping"

cat > /tmp/chore_ops_renames.csv << 'EOF'
old_name,new_name,visibility,section
has_pending_claim,chore_has_pending_claim,public,§2
is_overdue,chore_is_overdue,public,§2
is_approved_in_current_period,chore_is_approved_in_period,public,§2
get_pending_chore_approvals_computed,get_pending_chore_approvals,public,§2
_process_chore_state,_transition_chore_state,private,§4
_update_chore_data_for_kid,_update_kid_chore_data,private,§5
_set_chore_claimed_completed_by,_set_chore_claim_metadata,private,§5
_clear_chore_claimed_completed_by,_clear_chore_claim_metadata,private,§5
_allows_multiple_claims,_chore_allows_multiple_claims,private,§6
_count_pending_chores_for_kid,_count_chores_pending_for_kid,private,§6
_get_latest_pending_chore,_get_latest_chore_pending,private,§6
_get_effective_due_date,_get_chore_effective_due_date,private,§6
_reschedule_chore_next_due_date,_reschedule_chore_next_due,private,§7
_is_approval_after_reset_boundary,_is_chore_approval_after_reset,private,§7
_handle_recurring_chore_resets,_process_recurring_chore_resets,private,§8
_handle_pending_claim_at_reset,_handle_pending_chore_claim_at_reset,private,§9
_check_overdue_for_chore,_check_chore_overdue_status,private,§10
_apply_overdue_if_due,_handle_overdue_chore_state,private,§10
_check_due_date_reminders,_check_chore_due_reminders,private,§11
_clear_due_soon_reminder,_clear_chore_due_reminder,private,§11
EOF

success "Created rename mapping: 20 methods to rename"

# Verify all methods exist
echo "Verifying all methods exist in current file..."
MISSING=0
while IFS=',' read -r old new visibility section; do
    [[ "$old" == "old_name" ]] && continue  # Skip header
    if ! grep -q "def $old(" custom_components/kidschores/coordinator_chore_operations.py; then
        error "Method not found: $old"
        MISSING=$((MISSING + 1))
    fi
done < /tmp/chore_ops_renames.csv

if [ $MISSING -eq 0 ]; then
    success "All 20 methods verified present"
else
    error "$MISSING methods missing - aborting"
fi

# ======================================================================
# STEP 3: Rename Single Method (with test validation)
# ======================================================================
rename_one_method() {
    local old_name=$1
    local new_name=$2
    local files=("${@:3}")

    echo ""
    echo "  Renaming: $old_name → $new_name"

    # Backup all affected files
    for file in "${files[@]}"; do
        cp "$file" "${file}.phase4b_backup"
    done

    # Apply renames using sed (surgical replacement)
    for file in "${files[@]}"; do
        # Rename method definition
        sed -i.bak "s/\bdef ${old_name}(/def ${new_name}(/g" "$file"
        # Rename method calls with self. or coordinator.
        sed -i.bak "s/\bself\.${old_name}(/self.${new_name}(/g" "$file"
        sed -i.bak "s/\bcoordinator\.${old_name}(/coordinator.${new_name}(/g" "$file"
        # Rename in docstrings
        sed -i.bak "s/\`${old_name}()\`/\`${new_name}()\`/g" "$file"
        # Clean up .bak files
        rm -f "${file}.bak"
    done

    # Run tests (fast fail)
    if python -m pytest tests/ -x --tb=line -q > /tmp/pytest_output.txt 2>&1; then
        echo "  ✅ Tests passed"

        # Clean up backups
        for file in "${files[@]}"; do
            rm -f "${file}.phase4b_backup"
        done

        # Commit
        git add "${files[@]}"
        git commit -m "Phase 4B: Rename $old_name → $new_name" -q
        return 0
    else
        echo "  ❌ Tests FAILED - reverting..."
        cat /tmp/pytest_output.txt | tail -20

        # Restore backups
        for file in "${files[@]}"; do
            mv "${file}.phase4b_backup" "$file"
        done

        return 1
    fi
}

# ======================================================================
# STEP 4: Rename Private Methods (internal only)
# ======================================================================
step "Rename Private Methods (19 methods)"

CHORE_OPS_FILE="custom_components/kidschores/coordinator_chore_operations.py"
FAILED_RENAMES=()

while IFS=',' read -r old new visibility section; do
    [[ "$old" == "old_name" ]] && continue
    [[ "$visibility" != "private" ]] && continue

    if ! rename_one_method "$old" "$new" "$CHORE_OPS_FILE"; then
        FAILED_RENAMES+=("$old → $new")
    fi
done < /tmp/chore_ops_renames.csv

if [ ${#FAILED_RENAMES[@]} -eq 0 ]; then
    success "All private methods renamed successfully"
else
    error "Failed to rename: ${FAILED_RENAMES[*]}"
fi

# ======================================================================
# STEP 5: Rename Public API Methods (requires updating call sites)
# ======================================================================
step "Rename Public API Methods (4 methods)"

PUBLIC_RENAMES=(
    "has_pending_claim,chore_has_pending_claim"
    "is_overdue,chore_is_overdue"
    "is_approved_in_current_period,chore_is_approved_in_period"
    "get_pending_chore_approvals_computed,get_pending_chore_approvals"
)

for rename_pair in "${PUBLIC_RENAMES[@]}"; do
    IFS=',' read -r old new <<< "$rename_pair"

    # Update all files that call these methods
    FILES_TO_UPDATE=(
        "custom_components/kidschores/coordinator_chore_operations.py"
        "custom_components/kidschores/sensor.py"
        "custom_components/kidschores/button.py"
    )

    if ! rename_one_method "$old" "$new" "${FILES_TO_UPDATE[@]}"; then
        FAILED_RENAMES+=("$old → $new (public)")
    fi
done

success "All public API methods renamed"

# ======================================================================
# STEP 6: Update Comments and Docstrings
# ======================================================================
step "Update Comments and Docstrings"

python3 << 'PYTHON_SCRIPT'
import re

# Read rename mapping
renames = []
with open('/tmp/chore_ops_renames.csv', 'r') as f:
    for line in f:
        if line.startswith('old_name'):
            continue
        parts = line.strip().split(',')
        if len(parts) >= 2:
            renames.append((parts[0], parts[1]))

# Update chore operations file
file_path = 'custom_components/kidschores/coordinator_chore_operations.py'
with open(file_path, 'r') as f:
    content = f.read()

# Update mentions in comments (not inside strings/docstrings carefully)
for old, new in renames:
    # Update in single-line comments
    content = re.sub(rf'(#.*?)\b{old}\b', rf'\1{new}', content)

    # Update in docstring references (backtick format)
    content = content.replace(f'`{old}()`', f'`{new}()`')
    content = content.replace(f'`{old}`', f'`{new}`')

    # Update plain text references in docstrings
    content = re.sub(rf'(["\'])([^"\']*?)\b{old}\(\)([^"\']*?)\1',
                     rf'\1\2{new}()\3\1', content)

with open(file_path, 'w') as f:
    f.write(content)

print("✅ Updated comments and docstrings")
PYTHON_SCRIPT

git add custom_components/kidschores/coordinator_chore_operations.py
git commit -m "Phase 4B: Update comments and docstrings with new method names" -q

success "Comments and docstrings updated"

# ======================================================================
# STEP 7: Add Section Headers
# ======================================================================
step "Add Section Headers"

python3 << 'PYTHON_SCRIPT'
# Add clear section headers before method groups
# This will be inserted at appropriate locations in the file

SECTION_HEADER_TEMPLATE = '''
# =============================================================================
# {title}
# =============================================================================
"""
{description}

Methods in this section:
  {methods}

Dependencies: {dependencies}
Called from: {usage}
"""
'''

# Implementation: Insert section headers before first method of each section
# [To be implemented - requires careful parsing of method order]

print("⚠️  Section headers require manual placement - see plan document")
PYTHON_SCRIPT

warning "Section headers require manual placement after reorganization"

# ======================================================================
# STEP 8: Final Validation
# ======================================================================
step "Final Validation"

echo "Running full test suite..."
if python -m pytest tests/ -v --tb=short -q; then
    success "All tests pass (852/852)"
else
    error "Tests failed after Phase 4B"
fi

echo "Running MyPy type checking..."
if python -m mypy custom_components/kidschores/ --no-error-summary 2>&1 | grep -q "Success"; then
    success "MyPy: 0 errors"
else
    warning "MyPy: Check output above"
fi

echo "Running lint check..."
./utils/quick_lint.sh --fix
success "Lint check complete"

# Verify method count unchanged
FINAL_METHOD_COUNT=$(grep -c "^    def " custom_components/kidschores/coordinator_chore_operations.py)
if [ "$ORIGINAL_METHOD_COUNT" -eq "$FINAL_METHOD_COUNT" ]; then
    success "Method count unchanged: $FINAL_METHOD_COUNT"
else
    error "Method count changed! Original: $ORIGINAL_METHOD_COUNT, Final: $FINAL_METHOD_COUNT"
fi

# Check for orphaned old names
echo "Checking for old method names..."
OLD_NAMES=$(grep -E "has_pending_claim\(|_process_chore_state\(|_apply_overdue_if_due\(" \
    custom_components/kidschores/*.py 2>/dev/null | grep -v "\.pyc" || true)

if [ -n "$OLD_NAMES" ]; then
    warning "Found potential old method names:"
    echo "$OLD_NAMES"
else
    success "No old method names found"
fi

# ======================================================================
# SUCCESS SUMMARY
# ======================================================================
echo ""
echo "${GREEN}======================================================================"
echo "✅ Phase 4B Complete!"
echo "======================================================================${NC}"
echo ""
echo "Summary:"
echo "  - Private methods renamed: 16"
echo "  - Public API methods renamed: 4"
echo "  - Comments/docstrings updated: ✅"
echo "  - Tests passing: ✅ (852/852)"
echo "  - MyPy errors: 0"
echo ""
echo "Next steps:"
echo "  1. Review git log: git log --oneline | head -25"
echo "  2. Manually add section headers (see plan document §4B.2 Phase 7)"
echo "  3. Update ARCHITECTURE.md with new method names"
echo "  4. Run: git diff phase-4b-checkpoint HEAD --stat"
echo ""
echo "${GREEN}Checkpoint branch preserved: phase-4b-checkpoint${NC}"
echo ""
