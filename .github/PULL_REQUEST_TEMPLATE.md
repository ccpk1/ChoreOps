## Summary

- Describe what changed and why.

## Validation

- [ ] `./utils/quick_lint.sh --fix`
- [ ] `python -m pytest tests/ -v --tb=line` (or targeted suite with rationale)

## Rebrand guardrails (v0.5.0)

- [ ] No cosmetic internal variable renames in core data paths (`kid_id`, `parent_data`, etc.)
- [ ] Legacy compatibility decisions are explicit (shim kept/removed with rationale)
- [ ] If user-facing identifiers changed, migration and release notes were updated
