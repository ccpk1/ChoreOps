# Supporting doc: strict closure gates for `CHOREOPS-HF-STRICT-002`

## Purpose

Define the exact pass/fail closure gates for strict hard-fork completion with zero ambiguity.

## Non-negotiable closure policy

- Closure is **blocked** unless **every** mandatory gate below passes.
- “Almost zero,” “legacy alias retained temporarily,” or “functionally equivalent” are explicit failures.
- If any gate returns non-zero findings, initiative status remains **In progress**.
- No allowlist, waiver, exception table, or migration carve-out can be used to pass these gates.

## Gate set A: `const.py` strict lexical zero-state

All commands are executed from repo root (`/workspaces/choreops`).

### A1. Whole-word legacy term lines in const

```bash
grep -Inw -E 'kid|parent' custom_components/choreops/const.py
```

- **Pass criterion**: no output
- **Fail criterion**: any output line

### A2. Constant-definition names containing legacy terms

```bash
grep -InE '^[A-Z0-9_]*(KID|PARENT)[A-Z0-9_]*\s*=' custom_components/choreops/const.py
```

- **Pass criterion**: no output
- **Fail criterion**: any constant definition match

### A3. Literal assignment values containing legacy terms

```bash
grep -InE '=\s*["\x27][^"\x27]*\b(kid|parent)\b[^"\x27]*["\x27]' custom_components/choreops/const.py
```

- **Pass criterion**: no output
- **Fail criterion**: any literal-value match

### A4. Comment lines containing legacy terms

```bash
grep -InE '^\s*#.*\b(kid|parent)\b' custom_components/choreops/const.py
```

- **Pass criterion**: no output
- **Fail criterion**: any comment match

## Gate set B: runtime and docs zero-state guardrails

### B1. Runtime python legacy terms

```bash
grep -RInw -E 'kid|parent' custom_components/choreops --include='*.py'
```

- **Pass criterion**: no output
- **Fail criterion**: any output line

### B2. Top-level docs lexical gate

```bash
grep -Inw -E 'kid|parent' docs/*.md
```

- **Pass criterion**: no output
- **Fail criterion**: any output line

## Gate set C: quality and regression gates

### C1. Quality gate

```bash
./utils/quick_lint.sh --fix
```

- **Pass criterion**: command succeeds with no blocking errors

### C2. Type gate

```bash
mypy custom_components/choreops/
```

- **Pass criterion**: `Success: no issues found`

### C3. Full test gate

```bash
python -m pytest tests/ -v --tb=line
```

- **Pass criterion**: no test failures

## Evidence format required for closure request

Closure request must include:

1. Timestamped command output block for every gate (A1-A4, B1-B2, C1-C3)
2. Before/after metric table for `const.py` strict gates:
   - whole-word lines
   - constant-name matches
   - literal-value matches
   - comment matches
3. Explicit statement: `All strict gates passed with zero residual legacy findings in const.py`
4. Owner sign-off line with date

If any item is missing, closure request is invalid.

## Current baseline (recorded before execution)

- `const.py` whole-word lines with `kid|parent`: `75`
- `const.py` constant-name matches with `KID|PARENT`: `5`
- `const.py` literal-value assignment matches: `23`
- `const.py` comment matches: `36`

These must all reach `0` to satisfy Gate set A.

Gate sets B and C must also pass without exception.
