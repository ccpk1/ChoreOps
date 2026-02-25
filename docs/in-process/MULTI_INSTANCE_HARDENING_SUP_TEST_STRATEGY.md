# Supporting test strategy: Multi-instance hardening (Phase 1)

## Objective

Define a focused, fast feedback test suite for Phase 1 changes:
- Hybrid service target resolution
- Multi-entry-safe service lifecycle
- Entry-scoped device identifier behavior
- Documentation alignment checks

Primary initiative plan:
- [MULTI_INSTANCE_HARDENING_IN-PROCESS.md](./MULTI_INSTANCE_HARDENING_IN-PROCESS.md)

## Test architecture approach

- Use scenario-driven setup from `tests/scenarios/` (Stårblüm family) wherever possible.
- Add dual-config-entry fixtures for isolation checks.
- Prefer service-call and button workflows for behavior validation.
- Keep notification payload tests out of Phase 1 (deferred by decision).

## Test matrix

| Area | Test case | Expected result |
| --- | --- | --- |
| Service targeting | `config_entry_id` provided and valid | Handler routes to exact entry |
| Service targeting | `config_entry_id` provided and invalid | Clear actionable error |
| Service targeting | Omitted with one loaded entry | Auto-select single entry |
| Service targeting | Omitted with multiple loaded entries | Ambiguous target error + available entries |
| Service targeting | Optional title provided and unique (if enabled) | Resolves correctly |
| Service targeting | Optional title provided and ambiguous (if enabled) | Explicit ambiguity error |
| Service lifecycle | Register services with first entry | Services registered |
| Service lifecycle | Load second entry | No duplicate registration side-effects |
| Service lifecycle | Unload one of two entries | Services remain available |
| Service lifecycle | Unload final entry | Services removed |
| Device identity | Create same-name/same-ID-like users across two entries | Distinct devices per entry |
| Device identity | User deletion cleanup | Only target entry device removed |
| Device identity | System orphan cleanup | No cross-entry device removal |
| Diagnostics parsing | Device identifier decode | Correct assignee extraction for scoped format |

## Recommended test files

- `tests/test_services_target_resolution.py`
  - Resolver logic tests and service-level behavior tests.
- `tests/test_services_lifecycle_multi_entry.py`
  - Registration/unregistration reference-count behavior.
- `tests/test_device_identifier_scoping.py`
  - Device creation/lookup/delete/orphan cleanup paths.

If repository conventions prefer existing modules, fold cases into nearest existing test files and keep naming as sub-sections.

## Fixture plan

- `single_entry_setup`:
  - One config entry via scenario setup.
- `dual_entry_setup`:
  - Two ChoreOps config entries loaded in same HA test runtime.
  - Use distinct titles (e.g., `ChoreOps` and `ChoreOps Family B`).
  - Overlap user display names intentionally to prove target isolation.

## Assertions checklist (critical)

- Service call modifies only intended entry’s storage and entities.
- Errors are user-actionable and reference next-step fields to supply.
- No service disappears while at least one entry remains loaded.
- Device registry lookups and removals are always scoped.

## Performance and CI guidance

- Keep new tests focused and isolated from full-suite complexity.
- Prefer small targeted modules for quick local iteration.
- After focused runs pass, include full suite gate in final verification.

## Execution commands

1. `./utils/quick_lint.sh --fix`
2. `mypy custom_components/choreops/`
3. Focused runs (new files)
   - `python -m pytest tests/test_services_target_resolution.py -v`
   - `python -m pytest tests/test_services_lifecycle_multi_entry.py -v`
   - `python -m pytest tests/test_device_identifier_scoping.py -v`
4. Broader confidence
   - `python -m pytest tests/ -v`

## Documentation verification

After code/tests pass, verify docs reflect behavior:

- `custom_components/choreops/services.yaml`
- `README.md`
- ChoreOps wiki service pages/FAQ

Checklist:
- Single-entry examples omit target field
- Multi-entry examples include `config_entry_id`
- Troubleshooting section covers ambiguous target error
