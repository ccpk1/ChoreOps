# Dashboard registry generation - Builder handoff

---

status: COMPLETE_ARCHIVED
owner: Strategist Agent
created: 2026-02-26
parent_plan: DASHBOARD_REGISTRY_GENERATION_COMPLETED.md
handoff_from: ChoreOps Strategist
handoff_to: ChoreOps Plan Agent
phase_focus: Phase 0-6 execution with hard-fork migration and parity tests

---

## Handoff button

[HANDOFF_TO_BUILDER_DASHBOARD_REGISTRY_GENERATION](DASHBOARD_REGISTRY_GENERATION_COMPLETED.md)

## Implementation runbook

- [Builder implementation plan](DASHBOARD_REGISTRY_GENERATION_SUP_BUILDER_IMPLEMENTATION.md)
- [Gap remediation plan](DASHBOARD_REGISTRY_GENERATION_SUP_GAP_REMEDIATION_PLAN.md)
- [Architecture standards and frozen decisions](DASHBOARD_REGISTRY_GENERATION_SUP_ARCH_STANDARDS.md)

## Handoff objective

Implement the dashboard registry generation migration exactly as ratified, including:

1. dual-repo source/vendored topology,
2. D11/D12 helper identity contract,
3. D13 canonical warning behavior,
4. D16 release/channel policy,
5. preference docs contract and runtime delivery,
6. translation bundle runtime update + fallback behavior,
7. full template lookup migration to instance-safe lookup contract,
8. dashboard helper lookup identity attribute completion,
9. create/update parity for release + prerelease selection,
10. dashboard provenance metadata stamping for troubleshooting.

## Hard constraints

- Hard-fork execution only: no legacy fallback paths retained.
- Remove obsolete constants, helpers, and path usage in-scope.
- Follow platinum standards (typing, docstrings, translation keys, lazy logging).
- Treat `DASHBOARD_REGISTRY_GENERATION_SUP_BUILDER_IMPLEMENTATION.md` as source of execution truth.

## Builder acceptance gate

- All required phases complete in the implementation plan.
- Validation commands pass:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- Test coverage includes D11/D12/D13, path migrations, release/channel behavior, cache/fallback paths, and preference metadata/asset contracts.
- Sync tooling + CI parity checks are in place and documented.
