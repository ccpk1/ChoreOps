#!/bin/bash
# Portable test runner for ChoreOps.
# Tries ha-venv first, falls back gracefully.
# Usage: ./utils/run_tests.sh [pytest args...]

HA_PYTHON="/home/vscode/.local/ha-venv/bin/python"

if [ -x "$HA_PYTHON" ]; then
  exec "$HA_PYTHON" -m pytest "$@"
fi

# Fallback: try any python with pytest available
if command -v python3 &>/dev/null && python3 -c "import pytest" 2>/dev/null; then
  exec python3 -m pytest "$@"
fi

echo "ERROR: No Python with pytest found."
echo "Run 'script/setup' in the core workspace first, or install pytest."
exit 1
