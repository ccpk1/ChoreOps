# ChoreOps Code review guide

This guide defines a repeatable review process for ChoreOps changes.

Use this document for architectural and quality verification. For coding style and naming rules, use [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md).

## Scope

Use this checklist for any pull request that changes:

- `custom_components/choreops/`
- `tests/`
- `docs/` where behavior or workflows are described

## Review principles

- Prioritize architectural correctness over style feedback.
- Verify boundaries before reviewing implementation details.
- Prefer durable checks over one-off observations.
- Use User/Approver terminology for role capabilities.
- Use Item/Record for storage objects and Entity for Home Assistant platform objects.

## Required review flow

### 0) Boundary check (required first)

Run these checks before deeper review.

#### A. Purity check (`utils/`, `engines/`, `data_builders.py`)

```bash
grep -r "from homeassistant" custom_components/choreops/utils/
grep -r "from homeassistant" custom_components/choreops/engines/
grep -r "import homeassistant" custom_components/choreops/utils/
grep -r "import homeassistant" custom_components/choreops/engines/
grep -r "from homeassistant" custom_components/choreops/data_builders.py
grep -r "import homeassistant" custom_components/choreops/data_builders.py
```

Pass criteria:

- No Home Assistant imports in pure modules.

#### B. Lexicon check (items vs entities)

```bash
grep -rn "Chore Entity\|Kid Entity\|Parent Entity\|Badge Entity\|Reward Entity\|User Entity" custom_components/choreops/
grep -rn "entity data\|Entity data" custom_components/choreops/ | grep -v "Entity ID"
```

Pass criteria:

- Storage records use Item/Record language.
- Entity language is only used for HA entities and entity IDs.

#### C. CRUD ownership check (single write path)

```bash
grep -n "coordinator._data\[\|self._data\[" custom_components/choreops/options_flow.py
grep -n "coordinator._persist()\|self._persist()" custom_components/choreops/options_flow.py
grep -n "coordinator._data\[\|self._data\[" custom_components/choreops/services.py
grep -n "coordinator._persist()\|self._persist()" custom_components/choreops/services.py
```

Pass criteria:

- UI and service layers do not write storage directly.
- State writes are delegated to manager methods.

#### D. Manager coupling check (signal-first)

```bash
grep -rn "self\.coordinator\.\w*_manager\." custom_components/choreops/managers/
grep -rn "await.*_manager\." custom_components/choreops/managers/
```

Pass criteria:

- No direct cross-manager write calls.
- Cross-domain workflows are signal-based.

### 1) Change-scope review

Confirm the PR scope is coherent and minimal:

- New files are in the correct architectural layer.
- Existing APIs are not changed without migration or compatibility notes.
- Documentation updates match behavior changes.

### 2) Architecture contract review

Validate each changed file against this matrix.

| If code does this                       | It should live in                               | It should not live in             |
| --------------------------------------- | ----------------------------------------------- | --------------------------------- |
| Pure logic/calculation                  | `engines/` or `utils/`                          | `managers/`, `helpers/`           |
| Uses `hass`, dispatcher, or service bus | `managers/` or HA platform files                | `engines/`, `utils/`              |
| Uses registry APIs                      | `helpers/`                                      | `engines/`, `utils/`              |
| Sanitizes flow input payloads           | `data_builders.py` or `helpers/flow_helpers.py` | `services.py`, unrelated managers |
| Persists `_data`                        | `managers/` only                                | Any other layer                   |

### 3) Quality gate review

Confirm contributors ran the standard gates:

```bash
./utils/quick_lint.sh --fix
mypy custom_components/choreops/
python -m pytest tests/ -v --tb=line
```

Reviewer expectation:

- No unresolved lint/type/test failures related to changed scope.
- No suppressions added without justification.

### 4) API and UX contract review

For behavior changes, verify:

- Config/Options flows use constants and translation keys.
- Services validate inputs and fail with translatable exceptions.
- Entity IDs and unique IDs are stable and deterministic.
- New user-facing text is translated via `translations/en.json`.

### 5) Translation and constant review

Run targeted checks on changed files:

```bash
grep -n "TRANS_KEY_\|CFOP_ERROR_" custom_components/choreops/**/*.py
grep -n "errors\[.*\] = \"" custom_components/choreops/**/*.py
grep -n "description=\"[A-Z]" custom_components/choreops/**/*.py
grep -n "title=\"[A-Z]" custom_components/choreops/**/*.py
```

Pass criteria:

- User-facing strings use constants + translations.
- No new hardcoded user text.

### 6) Entry-scope and migration review

When a change touches storage, restore, or migration paths, verify:

- Data access stays config-entry scoped.
- No "first loaded entry" routing behavior is introduced.
- Migration code is additive, ordered, and safe to re-run.
- Backup/restore behavior is explicit and scoped.

### 7) Review output template

Use this summary in PR reviews:

```markdown
## Review summary

- Boundary checks: pass/fail
- Architecture placement: pass/fail
- CRUD and signal-first contract: pass/fail
- Quality gates: pass/fail
- Translation/constants: pass/fail
- Entry-scope/migration safety: pass/fail

## Required changes

- [ ] Item 1
- [ ] Item 2

## Notes

- Any accepted risk and rationale
```

## Escalation rules

Block merge when any of these are present:

- Home Assistant imports in pure layers
- Direct storage writes outside managers
- Direct cross-manager write calls
- Hardcoded user-facing strings
- Missing translation keys for new user-facing text
- Cross-entry behavior that bypasses explicit target resolution

## References

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md)
- [QUALITY_REFERENCE.md](QUALITY_REFERENCE.md)
- [custom_components/choreops/quality_scale.yaml](../custom_components/choreops/quality_scale.yaml)
